from ..utils import GoogleMimeTypes

VERSION = "v3"

DOWNLOAD_LIMIT = 4 * 10**6

DEFAULT_DOWNLOAD_CONVERSION_MAP = {
    GoogleMimeTypes.sheets: (GoogleMimeTypes.xlsx, ".xlsx"),
    GoogleMimeTypes.docs: (GoogleMimeTypes.doc, ".docx"),
    GoogleMimeTypes.slides: (GoogleMimeTypes.pdf, ".pdf"),
}
