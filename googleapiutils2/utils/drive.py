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
    conversion_map: dict[GoogleMimeTypes, GoogleMimeTypes] = DEFAULT_DOWNLOAD_CONVERSION_MAP,
) -> tuple[GoogleMimeTypes, str]:
    """Determine export MIME type and file extension for download operations.

    This function is used during download to convert Google Workspace native formats
    (which can't be downloaded directly) to standard exportable formats. It also
    assigns the appropriate file extension based on the export format.

    Conversion Logic:
        1. Check if mime_type exists in conversion_map
        2. If found: Return mapped export format and its extension (e.g., ".xlsx")
        3. If not found: Return original mime_type and empty extension

    The extension is derived from the MIME type's enum name. For example:
        GoogleMimeTypes.xlsx → ".xlsx"
        GoogleMimeTypes.pdf → ".pdf"

    Args:
        mime_type: Source MIME type from Google Drive file
        conversion_map: Maps native formats to export formats.
            Defaults to DEFAULT_DOWNLOAD_CONVERSION_MAP which converts:
            - sheets → xlsx
            - docs → docx
            - slides → pdf

    Returns:
        Tuple of (export_mime_type, file_extension):
            - export_mime_type: MIME type to use for export
            - file_extension: Extension with leading dot (e.g., ".xlsx") or empty string

    Examples:
        >>> export_mime_type(GoogleMimeTypes.sheets)
        (GoogleMimeTypes.xlsx, ".xlsx")

        >>> export_mime_type(GoogleMimeTypes.docs)
        (GoogleMimeTypes.docx, ".docx")

        >>> export_mime_type(GoogleMimeTypes.png)
        (GoogleMimeTypes.png, "")  # No conversion needed

        >>> custom_map = {GoogleMimeTypes.sheets: GoogleMimeTypes.csv}
        >>> export_mime_type(GoogleMimeTypes.sheets, custom_map)
        (GoogleMimeTypes.csv, ".csv")

    See also:
        DEFAULT_DOWNLOAD_CONVERSION_MAP in utils/misc.py: Default conversion mappings
        Drive.download(): Uses this function to determine export format
    """
    t_mime_type = conversion_map.get(mime_type)

    if t_mime_type is None:
        return mime_type, ""

    return t_mime_type, "." + t_mime_type.name


@cache
def mime_type_to_google_mime_type(mime_type: str) -> GoogleMimeTypes | None:
    """Convert MIME type string to GoogleMimeTypes enum.

    Performs reverse lookup from MIME type value (e.g., "text/csv") to the
    corresponding GoogleMimeTypes enum member (e.g., GoogleMimeTypes.csv).

    This is used when Google Drive API returns MIME type strings in file metadata,
    and we need to work with the GoogleMimeTypes enum.

    Args:
        mime_type: MIME type string (e.g., "text/csv", "application/pdf")

    Returns:
        GoogleMimeTypes enum member if found, None otherwise

    Examples:
        >>> mime_type_to_google_mime_type("text/csv")
        GoogleMimeTypes.csv

        >>> mime_type_to_google_mime_type("application/vnd.google-apps.spreadsheet")
        GoogleMimeTypes.sheets

        >>> mime_type_to_google_mime_type("unknown/type")
        None

    Note:
        Result is cached for performance since this is called frequently.
    """
    for m in GoogleMimeTypes:
        if m.value == mime_type:
            return m
    return None


@cache
def guess_mime_type(
    filepath: FilePath,
) -> GoogleMimeTypes | None:
    """Infer GoogleMimeTypes from file path extension.

    Uses Python's mimetypes module to guess MIME type from file extension,
    then converts to GoogleMimeTypes enum. This is the primary method for
    inferring from_mime_type during upload when not explicitly specified.

    Inference Process:
        1. Extract file extension from filepath (e.g., "data.csv" → ".csv")
        2. Use Python's guess_type() to get standard MIME type string
        3. Convert MIME type string to GoogleMimeTypes enum
        4. Return None if extension is unknown or not in GoogleMimeTypes

    Args:
        filepath: File path (str or Path) to infer MIME type from

    Returns:
        GoogleMimeTypes enum member if extension recognized, None otherwise

    Examples:
        >>> guess_mime_type("report.xlsx")
        GoogleMimeTypes.xlsx

        >>> guess_mime_type("/path/to/data.csv")
        GoogleMimeTypes.csv

        >>> guess_mime_type("document.docx")
        GoogleMimeTypes.docx

        >>> guess_mime_type("file.unknown")
        None

    Note:
        - Result is cached for performance
        - Used by Drive._upload() when from_mime_type is not specified
        - Falls back to GoogleMimeTypes.file in upload flow if this returns None

    See also:
        MIME_EXTENSIONS in utils/misc.py: Complete extension to MIME type mappings
        Drive._upload(): Uses this function for MIME type inference
    """
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
    """Get OAuth2 or Service Account credentials for Google API.

    This function supports two authentication flows:

    1. SERVICE ACCOUNT (Recommended for programmatic access):
       - For automated scripts, server applications, and domain-wide delegation
       - No user interaction required
       - Setup: https://cloud.google.com/iam/docs/service-accounts-create
       - Enable APIs: https://console.cloud.google.com/apis/library
       - Create Service Account: https://console.cloud.google.com/iam-admin/serviceaccounts
       - Download JSON key file
       - For domain-wide delegation: use creds.with_subject("user@domain.com")

       Example:
           creds = get_oauth2_creds(client_config="auth/service-account.json")
           drive = Drive(creds=creds)

           # With domain-wide delegation (Workspace only)
           creds = creds.with_subject("user@domain.com")
           drive = Drive(creds=creds)

    2. OAUTH2 CLIENT (For user authorization):
       - For applications that need user consent
       - Opens browser for user to sign in and authorize
       - Token saved for reuse (no browser needed on subsequent runs)
       - Setup: https://console.cloud.google.com/apis/credentials/oauthclient
       - Enable APIs: https://console.cloud.google.com/apis/library
       - Create OAuth 2.0 Client ID: Application type "Desktop app"
       - Configure consent screen: https://console.cloud.google.com/apis/credentials/consent
       - Download JSON file (NOT a service account key)

       Example:
           creds = get_oauth2_creds(
               client_config="auth/oauth2_credentials.json",  # OAuth Client JSON
               token_path="auth/token.pickle"  # Auto-created after authorization
           )
           drive = Drive(creds=creds)

    Auto-discovery:
        If client_config is not provided or doesn't exist:
        1. Checks ./auth/credentials.json
        2. Checks GOOGLE_API_CREDENTIALS environment variable

    Args:
        client_config: Path to client config file (service account or OAuth2 client) or dict.
        token_path: Path to save/load OAuth2 token (ignored for service accounts).
        scopes: List of OAuth scopes. See: https://developers.google.com/identity/protocols/oauth2/scopes
        *args: Additional arguments for credential creation.
        **kwargs: Additional keyword arguments for credential creation.

    Returns:
        ServiceAccountCredentials if service account JSON provided.
        Credentials (OAuth2) if OAuth2 client JSON provided.

    Raises:
        Exception: If OAuth2 flow used but no token_path provided.
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
                try:
                    creds.refresh(Request())
                except Exception as e:
                    creds = None
                    print(f"Error refreshing credentials: {e}")

        if creds is None:
            flow = InstalledAppFlow.from_client_config(client_config, scopes=scopes, *args, **kwargs)
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

    get_adjacent = lambda x: (paths[t_ix] if x in paths and (t_ix := paths.index(x) + 1) < len(paths) else None)

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
