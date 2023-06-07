from __future__ import annotations

import json
import pickle
import urllib.parse
from collections import defaultdict
from enum import Enum
from functools import cache
from pathlib import Path
from typing import *

import googleapiclient.http
import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

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


def url_components(url: str) -> dict[str, List[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)


def update_url_params(url: str, params: dict) -> str:
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

    Args:
        client_config: Path to client config file or dict with client config.
        token_path: Path to token file.
        scopes: List of scopes. For more information on scopes, see:
            https://developers.google.com/identity/protocols/oauth2/scopes
    """

    token_path = Path(token_path)

    if not isinstance(client_config, dict):
        path = Path(client_config)
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
    url: str, filepath: FilePath, chunk_size=googleapiclient.http.DEFAULT_CHUNK_SIZE
) -> Path:
    filepath = Path(filepath)

    with requests.get(url, stream=True) as r:
        r.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                f.write(chunk)

    return filepath


def get_id_from_url(url: str) -> str:
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
        comps = url_components(url)
        if (ids := comps.get("id")) is not None:
            return ids[0]
        else:
            raise ValueError(f"Could not parse file URL of {url}")


@cache
def parse_file_id(
    file_id: str,
) -> str:
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


T = TypeVar("T")
P = ParamSpec("P")


def take_annotation_from(
    this: Callable[P, Optional[T]]
) -> Callable[[Callable], Callable[P, Optional[T]]]:
    def decorator(real_function: Callable) -> Callable[P, Optional[T]]:
        def new_function(*args: P.args, **kwargs: P.kwargs) -> Optional[T]:
            return real_function(*args, **kwargs)

        return new_function

    return decorator
