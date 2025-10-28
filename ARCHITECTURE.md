# googleapiutils2 Architecture Analysis

## Executive Summary

googleapiutils2 is a well-architected Python library (~6,800 lines) providing unified wrappers for Google APIs (Drive, Sheets, Gmail, Admin, Groups, Geocoding). The codebase demonstrates strong architectural patterns with clear separation of concerns, consistent inheritance hierarchies, robust error handling, and sophisticated request management.

---

## 1. Inheritance Hierarchy & Base Classes

### DriveBase: The Foundation
**Location:** `googleapiutils2/utils/drive.py`

`DriveBase` is the root class that all API wrappers inherit from (except Geocode). It provides:

- **Credential Management**
  - Supports both ServiceAccount and OAuth2 credentials via `get_oauth2_creds()`
  - Auto-discovery: checks `./auth/credentials.json` or `GOOGLE_API_CREDENTIALS` env var
  - Automatic credential refreshing for OAuth2 tokens

- **Request Execution & Throttling**
  - `execute()`: Primary method with retry decorator (10 retries, 30s delay)
  - `execute_no_retry()`: For operations that shouldn't retry
  - `execute_queue()`: Async queueing via `DriveThread`
  - Two throttlers: `_execute_throttler` (0.1s) and `_execute_queue_throttler` (1s)

- **TTL Caching**
  - `_cache: TTLCache` (128 items, 80s TTL)
  - Used via `@cachedmethod` decorator throughout

- **Background Request Queueing**
  - `DriveThread` class manages async request execution
  - Daemon thread monitors main thread; gracefully shuts down queued requests
  - Handles transient network errors and rate limiting

### API Class Hierarchy
```
DriveBase
├── Drive              (googleapiutils2/drive/drive.py)
├── Sheets             (googleapiutils2/sheets/sheets.py)
├── Mail               (googleapiutils2/mail/mail.py)
├── Admin              (googleapiutils2/admin/admin.py)
└── Groups             (googleapiutils2/groups/groups.py)

Standalone:
├── Geocode            (googleapiutils2/geocode/geocode.py) - Does NOT inherit DriveBase
├── Permissions        (googleapiutils2/drive/drive.py) - Wrapper for Drive.permissions
├── ResourceMonitor    (googleapiutils2/monitor.py) - Abstract base for monitors
├── DriveMonitor       (googleapiutils2/monitor.py) - Extends ResourceMonitor
└── SheetsMonitor      (googleapiutils2/monitor.py) - Extends ResourceMonitor
```

---

## 2. Common Patterns & Decorators

### A. Retry Decorator (Exponential Backoff)
**Location:** `googleapiutils2/utils/decorators.py`

```python
@retry(
    retries=10,
    delay=30.0,
    exponential_backoff=False,
    on_exception=on_http_exception,
)
def execute(self, request):
    # Handles HTTP 429, socket errors (48, 49, 54, 61), 
    # connection errors, timeouts
```

- **Applied to:** `DriveBase.execute()` method
- **Behavior:** Logs retries, uses random jitter, supports both sync/async
- **Custom exception handlers:** Can define which exceptions trigger retry

### B. TTL Caching Pattern
**Location:** `googleapiutils2/utils/decorators.py`

Two cache mechanisms:

1. **In-Memory TTL Cache** (via cachetools)
   ```python
   @cachedmethod(operator.attrgetter("_cache"), key=named_methodkey("method_name"))
   def cached_method(self, ...):
   ```
   - Used in: `Groups.get()`, `Sheets._get_sheet_id()`, `Drive` internal methods
   - 80-second TTL by default

2. **File-Based Cache** (for longer-lived results)
   ```python
   @cache_with_stale_interval(datetime.timedelta(hours=1))
   def expensive_function(...):
   ```
   - Uses pickle + JSON metadata
   - Stored in `/tmp/{hash}/`
   - Used less frequently, available for custom use

### C. Throttling Pattern
**Location:** `googleapiutils2/utils/utils.py` - `Throttler` class

```python
class Throttler:
    def __init__(self, throttle_time: float = THROTTLE_TIME):
    def dt(self) -> float:          # Time until next request allowed
    def throttle(self) -> float:    # Sleep if needed, reset timer
```

- **Execute throttler:** 0.1s between individual API calls
- **Queue throttler:** 1s for batch operations
- Prevents rate limiting and API quota exhaustion

### D. Named Method Key Pattern
**Location:** `googleapiutils2/utils/utils.py`

```python
def named_methodkey(name: str):
    def _key(self, *args, **kwargs):
        return (name, *list(args), *list(kwargs.values()))
    return _key
```

Used for cache keys in: `Groups.get()`, `Sheets` methods
- Allows caching methods on instance without storing `self`
- Ensures consistent cache keys regardless of argument order

---

## 3. Error Handling Strategy

### Custom Exception Hierarchy
**Location:** `googleapiutils2/utils/drive.py`

```
GoogleAPIException (base)
├── InvalidRequestError      (400-type errors)
├── OverQueryLimitError      (429 rate limiting)
├── RequestDeniedError       (403 permission errors)
├── NotFoundError            (404 file not found)
└── UnknownError             (generic failures)
```

### Automatic Exception Handling
- `raise_for_status()`: Maps Google API status strings to exceptions
- Used in: Geocode API, error responses
- Enables programmatic error handling: `except NotFoundError:`

### Transient Error Detection
**Location:** `googleapiutils2/utils/drive.py` - `on_http_exception()`

```python
def on_http_exception(e: Exception) -> bool:
    # Retries on:
    # - HTTP 429 (rate limiting)
    # - Socket errors: 48 (EADDRINUSE), 49 (EADDRNOTAVAIL), 
    #                  54 (ECONNRESET), 61 (ECONNREFUSED)
    # - ConnectionError, TimeoutError, socket.timeout
```

---

## 4. Codebase Organization & Module Structure

### Directory Layout
```
googleapiutils2/
├── utils/
│   ├── __init__.py          # Public API exports
│   ├── decorators.py        # retry, cache_with_stale_interval
│   ├── drive.py             # DriveBase, get_oauth2_creds, parse_file_id
│   ├── misc.py              # GoogleMimeTypes enum, constants, type defs
│   └── utils.py             # Throttler, hex_to_rgb, URL manipulation
├── drive/
│   ├── __init__.py          # Exports Drive, Permissions
│   ├── drive.py             # Drive class (1223 lines)
│   └── misc.py              # Helper enums, create_listing_fields()
├── sheets/
│   ├── __init__.py          # Exports Sheets, SheetsValueRange, SheetSlice
│   ├── sheets.py            # Sheets class
│   ├── sheets_value_range.py
│   ├── sheets_slice.py
│   └── misc.py
├── mail/
│   ├── __init__.py
│   └── mail.py              # Mail (Gmail wrapper)
├── admin/
│   ├── __init__.py
│   └── admin.py             # Admin (Google Workspace Admin SDK)
├── groups/
│   ├── __init__.py
│   └── groups.py            # Groups (Google Groups)
├── geocode/
│   ├── __init__.py
│   └── geocode.py           # Geocode (Maps Geocoding - standalone)
├── monitor.py               # DriveMonitor, SheetsMonitor
└── __init__.py              # Public package exports
```

### Public API (via __init__.py)
**Location:** `googleapiutils2/__init__.py`

```python
from .admin import *                    # Admin
from .drive import *                    # Drive, Permissions
from .geocode import *                  # Geocode
from .groups import *                   # Groups
from .mail import *                     # Mail
from .monitor import DriveMonitor, SheetsMonitor
from .sheets import *                   # Sheets, SheetsValueRange, SheetSlice
from .utils import (                    # Utility exports
    GoogleMimeTypes,
    ServiceAccountCredentials,
    cache_with_stale_interval,
    get_oauth2_creds,
    parse_file_id,
    retry,
)
```

---

## 5. TYPE_CHECKING Blocks (Circular Import Prevention)

Pattern used throughout for lazy imports:

```python
if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import (
        DriveResource,
        File,
        Permission,
    )
```

**Benefits:**
- Avoids circular imports at runtime
- Provides full type hints for IDEs
- Lightweight runtime (no extra imports)

**Applied to:**
- All Google API resource types (`File`, `Message`, `User`, `Sheet`, etc.)
- Used in: `Drive`, `Sheets`, `Mail`, `Admin`, `Groups`, `Geocode`

---

## 6. Specific Architectural Highlights

### A. Drive Class (1223 lines)
**Location:** `googleapiutils2/drive/drive.py`

**Key Design Patterns:**
- **Overloaded Methods:** Single `upload()`, `download()` methods handle multiple input types
  ```python
  def upload(self, filepath: FilePath | pd.DataFrame | BytesIO, ...)
  def download(self, filepath: FilePath | BytesIO, ...)
  ```

- **Internal Method Variants:** `_upload_file()`, `_upload_data()`, `_upload_frame()` handle specifics
  - Cleaner public API while maintaining implementation separation

- **Polymorphic Behavior:**
  - `_download()`: Direct file download
  - `_download_nested_filepath()`: Recursive folder download
  - Smart file extension handling and MIME type conversion

- **Caching Strategy:**
  - MD5 checksum comparison to avoid redundant uploads
  - Checks if file already exists before operations

### B. Sheets Class
**Location:** `googleapiutils2/sheets/sheets.py`

**Features:**
- **SheetsValueRange:** Dataclass for range operations
  ```python
  sheet_range = SheetsValueRange(sheets, spreadsheet_id, "Sheet1")
  ```

- **Sheet Slicing Support:** Python-like indexing
  ```python
  sheet[1:5, "A":"C"].read()
  sheet[1, "A"].update([["Value"]])
  ```

- **Batch Operations:** Auto-batching with configurable throttling
  ```python
  sheets.batch_update(spreadsheet_id, {...})
  sheets.batch_update_remaining_auto()  # atexit handler
  ```

- **DataFrame Integration:**
  ```python
  df = sheet[...].to_frame()
  sheets.from_frame(df, include_header=True)
  ```

### C. Monitoring Pattern
**Location:** `googleapiutils2/monitor.py`

**Architecture:**
- Abstract `ResourceMonitor` base class
- Concrete implementations: `DriveMonitor`, `SheetsMonitor`
- Revision-based change detection (efficient polling)
- Callback mechanism for change notifications

```python
class ResourceMonitor(ABC):
    @abstractmethod
    def _get_current_state(self) -> MonitoredResource:
        """Get resource state with revision ID"""
    
    @abstractmethod
    def _get_current_data(self) -> Any:
        """Get actual resource data"""
    
    def _has_changed(self, current, prev) -> bool:
        """Compare states"""
```

### D. Geocode Class (Standalone)
**Location:** `googleapiutils2/geocode/geocode.py`

- **Does NOT inherit DriveBase** (intentional)
- Simple, focused API for Maps Geocoding
- Direct HTTP requests via `requests` library
- Minimal state management

---

## 7. Constants & Configuration

### Location: `googleapiutils2/utils/misc.py`

**API Configuration:**
- `EXECUTE_TIME = 0.1` - Delay between individual API calls
- `THROTTLE_TIME = 1` - Delay for batch/queue operations
- `DEFAULT_TIMEOUT = 8 * 60` - Socket timeout (8 minutes)

**OAuth Configuration:**
- `TOKEN_PATH = "auth/token.pickle"` - Auto-save location for tokens
- `CONFIG_PATH = "auth/credentials.json"` - Auto-discovery path
- `CONFIG_ENV_VAR = "GOOGLE_API_CREDENTIALS"` - Env var fallback

**API Scopes:**
```python
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    # ... Gmail, Admin, Groups scopes
]
```

### MIME Type Management
**GoogleMimeTypes Enum:**
- 20+ Google Workspace formats (docs, sheets, slides, etc.)
- 20+ standard formats (csv, xlsx, pdf, docx, etc.)
- MIME_EXTENSIONS mapping for file type inference
- DEFAULT_DOWNLOAD_CONVERSION_MAP for format conversion

```python
GoogleMimeTypes.sheets → xlsx (download conversion)
GoogleMimeTypes.docs → docx (download conversion)
GoogleMimeTypes.slides → pdf (download conversion)
```

---

## 8. Testing Architecture

**Location:** `test/` directory with subdirectories per module

**Patterns:**
- Session-scoped fixtures for API client instances
- Shared authentication via `conftest.py`
- Real Google API integration (not mocked)
- Automatic cleanup of test resources

```python
@pytest.fixture(scope="session", autouse=True)
def drive(creds):
    return Drive(creds=creds)

# Fixtures create test folders, then delete after all tests
```

---

## 9. Key Separation of Concerns

### By Module
| Module | Responsibility | Key Classes |
|--------|-----------------|------------|
| `utils/` | Core infrastructure | DriveBase, Throttler, decorators, auth |
| `drive/` | File operations | Drive, Permissions |
| `sheets/` | Spreadsheet ops | Sheets, SheetsValueRange, SheetSlice |
| `mail/` | Gmail | Mail |
| `admin/` | Workspace admin | Admin |
| `groups/` | Google Groups | Groups |
| `geocode/` | Maps geocoding | Geocode |
| `monitor/` | Change detection | ResourceMonitor, DriveMonitor, SheetsMonitor |

### By Responsibility
- **Authentication:** `get_oauth2_creds()` (utils/drive.py)
- **Request execution:** `DriveBase.execute()`, retry decorator
- **Caching:** TTL cache, file cache
- **Throttling:** Throttler class, two-level throttling
- **Error handling:** Custom exception hierarchy, `raise_for_status()`
- **Pagination:** `list_drive_items()` helper
- **Type hints:** TYPE_CHECKING blocks, comprehensive type annotations

---

## 10. Patterns to Preserve

### Must Keep
1. **DriveBase inheritance** - Provides unified throttling, caching, retry logic
2. **Two-level throttling** - Prevents API quota exhaustion
3. **Custom exception hierarchy** - Enables programmatic error handling
4. **TYPE_CHECKING pattern** - Avoids circular imports
5. **Cache invalidation on updates** - Prevents stale data
6. **Overloaded public methods** - Clean user-facing API
7. **Background request queueing** - `DriveThread` for async operations
8. **Credential auto-discovery** - Reduces boilerplate

### Optional Extensions
1. **Additional monitoring patterns** - More abstract resource monitors
2. **Custom caching backends** - Beyond TTL cache
3. **Metrics/logging hooks** - For production monitoring
4. **Batch operation builders** - More sophisticated request batching

---

## 11. Performance Characteristics

### Caching
- 80-second TTL on all DriveBase methods
- Reduces redundant API calls for frequently accessed data
- File-based persistent cache available (pickle-based)

### Throttling
- 0.1s between individual API calls
- 1s between batch operations
- Prevents 429 (Too Many Requests) errors
- Configurable via constructor parameters

### Retry Strategy
- 10 retries with exponential backoff (up to 30 seconds)
- Automatic detection of transient vs. permanent errors
- Network resilience for unstable connections

### Request Queueing
- Background thread processes API calls asynchronously
- Daemon thread ensures graceful shutdown
- Useful for high-throughput scenarios

---

## 12. Code Quality Observations

### Strengths
- Comprehensive type hints (py.typed included)
- Consistent naming conventions
- Well-documented methods with docstrings
- Proper use of standard library (enum, dataclass, abc)
- Minimal external dependencies (google-api-python-client, pandas, cachetools, loguru)

### Architectural Strengths
- Single responsibility principle (modules by service)
- Dependency injection (credentials passed to constructors)
- Abstract base classes where appropriate
- Lazy imports via TYPE_CHECKING
- Clear public API via __init__.py exports

---

## Summary Table

| Aspect | Implementation | Location |
|--------|---|---|
| **Base class** | DriveBase | utils/drive.py |
| **Retry logic** | @retry decorator | utils/decorators.py |
| **Caching** | TTL cache + file cache | utils/decorators.py |
| **Throttling** | Throttler class | utils/utils.py |
| **Error handling** | Custom exceptions | utils/drive.py |
| **Authentication** | get_oauth2_creds() | utils/drive.py |
| **API wrappers** | Drive, Sheets, Mail, Admin, Groups | drive/, sheets/, mail/, admin/, groups/ |
| **Monitoring** | ResourceMonitor abstract class | monitor.py |
| **Type hints** | TYPE_CHECKING blocks | All modules |
| **Public API** | Curated exports | __init__.py files |

