from __future__ import annotations

import json
import os
import pickle
import time
import urllib.parse
from collections import defaultdict
from enum import Enum
from functools import cache
from pathlib import Path
from typing import *

import googleapiclient.http
import requests
from cachetools import TTLCache
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from threading import Thread
from queue import Queue
import atexit

FilePath = str | Path

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import File
    from googleapiclient._apis.sheets.v4.resources import Color, Spreadsheet


THROTTLE_TIME = 30

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]


TOKEN_PATH = "auth/token.pickle"
CONFIG_PATH = "auth/credentials.json"
CONFIG_ENV_VAR = "GOOGLE_API_CREDENTIALS"


class GoogleMimeTypes(Enum):
    """Enum representing the MIME types used by Google Drive API.

    Each member of this enum represents a MIME type used by Google Drive API.
    These MIME types are used to identify the type of a file or folder in Google Drive.

    Attributes:
        audio (str): MIME type for audio files.
        docs (str): MIME type for Google Docs files.
        drive_sdk (str): MIME type for Google Drive SDK files.
        drawing (str): MIME type for Google Drawings files.
        file (str): MIME type for generic files.
        folder (str): MIME type for folders.
        form (str): MIME type for Google Forms files.
        fusiontable (str): MIME type for Google Fusion Tables files.
        jam (str): MIME type for Google Jamboard files.
        map (str): MIME type for Google My Maps files.
        photo (str): MIME type for Google Photos files.
        slides (str): MIME type for Google Slides files.
        script (str): MIME type for Google Apps Script files.
        shortcut (str): MIME type for Google Drive shortcut files.
        site (str): MIME type for Google Sites files.
        sheets (str): MIME type for Google Sheets files.
    """

    audio = "application/vnd.google-apps.audio"
    docs = "application/vnd.google-apps.document"
    drive_sdk = "application/vnd.google-apps.drive-sdk"
    drawing = "application/vnd.google-apps.drawing"
    file = "application/vnd.google-apps.file"
    folder = "application/vnd.google-apps.folder"
    form = "application/vnd.google-apps.form"
    fusiontable = "application/vnd.google-apps.fusiontable"
    jam = "application/vnd.google-apps.jam"
    map = "application/vnd.google-apps.map"
    photo = "application/vnd.google-apps.photo"
    slides = "application/vnd.google-apps.presentation"
    script = "application/vnd.google-apps.script"
    shortcut = "application/vnd.google-apps.shortcut"
    site = "application/vnd.google-apps.site"
    sheets = "application/vnd.google-apps.spreadsheet"
    unknown = "application/vnd.google-apps.unknown"
    video = "application/vnd.google-apps.video"

    xls = "application/vnd.ms-excel"
    xlsx = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ods = "application/vnd.oasis.opendocument.spreadsheet"
    csv = "text/csv"

    jpg = "image/jpeg"
    png = "image/png"
    svg = "image/svg+xml"
    gif = "image/gif"
    bmp = "image/bmp"

    txt = "text/plain"
    html = "text/html"
    htm = "text/html"
    xml = "text/xml"
    tmpl = "text/plain"

    doc = "application/msword"
    docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    pdf = "application/pdf"
    js = "text/js"
    swf = "application/x-shockwave-flash"
    mp3 = "audio/mpeg"
    zip = "application/zip"
    rar = "application/rar"
    tar = "application/tar"
    arj = "application/arj"
    cab = "application/cab"
    php = "application/x-httpd-php"
    json = "application/vnd.google-apps.script+json"

    default = "application/octet-stream"


MIME_EXTENSIONS: dict[GoogleMimeTypes, list[str]] = {
    GoogleMimeTypes.audio: ["mp3", "wav", "aac", "m4a", "wma", "flac"],
    GoogleMimeTypes.docs: ["doc", "docx"],
    GoogleMimeTypes.drawing: ["svg"],
    GoogleMimeTypes.file: [],
    GoogleMimeTypes.folder: [],
    GoogleMimeTypes.form: ["html"],
    GoogleMimeTypes.fusiontable: [],
    GoogleMimeTypes.jam: ["jam"],
    GoogleMimeTypes.map: [],
    GoogleMimeTypes.photo: ["jpg", "jpeg", "png", "gif", "bmp", "tif", "tiff"],
    GoogleMimeTypes.slides: ["ppt", "pptx"],
    GoogleMimeTypes.script: ["gs"],
    GoogleMimeTypes.shortcut: [],
    GoogleMimeTypes.site: ["html"],
    GoogleMimeTypes.sheets: ["csv", "xlsx", "ods", "xls"],
    GoogleMimeTypes.unknown: [],
    GoogleMimeTypes.video: ["mp4", "avi", "mov", "wmv", "flv", "mkv"],
    GoogleMimeTypes.xls: ["xls"],
    GoogleMimeTypes.xlsx: ["xlsx"],
    GoogleMimeTypes.ods: ["ods"],
    GoogleMimeTypes.csv: ["csv"],
    GoogleMimeTypes.jpg: ["jpg", "jpeg"],
    GoogleMimeTypes.png: ["png"],
    GoogleMimeTypes.svg: ["svg"],
    GoogleMimeTypes.gif: ["gif"],
    GoogleMimeTypes.bmp: ["bmp"],
    GoogleMimeTypes.txt: ["txt"],
    GoogleMimeTypes.html: ["html", "htm"],
    GoogleMimeTypes.xml: ["xml"],
    GoogleMimeTypes.tmpl: ["tmpl"],
    GoogleMimeTypes.doc: ["doc"],
    GoogleMimeTypes.docx: ["docx"],
    GoogleMimeTypes.pdf: ["pdf"],
    GoogleMimeTypes.js: ["js"],
    GoogleMimeTypes.swf: ["swf"],
    GoogleMimeTypes.mp3: ["mp3"],
    GoogleMimeTypes.zip: ["zip"],
    GoogleMimeTypes.rar: ["rar"],
    GoogleMimeTypes.tar: ["tar"],
    GoogleMimeTypes.arj: ["arj"],
    GoogleMimeTypes.cab: ["cab"],
    GoogleMimeTypes.php: ["php"],
    GoogleMimeTypes.json: ["json"],
    GoogleMimeTypes.default: [],
}


DEFAULT_DOWNLOAD_CONVERSION_MAP = {
    GoogleMimeTypes.sheets: GoogleMimeTypes.xlsx,
    GoogleMimeTypes.docs: GoogleMimeTypes.docx,
    GoogleMimeTypes.slides: GoogleMimeTypes.pdf,
}


def validate_ext_mime_type(name: str, mime_type: GoogleMimeTypes) -> bool:
    """Validates if the file name matches the expected extensions for its MIME type."""

    extension = name.split(".")[-1].lower() if "." in name else name

    extensions = MIME_EXTENSIONS.get(mime_type, [])

    return extension in extensions


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

    return t_mime_type, t_mime_type.name


class DriveBase:
    """Args:
    creds (Credentials, optional): The credentials to use. If None, the following paths will be tried:
        - ~/auth/credentials.json
        - env var: GOOGLE_API_CREDENTIALS
    throttle_time (float, optional): The time to wait between requests. Defaults to THROTTLE_TIME (30).
    """

    def __init__(self, creds: Credentials | None, throttle_time: float = THROTTLE_TIME):
        # Google Drive API service creds
        self.creds = creds if creds is not None else get_oauth2_creds()

        # throttle time in seconds; used in throttled_fn
        self.throttle_time = throttle_time
        # used to throttle calls to throttled_fn
        self._prev_time: Optional[float] = None

        # TTL cache for various functions; used by way of "@cachedmethod(operator.attrgetter("_cache"))"
        self._cache: TTLCache = TTLCache(maxsize=128, ttl=80)

        self._request_queue: Queue[googleapiclient.http.HttpRequest] = Queue()

        def _worker():
            while True:
                request = self._request_queue.get()
                self._request_queue.task_done()
                request.execute()

        self._request_thread = Thread(target=_worker, daemon=True)
        self._request_thread.start()

        atexit.register(self._request_queue.join)

    def execute(self, request: googleapiclient.http.HttpRequest) -> Any:
        self._request_queue.put(request)
        return None

    def throttle_fn(
        self,
        on_every_call: Callable[[], bool | None],
        on_final_call: Callable[[], None],
    ):
        """Throttles a function to be called at most once every throttle_time seconds.

        Args:
            on_every_call (Callable[[], bool | None]): Function that is called on every call to throttled_fn.
                If this function returns False, throttled_fn will not call on_final_call.
                If this function returns None, throttled_fn will call on_final_call.
            on_final_call (Callable[[], None]): Function that is called on the final call to throttled_fn.
        """
        can_call = on_every_call()
        can_call = can_call if can_call is not None else True

        curr_time = time.perf_counter()
        dt = (
            curr_time - self._prev_time
            if self._prev_time is not None
            else self.throttle_time
        )

        if not (dt >= self.throttle_time and can_call):
            return None

        self._prev_time = curr_time

        return on_final_call()


def named_methodkey(name: str):
    """Hash key that ignores the first argument of a method, but is named for the method."""

    def _key(self, *args, **kwargs):
        return tuple([name] + list(args) + list(kwargs.values()))

    return _key


def hex_to_rgb(hex_code: str) -> Color:
    """Converts a hex color code to RGB(A), where each value is between 0 and 1.

    Args:
        hex_code (str): Hex color code to convert. Can be 3, 4, 6, or 8 characters long (optional alpha is supported).
    """
    hex_code = hex_code.lstrip("#")

    if len(hex_code) == 3 or len(hex_code) == 4:
        hex_code = "".join([2 * c for c in hex_code])

    rgb: Color = {
        "red": int(hex_code[:2], 16),
        "green": int(hex_code[2:4], 16),
        "blue": int(hex_code[4:6], 16),
    }

    if len(hex_code) == 8:
        rgb["alpha"] = int(hex_code[6:8], 16)
    elif len(hex_code) != 6:
        raise ValueError("Invalid hex code")

    return {k: v / 255.0 for k, v in rgb.items()}  # type: ignore


def get_url_params(url: str) -> dict[str, List[str]]:
    """Get the components of the given URL."""
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)


def update_url_params(url: str, params: dict) -> str:
    """Update the query parameters of the given URL with the given params."""
    url_obj = urllib.parse.urlparse(url)
    params.update(urllib.parse.parse_qsl(url_obj.query))

    query = urllib.parse.urlencode(params)

    url_obj = urllib.parse.ParseResult(
        url_obj.scheme,
        url_obj.netloc,
        url_obj.path,
        url_obj.params,
        query,
        url_obj.fragment,
    )

    return url_obj.geturl()


def q_escape(s: str) -> str:
    s = s.replace("'", r"\'")
    return f"'{s}'"


def get_oauth2_creds(
    client_config: FilePath | dict = CONFIG_PATH,
    token_path: FilePath = TOKEN_PATH,
    scopes: List[str] = SCOPES,
) -> Credentials:
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

    token_path = Path(token_path)

    if not isinstance(client_config, dict):
        path = Path(client_config)

        if not path.exists():
            path = Path(os.environ.get(CONFIG_ENV_VAR, ""))

        if not path.exists():
            raise Exception(
                "No client config file found. Please provide a client config file path or set the GOOGLE_API_CREDENTIALS environment variable."
            )

        client_config = json.loads(path.read_bytes())

    is_service_account = client_config.get("type", "") == "service_account"  # type: ignore

    if is_service_account:
        return service_account.Credentials.from_service_account_info(
            client_config, scopes=scopes
        )  # type: ignore
    else:
        creds: Credentials = None  # type: ignore

        if token_path.exists():
            creds = pickle.loads(token_path.read_bytes())

        if creds is not None and not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())

        elif creds is None:
            flow = InstalledAppFlow.from_client_config(client_config, scopes)
            creds = flow.run_local_server(port=0)  # type: ignore
            token_path.write_bytes(pickle.dumps(creds))

        return creds  # type: ignore


def download_large_file(
    url: str,
    filepath: FilePath,
    chunk_size: int = googleapiclient.http.DEFAULT_CHUNK_SIZE,
) -> Path:
    """Download a large file from the given URL to the given filepath."""

    filepath = Path(filepath)

    with requests.get(url, stream=True) as r:
        r.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                f.write(chunk)

    return filepath


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

    get_adjacent = (
        lambda x: paths[t_ix]
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


def to_base(x: str | int, base: int, from_base: int = 10) -> list[int]:
    if isinstance(x, str):
        x = int(x, base=from_base)

    y = []
    while True:
        y.append(x % base)
        if (x := (x // base) - 1) < 0:
            break

    return y[::-1]


def nested_defaultdict(
    existing: dict | Any | None = None, **kwargs: Any
) -> dict[Any, Any]:
    if existing is None:
        existing = {}
    elif not isinstance(existing, dict):
        return existing
    existing = {key: nested_defaultdict(val) for key, val in existing.items()}
    return defaultdict(nested_defaultdict, existing, **kwargs)
