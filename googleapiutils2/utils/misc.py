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
    """Enum representing MIME types for Google Drive API.

    This enum contains both Google Workspace native formats and standard file formats.
    Understanding MIME type conversions is essential for upload/download operations.

    ## Google Workspace Native Formats (Cloud-native, not directly downloadable)

    These formats exist only in Google's cloud and require conversion for download:
        docs: Google Docs (word processing)
        sheets: Google Sheets (spreadsheets)
        slides: Google Slides (presentations)
        forms: Google Forms
        drawing: Google Drawings
        script: Google Apps Script
        site: Google Sites
        jam: Google Jamboard
        map: Google My Maps

    ## Upload Conversions (file → Google native format)

    When uploading with to_mime_type, files are converted to Google native formats:
        .csv, .xlsx, .xls, .ods → GoogleMimeTypes.sheets (Google Sheets)
        .doc, .docx, .txt, .html → GoogleMimeTypes.docs (Google Docs)
        .ppt, .pptx → GoogleMimeTypes.slides (Google Slides)

    Example:
        drive.upload("data.csv", to_mime_type=GoogleMimeTypes.sheets)
        # Uploads CSV and converts to Google Sheets

    ## Download Conversions (Google native → standard format)

    Google native formats are automatically converted using DEFAULT_DOWNLOAD_CONVERSION_MAP:
        GoogleMimeTypes.sheets → xlsx (Excel format)
        GoogleMimeTypes.docs → docx (Word format)
        GoogleMimeTypes.slides → pdf (PDF format)

    Example:
        drive.download("file_id", "output.xlsx")
        # Google Sheets automatically exported as .xlsx

    ## Standard File Formats (Direct storage, no conversion needed)

    Spreadsheets:
        xlsx: Excel 2007+ format
        xls: Excel 97-2003 format
        xlsm: Excel macro-enabled format
        ods: OpenDocument Spreadsheet
        csv: Comma-separated values

    Documents:
        docx: Word 2007+ format
        doc: Word 97-2003 format
        pdf: Portable Document Format
        txt: Plain text
        html: HTML document
        md: Markdown
        xml: XML document

    Images:
        jpg: JPEG image
        png: PNG image
        svg: SVG vector image
        gif: GIF image
        bmp: Bitmap image

    Media:
        audio: Audio files (mp3, wav, aac, etc.)
        video: Video files (mp4, avi, mov, etc.)
        mp3: MP3 audio

    Archives:
        zip: ZIP archive
        rar: RAR archive
        tar: TAR archive

    Other:
        folder: Google Drive folder
        shortcut: Google Drive shortcut
        file: Generic file type
        json: JSON data
        js: JavaScript
        php: PHP script
        default: Unknown/binary file (application/octet-stream)

    ## MIME Type Inference

    When from_mime_type or to_mime_type are not specified:
    1. Inferred from file extension using MIME_EXTENSIONS mapping
    2. Falls back to GoogleMimeTypes.file if unknown
    3. For updates, uses existing file's MIME type if to_mime_type is None

    See also:
        MIME_EXTENSIONS: Maps MIME types to file extensions
        DEFAULT_DOWNLOAD_CONVERSION_MAP: Defines native format export conversions
    """

    # Google Workspace Native Formats
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

    # Spreadsheet Formats
    xls = "application/vnd.ms-excel"
    xlsm = "application/vnd.ms-excel.sheet.macroenabled.12"
    xlsx = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ods = "application/vnd.oasis.opendocument.spreadsheet"
    csv = "text/csv"

    # Image Formats
    jpg = "image/jpeg"
    png = "image/png"
    svg = "image/svg+xml"
    gif = "image/gif"
    bmp = "image/bmp"

    # Document Formats
    txt = "text/plain"
    html = "text/html"
    xml = "text/xml"
    md = "text/markdown"
    doc = "application/msword"
    docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    pdf = "application/pdf"

    # Other Formats
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


"""
Maps GoogleMimeTypes to their corresponding file extensions.

This mapping is used for:
1. MIME type inference from file extensions during upload
2. File extension assignment during download
3. File type validation

When uploading a file without explicit from_mime_type, the extension is used
to infer the MIME type. Multiple extensions can map to the same MIME type.

Example:
    File "data.csv" → inferred as GoogleMimeTypes.csv
    File "report.docx" → inferred as GoogleMimeTypes.docx

When a Google native format (sheets, docs, slides) is uploaded with to_mime_type,
these extensions indicate which source files can be converted:
    sheets: Accepts csv, xlsx, ods, xls
    docs: Accepts doc, docx, rtf, txt, html
    slides: Accepts ppt, pptx

See also:
    guess_mime_type() in utils/drive.py: Uses this mapping for inference
"""
MIME_EXTENSIONS: dict[GoogleMimeTypes, list[str]] = {
    # Google Workspace formats and their convertible source extensions
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
    # Standard file formats
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


"""
Default conversion map for downloading Google Workspace native formats.

Google Workspace native formats (sheets, docs, slides) exist only in the cloud
and cannot be downloaded directly. This map defines the export format used when
downloading these files.

Conversions:
    sheets → xlsx: Google Sheets exported as Excel 2007+ format (.xlsx)
    docs → docx: Google Docs exported as Word 2007+ format (.docx)
    slides → pdf: Google Slides exported as PDF format (.pdf)

This map is used by the download() function's conversion_map parameter.
You can provide a custom conversion map to export to different formats:

Example - Custom conversion map:
    custom_map = {
        GoogleMimeTypes.sheets: GoogleMimeTypes.csv,  # Export as CSV instead
        GoogleMimeTypes.docs: GoogleMimeTypes.pdf,     # Export as PDF instead
    }
    drive.download(file_id, "output", conversion_map=custom_map)

Available export formats:
    Google Sheets can export to: xlsx, ods, csv, pdf, html
    Google Docs can export to: docx, pdf, html, txt
    Google Slides can export to: pdf, pptx, txt

The conversion happens via Google's export API. File extensions are automatically
assigned based on the export format using export_mime_type() in utils/drive.py.

See also:
    Drive.download(): Uses this map for automatic format conversion
    export_mime_type() in utils/drive.py: Determines export format and extension
    Google Drive Export documentation: https://developers.google.com/drive/api/v3/ref-export-formats
"""
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
