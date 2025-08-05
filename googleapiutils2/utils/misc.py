from __future__ import annotations

from enum import Enum
from pathlib import Path

FilePath = str | Path

DEFAULT_TIMEOUT = 8 * 60  # 8 minutes

EXECUTE_TIME = 0.1

THROTTLE_TIME = 1


SCOPES = [
    # Google Drive API
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
    # Google Sheets API
    "https://www.googleapis.com/auth/spreadsheets",
    # Gmail
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    # Google Cloud platform:
    "https://www.googleapis.com/auth/cloud-platform",
    # Google Admin SDK API
    "https://www.googleapis.com/auth/admin.directory.user",
    "https://www.googleapis.com/auth/admin.directory.user.security",
    "https://www.googleapis.com/auth/admin.directory.domain",
    # Google Groups Settings API
    "https://www.googleapis.com/auth/admin.directory.group",
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
    xlsm = "application/vnd.ms-excel.sheet.macroenabled.12"
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
    xml = "text/xml"
    md = "text/markdown"

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
    GoogleMimeTypes.docs: ["doc", "docx", "rtf", "txt", "html"],
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
    GoogleMimeTypes.txt: ["txt", "md"],
    GoogleMimeTypes.html: ["html", "htm"],
    GoogleMimeTypes.md: ["md"],
    GoogleMimeTypes.xml: ["xml"],
    GoogleMimeTypes.doc: ["doc", "docx", "rtf", "txt", "html"],
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

GOOGLE_MIME_TYPES = [
    GoogleMimeTypes.audio,
    GoogleMimeTypes.docs,
    GoogleMimeTypes.drawing,
    GoogleMimeTypes.file,
    GoogleMimeTypes.folder,
    GoogleMimeTypes.sheets,
]
