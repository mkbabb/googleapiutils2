from __future__ import annotations

import http
import os
import pickle
import socket
import threading
import time
import urllib.parse
from collections.abc import Callable
from functools import cache
from mimetypes import guess_type
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from typing import (
    Any,
    ParamSpec,
    TypeVar,
)

import googleapiclient.http
from cachetools import TTLCache
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from loguru import logger

from googleapiutils2.utils.decorators import retry
from googleapiutils2.utils.misc import (
    CONFIG_ENV_VAR,
    CONFIG_PATH,
    DEFAULT_DOWNLOAD_CONVERSION_MAP,
    DEFAULT_TIMEOUT,
    EXECUTE_TIME,
    SCOPES,
    THROTTLE_TIME,
    TOKEN_PATH,
    FilePath,
    GoogleMimeTypes,
)
from googleapiutils2.utils.utils import Throttler, get_url_params, path_or_str_to_json

T = TypeVar("T")
P = ParamSpec("P")

socket.setdefaulttimeout(DEFAULT_TIMEOUT)




def export_mime_type(
    mime_type: GoogleMimeTypes,
    conversion_map: dict[
        GoogleMimeTypes, GoogleMimeTypes
    ] = DEFAULT_DOWNLOAD_CONVERSION_MAP,
) -> tuple[GoogleMimeTypes, str]:
    """Get the MIME type to export a file to and the corresponding file extension."""
    t_mime_type = conversion_map.get(mime_type)

    if t_mime_type is None:
        return mime_type, ""

    return t_mime_type, "." + t_mime_type.name


@cache
def mime_type_to_google_mime_type(mime_type: str) -> GoogleMimeTypes | None:
    for m in GoogleMimeTypes:
        if m.value == mime_type:
            return m
    return None


@cache
def guess_mime_type(
    filepath: FilePath,
) -> GoogleMimeTypes | None:
    mime_type, _ = guess_type(str(filepath))
    return mime_type_to_google_mime_type(mime_type)


class GoogleAPIException(Exception):
    pass


class InvalidRequestError(GoogleAPIException):
    pass


class OverQueryLimitError(GoogleAPIException):
    pass


class RequestDeniedError(GoogleAPIException):
    pass


class NotFoundError(GoogleAPIException):
    pass


class UnknownError(GoogleAPIException):
    pass


def raise_for_status(status: str) -> None:
    if status == "OK":
        return

    if status == "INVALID_REQUEST":
        raise InvalidRequestError("The request was invalid.")
    elif status == "OVER_QUERY_LIMIT":
        raise OverQueryLimitError("You are over your query limit.")
    elif status == "REQUEST_DENIED":
        raise RequestDeniedError("Your request was denied.")
    elif status == "NOT_FOUND":
        raise NotFoundError("The requested resource was not found.")
    elif status == "UNKNOWN_ERROR":
        raise UnknownError("An unknown error occurred.")
    else:
        raise GoogleAPIException("An unexpected error occurred.")


def on_http_exception(e: Exception) -> bool:
    # Retry rate limiting errors
    if isinstance(e, googleapiclient.errors.HttpError):  # type: ignore
        status = e.resp.status  # type: ignore
        return status == http.HTTPStatus.TOO_MANY_REQUESTS

    # Retry transient network/socket errors
    if isinstance(e, OSError):
        # Errno 49 (EADDRNOTAVAIL): Can't assign requested address - port exhaustion
        # Errno 48 (EADDRINUSE): Address already in use
        # Errno 54 (ECONNRESET): Connection reset by peer
        # Errno 61 (ECONNREFUSED): Connection refused
        if e.errno in (48, 49, 54, 61):
            return True

    # Retry connection and timeout errors
    if isinstance(e, (ConnectionError, TimeoutError, socket.timeout)):
        return True

    return False


class DriveThread:
    """Handles threaded execution of Google Drive API requests."""

    def __init__(
        self,
        worker_func: Callable[[googleapiclient.http.HttpRequest], Any],
    ):
        """
        Initialize the drive thread.

        Args:
            worker_func: Function to process each request
            name: Name for the worker thread
        """

        self._worker_func = worker_func

        self._request_queue: Queue[googleapiclient.http.HttpRequest | None] = Queue()

        self._request_thread: Thread | None = None

        self._monitor_thread: Thread | None = None

        self._init_worker()

        self._init_monitor()

    def _init_worker(self) -> None:
        """Initialize the worker thread for processing queued requests."""

        def _worker() -> None:
            while True:
                try:
                    # Get with timeout to allow checking stop flag
                    request = self._request_queue.get(timeout=1.0)
                except Empty:
                    continue

                if request is None:
                    break

                try:
                    t = time.perf_counter()

                    # logger.debug(f"Executing request: {request}")

                    self._worker_func(request)

                    time.perf_counter() - t

                    # logger.debug(f"Request completed in {dt:.2f} seconds")

                except Exception as e:
                    logger.error(f"Error executing request: {e}")
                finally:
                    self._request_queue.task_done()

            # logger.debug("Worker thread stopped")

        self._request_thread = Thread(
            target=_worker,
            daemon=False,
        )
        self._request_thread.start()

    def _init_monitor(self) -> None:
        def monitor_thread():
            main_thread = threading.main_thread()

            main_thread.join()

            self._cleanup()

        self._monitor_thread = Thread(target=monitor_thread, daemon=True)
        self._monitor_thread.start()

    def enqueue(self, request: googleapiclient.http.HttpRequest | None) -> None:
        """Add a request to the execution queue."""
        # logger.debug(f"Enqueuing request {id(self._request_queue)}: {request}")
        self._request_queue.put(request)

    def _cleanup(self) -> None:
        """Clean up resources and ensure graceful shutdown."""
        # Wait for remaining items in queue
        if self._request_thread is None:
            return

        self.enqueue(None)

        self._request_queue.join()

        self._request_thread.join()


class DriveBase:
    """Base class for Google Drive API operations with throttling and request queueing."""

    def __init__(
        self,
        creds: Credentials | ServiceAccountCredentials | None = None,
        execute_time: float = EXECUTE_TIME,
        throttle_time: float = THROTTLE_TIME,
    ):
        # Google Drive API service credentials
        self.creds = creds if creds is not None else get_oauth2_creds()

        # Create throttlers for different operations
        self._execute_throttler = Throttler(execute_time)
        self._execute_queue_throttler = Throttler(throttle_time)

        # TTL cache for various functions
        self._cache: TTLCache = TTLCache(maxsize=128, ttl=80)

        # Initialize drive thread
        self._drive_thread = DriveThread(worker_func=self.execute)

    @retry(
        retries=10,
        delay=30.0,
        exponential_backoff=False,
        on_exception=on_http_exception,
    )
    def execute(self, request: googleapiclient.http.HttpRequest) -> Any:
        """Execute a request with retry and throttling."""
        self._execute_throttler.throttle()

        return request.execute(num_retries=1)

    def execute_no_retry(self, request: googleapiclient.http.HttpRequest) -> Any:
        """Execute a request without retry."""
        self._execute_throttler.throttle()

        return request.execute(num_retries=0)

    def execute_queue(self, request: googleapiclient.http.HttpRequest) -> None:
        """Add a request to the execution queue."""
        self._drive_thread.enqueue(request)


def q_escape(s: str) -> str:
    s = s.replace("'", r"\'")
    return f"'{s}'"


def load_client_config(
    client_config: FilePath | dict | None = CONFIG_PATH,
):
    # If the client config is None, or it's a filepath that doesn't exist, load the environment variable
    if client_config is None:
        client_config = os.environ.get(CONFIG_ENV_VAR, None)
    elif isinstance(client_config, str | Path):
        client_config_path = Path(client_config)

        if not client_config_path.exists():
            client_config = os.environ.get(CONFIG_ENV_VAR, None)

    if client_config is None:
        raise Exception(
            "No client config found. Please provide a client config file or dict object, or set the GOOGLE_API_CREDENTIALS environment variable."
        )

    if isinstance(client_config, dict):
        return client_config
    elif isinstance(client_config, str | Path):
        return path_or_str_to_json(client_config)


def get_oauth2_creds(
    client_config: FilePath | dict | None = CONFIG_PATH,
    token_path: FilePath | None = TOKEN_PATH,
    scopes: list[str] = SCOPES,
    *args: Any,
    **kwargs: Any,
) -> Credentials | ServiceAccountCredentials | Any:
    """Get OAuth2 credentials for Google API.

    If the client config provided is for a service account, we return the credentials.
    Otherwise, we return the credentials from the token file if it exists, or we
    authenticate the user and save the credentials to the token file.

    If the client config is a path to a file, we first check if the file exists.
    If it doesn't, we check if the GOOGLE_API_CREDENTIALS environment variable is set.
    If it is, we use the path provided by the environment variable.

    Args:
        client_config: Path to client config file or dict with client config.
        token_path: Path to token file.
        scopes: List of scopes. For more information on scopes, see:
            https://developers.google.com/identity/protocols/oauth2/scopes
    """

    client_config = load_client_config(client_config=client_config)

    is_service_account = client_config is not None and client_config.get("type", "") == "service_account"  # type: ignore

    if is_service_account:
        return service_account.Credentials.from_service_account_info(client_config, scopes=scopes, *args, **kwargs)  # type: ignore
    elif token_path is not None:
        token_path = Path(token_path)  # type: ignore
        creds: Credentials | None = None

        if token_path.exists():
            creds = pickle.loads(token_path.read_bytes())

        if creds is not None and not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())

        elif creds is None:
            flow = InstalledAppFlow.from_client_config(
                client_config, scopes=scopes, *args, **kwargs
            )
            creds = flow.run_local_server(port=0)  # type: ignore

            token_path.write_bytes(pickle.dumps(creds))

        return creds  # type: ignore

    raise Exception("No token path provided.")


def get_id_from_url(url: str) -> str:
    """
    Extracts the ID from the URL provided.

    This function supports URLs of the form:
    - '.../folders/{id}/...'
    - '.../d/{id}/...'
    - With a query parameter named 'id': '...?id={id}...'

    Args:
        url (str): The URL string from which to extract the ID.

    Raises:
        ValueError: If the function can't parse the URL to find an ID.

    Examples:
    --------
    >>> get_id_from_url('https://example.com/folders/123456789')
    '123456789'

    >>> get_id_from_url('https://example.com/d/123456789')
    '123456789'

    >>> get_id_from_url('https://example.com/?id=123456789')
    '123456789'
    """
    url_obj = urllib.parse.urlparse(url)
    path = url_obj.path
    paths = path.split("/")

    get_adjacent = lambda x: (
        paths[t_ix]
        if x in paths and (t_ix := paths.index(x) + 1) < len(paths)
        else None
    )

    id = get_adjacent("folders") or get_adjacent("d")

    if id is not None:
        return id
    else:
        params = get_url_params(url)
        if (ids := params.get("id")) is not None:
            return ids[0]
        else:
            raise ValueError(f"Could not parse file URL of {url}")


@cache
def parse_file_id(
    file_id: str,
) -> str:
    """
    Parse the given file_id which could be an ID string, URL string or a dictionary object.

    This function supports the following formats:
    - Direct ID string: '123456789'
    - URL formats supported by 'get_id_from_url' function.
    - Dictionary object with 'id' or 'spreadsheetId' as keys.

    Args:
        file_id (str): The ID string or URL or dictionary from which to extract the ID.

    Examples:
    --------
    >>> parse_file_id('123456789')
    '123456789'

    >>> parse_file_id('https://example.com/d/123456789')
    '123456789'

    >>> parse_file_id({'id': '123456789'})
    '123456789'
    """

    def parse(file_id: str) -> str:
        if "http" in file_id:
            return get_id_from_url(file_id)
        else:
            return file_id

    def obj_to_id(file: str) -> str:
        if isinstance(file, str):
            return file
        elif isinstance(file, dict):
            return file.get("id", file.get("spreadsheetId", None))

    if (id := obj_to_id(file_id)) is not None:
        return parse(id)
    else:
        return file_id
