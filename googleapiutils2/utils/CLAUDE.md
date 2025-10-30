# utils/

Core infrastructure for googleapiutils2: authentication, base classes, caching, throttling, retry logic, MIME types.

## File Tree

```
utils/
├── __init__.py          # Public exports
├── drive.py             # DriveBase, DriveThread, auth, exceptions, MIME utils
├── decorators.py        # retry, cache_with_stale_interval
├── misc.py              # GoogleMimeTypes, SCOPES, constants, type aliases
└── utils.py             # Throttler, hex_to_rgb, URL parsing, data structures
```

## Key Classes

### DriveBase (drive.py)
Base class for all API wrappers (Drive, Sheets, Mail, Admin, Groups).

**Provides:**
- Credential management (OAuth2, Service Account)
- Request execution with retry
- TTL caching (80s, 128 entries)
- Throttling (0.1s individual, 1s batch)
- Background request queueing

**Methods:**
- `execute(request)` - Execute with retry decorator
- `execute_no_retry(request)` - Execute without retry
- `execute_queue(request)` - Queue for background execution

### DriveThread (drive.py)
Background thread for async request execution.

**Features:**
- Worker thread processes queued requests
- Monitor thread for graceful shutdown
- Daemon threads (auto-cleanup)

### Throttler (utils.py)
Rate limiter with configurable delay.

**Methods:**
- `throttle()` - Sleep if needed, reset timer
- `dt()` - Time until next request allowed
- `reset()` - Reset timer

### GoogleMimeTypes (misc.py)
Enum of Google Drive MIME types.

**Native formats:** sheets, docs, slides, forms, drawing, script, folder, shortcut, etc.
**Standard formats:** xlsx, csv, pdf, docx, jpg, png, zip, etc.

## Key Functions

### Authentication
- `get_oauth2_creds(client_config, token_path)` - Load OAuth2/Service Account creds
- `load_client_config(config)` - Parse config from file/dict/env

### MIME Types
- `export_mime_type(mime_type, conversion_map)` - Get export format + extension
- `mime_type_to_google_mime_type(mime_type)` - String → GoogleMimeTypes enum
- `guess_mime_type(filepath)` - Infer MIME from file extension

### URL/ID Parsing
- `parse_file_id(file_id)` - Extract ID from URL/string/dict
- `get_id_from_url(url)` - Extract ID from Drive/Sheets URLs
- `get_url_params(url)` - Parse query parameters
- `update_url_params(url, params)` - Merge params into URL

### Error Handling
- `raise_for_status(status)` - Raise typed exceptions from status strings
- `on_http_exception(e)` - Retry predicate for transient errors (HTTP 429, socket errors)

### Utilities
- `hex_to_rgb(hex_color)` - Hex → RGB dict (0-1 scale)
- `nested_defaultdict()` - Recursive defaultdict
- `deep_update(d, u)` - Deep merge dicts
- `download_large_file(url, filepath)` - Streaming download
- `named_methodkey(name)` - Cache key generator

## Decorators

### retry (decorators.py)
```python
@retry(retries=10, delay=30.0, exponential_backoff=False, on_exception=predicate)
def function():
    ...
```

**Features:**
- Configurable retries, delay, backoff
- Custom exception predicate
- Random jitter
- Logging

**Used on:** `DriveBase.execute()`

### cache_with_stale_interval (decorators.py)
```python
@cache_with_stale_interval(timedelta(hours=1))
def expensive_function(...):
    ...
```

**Features:**
- File-based persistent cache (pickle)
- Staleness checking
- MD5 hash of normalized inputs
- Stored in `/tmp/{hash}/`

## Constants

### Timeouts (misc.py)
- `DEFAULT_TIMEOUT = 480` - Socket timeout (8 min)
- `EXECUTE_TIME = 0.1` - Request throttle (100ms)
- `THROTTLE_TIME = 1` - Batch throttle (1s)

### Paths (misc.py)
- `TOKEN_PATH = "auth/token.pickle"` - OAuth2 token cache
- `CONFIG_PATH = "auth/credentials.json"` - Default config location
- `CONFIG_ENV_VAR = "GOOGLE_API_CREDENTIALS"` - Env var for config

### SCOPES (misc.py)
```python
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/admin.directory.user",
    "https://www.googleapis.com/auth/admin.directory.group",
    # ...
]
```

### MIME Conversions (misc.py)
```python
DEFAULT_DOWNLOAD_CONVERSION_MAP = {
    GoogleMimeTypes.sheets: GoogleMimeTypes.xlsx,
    GoogleMimeTypes.docs: GoogleMimeTypes.docx,
    GoogleMimeTypes.slides: GoogleMimeTypes.pdf,
    # ...
}
```

## Exceptions

```python
GoogleAPIException (base)
├── InvalidRequestError      # 400-type errors
├── OverQueryLimitError      # 429 rate limiting
├── RequestDeniedError       # 403 permission errors
├── NotFoundError            # 404 file not found
└── UnknownError             # Generic failures
```

**Usage:**
```python
from googleapiutils2 import NotFoundError, GoogleAPIException

try:
    drive.get("file_id")
except NotFoundError:
    # Handle missing file
except GoogleAPIException as e:
    # Handle other API errors
```

## Patterns

### DriveBase Inheritance
```python
from googleapiutils2.utils import DriveBase

class MyAPI(DriveBase):
    def __init__(self, creds=None, **kwargs):
        super().__init__(creds=creds, **kwargs)
        # Custom initialization
```

**Inherits:**
- TTL cache (80s)
- Retry logic (10 retries)
- Throttling (0.1s/1s)
- Request queueing

### Caching Strategy
```python
# In-memory TTL cache
from cachetools import cachedmethod
from operator import attrgetter
from googleapiutils2.utils import named_methodkey

class MyClass(DriveBase):
    @cachedmethod(operator.attrgetter("_cache"), key=named_methodkey("get"))
    def get(self, file_id):
        return self.execute(request)
```

### Retry on Transient Errors
```python
@retry(retries=10, delay=30.0, on_exception=on_http_exception)
def execute(self, request):
    return request.execute()
```

**Retries on:**
- HTTP 429 (TOO_MANY_REQUESTS)
- Socket errors (48, 49, 54, 61)
- ConnectionError, TimeoutError

## Public API

**Exported from `__init__.py`:**

```python
# Decorators
cache_with_stale_interval, retry

# Core
DriveBase, DriveThread, ServiceAccountCredentials
get_oauth2_creds, parse_file_id, q_escape
export_mime_type, guess_mime_type, mime_type_to_google_mime_type
on_http_exception, raise_for_status

# Constants
GoogleMimeTypes, SCOPES, DEFAULT_DOWNLOAD_CONVERSION_MAP
EXECUTE_TIME, THROTTLE_TIME, FilePath

# Utils
Throttler, deep_update, download_large_file, hex_to_rgb
named_methodkey, nested_defaultdict, to_base, update_url_params
```

## Usage Examples

### Custom API Wrapper
```python
from googleapiutils2.utils import DriveBase

class CustomAPI(DriveBase):
    def __init__(self, creds=None, **kwargs):
        super().__init__(creds=creds, **kwargs)
        self.service = build("custom", "v1", credentials=self.creds)

    def get_resource(self, resource_id):
        request = self.service.resources().get(id=resource_id)
        return self.execute(request)  # Automatic retry, caching, throttling
```

### Authentication
```python
from googleapiutils2 import get_oauth2_creds

# Service Account
creds = get_oauth2_creds(client_config="auth/service-account.json")

# OAuth2 Client
creds = get_oauth2_creds(
    client_config="auth/oauth2.json",
    token_path="auth/token.pickle"
)

# Auto-discovery
creds = get_oauth2_creds()  # Checks ./auth/credentials.json or env
```

### MIME Type Handling
```python
from googleapiutils2 import GoogleMimeTypes, guess_mime_type, export_mime_type

# Guess from extension
mime = guess_mime_type("document.docx")  # GoogleMimeTypes.docx

# Export format
format, ext = export_mime_type(GoogleMimeTypes.sheets)
# (GoogleMimeTypes.xlsx, ".xlsx")
```
