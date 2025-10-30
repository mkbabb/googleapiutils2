# googleapiutils2

Python wrapper for Google APIs: Drive, Sheets, Gmail, Admin, Groups, Geocoding.

## Installation

```bash
pip install googleapiutils2
```

Requires Python ^3.12

## File Tree

```
googleapiutils2/
├── __init__.py              # Package exports
├── monitor.py               # DriveMonitor, SheetsMonitor (change detection)
├── utils/                   # Core infrastructure
│   ├── __init__.py          # Utils exports
│   ├── drive.py             # DriveBase, auth, exceptions, MIME utils
│   ├── decorators.py        # retry, cache_with_stale_interval
│   ├── misc.py              # GoogleMimeTypes, SCOPES, constants
│   └── utils.py             # Throttler, hex_to_rgb, URL parsing
├── drive/                   # Google Drive API
│   ├── __init__.py          # Drive, Permissions exports
│   ├── drive.py             # Drive class (upload, download, copy, list, etc.)
│   └── misc.py              # Constants, pagination helpers
├── sheets/                  # Google Sheets API
│   ├── __init__.py          # Sheets, SheetsValueRange, SheetSlice exports
│   ├── sheets.py            # Sheets class (CRUD, formatting, batching)
│   ├── sheets_value_range.py  # Range wrapper with slice notation
│   ├── sheets_slice.py      # Slice indexing implementation
│   └── misc.py              # A1 notation, enums, constants
├── mail/                    # Gmail API
│   ├── __init__.py          # Mail export
│   └── mail.py              # Mail class (send, draft, labels, messages)
├── admin/                   # Google Workspace Admin API
│   ├── __init__.py          # Admin export
│   └── admin.py             # Admin class (user management)
├── groups/                  # Google Groups API
│   ├── __init__.py          # Groups export
│   ├── groups.py            # Groups class (group/member management)
│   └── misc.py              # Constants
└── geocode/                 # Google Maps Geocoding API
    ├── __init__.py          # Geocode export
    ├── geocode.py           # Geocode class (address ↔ coordinates)
    └── misc.py              # TypedDicts, LocationType enum

test/                        # Integration tests (live API)
├── conftest.py              # Shared fixtures
├── drive/                   # Drive tests
├── sheets/                  # Sheets tests
└── geocode/                 # Geocode tests

examples/                    # Usage examples
├── drive_upload.py          # Upload files/folders
├── sheets_crud.py           # Sheet operations
├── mail.py                  # Send emails
├── monitor.py               # Change detection
└── ...
```

## Authentication

Two methods supported:

### Service Account (automation)
```python
from googleapiutils2 import Drive, get_oauth2_creds

# Basic
creds = get_oauth2_creds(client_config="auth/service-account.json")
drive = Drive(creds=creds)

# Domain-wide delegation (Workspace only)
creds = get_oauth2_creds(client_config="auth/service-account.json")
creds = creds.with_subject("user@domain.com")
drive = Drive(creds=creds)
```

**Setup:** https://console.cloud.google.com/iam-admin/serviceaccounts

### OAuth2 Client (user consent)
```python
# First run: browser auth, saves token to auth/token.pickle
creds = get_oauth2_creds(
    client_config="auth/oauth2_credentials.json",
    token_path="auth/token.pickle"
)
drive = Drive(creds=creds)
```

**Setup:** https://console.cloud.google.com/apis/credentials/oauthclient (Desktop app)

### Auto-discovery
```python
# Checks ./auth/credentials.json or GOOGLE_API_CREDENTIALS env var
drive = Drive()
sheets = Sheets()
```

## Quick Start

### Drive
```python
from googleapiutils2 import Drive, GoogleMimeTypes

drive = Drive()

# Upload
drive.upload("file.csv", to_mime_type=GoogleMimeTypes.sheets, parents=["folder_id"])
drive.upload("./folder", recursive=True, update=True)

# List
for file in drive.list(query="name contains 'report'"):
    print(f"{file['name']}: {file['id']}")

# Download
drive.download("file_id", "./output.pdf", mime_type=GoogleMimeTypes.pdf)
drive.download("folder_id", "./local_folder", recursive=True)
```

### Sheets
```python
from googleapiutils2 import Sheets, SheetsValueRange

sheets = Sheets()
Sheet1 = SheetsValueRange(sheets, sheet_url, "Sheet1")

# Slice notation
Sheet1[1, "A"].update([["Value"]])
Sheet1[2:5, 1:3].update([[1,2,3], [4,5,6], [7,8,9]])
data = Sheet1[...].read()

# Batch
sheets.batch_update(sheet_url, {
    Sheet1[1, ...]: [["Header 1", "Header 2"]],
    Sheet1[2:4, ...]: [[1, 2], [3, 4]]
})

# DataFrame
df = Sheet1[...].to_frame()
Sheet1.update(sheets.from_frame(df, include_header=True))

# Format
sheets.format(sheet_url, Sheet1[1, ...], bold=True, background_color="#d48686")
```

### Mail
```python
from googleapiutils2 import Mail

mail = Mail()

# Send
mail.send(
    sender="me@example.com",
    to="user@example.com",
    subject="Test",
    body="Hello"
)

# List
for msg in mail.list_messages(query="from:user@example.com after:2024/01/01"):
    print(msg['id'], msg['snippet'])
```

### Admin
```python
from googleapiutils2 import Admin

admin = Admin()

# Create user
user = admin.create_user(
    primary_email="test@domain.com",
    given_name="Test",
    family_name="User",
    password="temp123"
)

# List
for user in admin.list_users(query="givenName:John"):
    print(user['primaryEmail'])
```

### Groups
```python
from googleapiutils2 import Groups

groups = Groups()

# Create
group = groups.create(
    email="team@domain.com",
    name="Engineering",
    description="All engineers"
)

# Members
groups.members_insert("team@domain.com", "user@domain.com")
for member in groups.members_list("team@domain.com"):
    print(member['email'], member['role'])
```

### Geocode
```python
from googleapiutils2 import Geocode

geocoder = Geocode(api_key="YOUR_API_KEY")

# Forward
results = geocoder.geocode("1600 Amphitheatre Parkway, Mountain View, CA")
print(results[0]['geometry']['location'])  # {'lat': 37.422, 'lng': -122.084}

# Reverse
results = geocoder.reverse_geocode(lat=37.422, long=-122.084)
```

### Monitor
```python
from googleapiutils2 import SheetsMonitor

def on_change(data, monitor):
    print(f"Sheet updated: {len(data)} rows")

monitor = SheetsMonitor(sheets, drive, sheet_url, on_change, interval=30)
monitor.start()
```

## Architecture

**Base Class:** `DriveBase` - All API classes inherit (except Geocode)
- TTL caching (80s, 128 entries)
- Retry decorator (10 retries, 30s delay, exponential backoff)
- Throttling (0.1s individual requests, 1s batch operations)
- Background request queueing via `DriveThread`

**Exception Hierarchy:**
- `GoogleAPIException` (base)
  - `InvalidRequestError`
  - `OverQueryLimitError`
  - `RequestDeniedError`
  - `NotFoundError`
  - `UnknownError`

**Key Patterns:**
- TYPE_CHECKING blocks: Circular import prevention
- TTL caching: `@cachedmethod` on DriveBase
- Pagination: Generator pattern via `list_drive_items()`
- MIME conversion: Auto-detect upload, auto-export download
- Slice notation: NumPy-like indexing for Sheets

## Module Details

- **utils/**: See [googleapiutils2/utils/CLAUDE.md](googleapiutils2/utils/CLAUDE.md)
- **drive/**: See [googleapiutils2/drive/CLAUDE.md](googleapiutils2/drive/CLAUDE.md)
- **sheets/**: See [googleapiutils2/sheets/CLAUDE.md](googleapiutils2/sheets/CLAUDE.md)
- **mail/**: See [googleapiutils2/mail/CLAUDE.md](googleapiutils2/mail/CLAUDE.md)
- **admin/**: See [googleapiutils2/admin/CLAUDE.md](googleapiutils2/admin/CLAUDE.md)
- **groups/**: See [googleapiutils2/groups/CLAUDE.md](googleapiutils2/groups/CLAUDE.md)
- **geocode/**: See [googleapiutils2/geocode/CLAUDE.md](googleapiutils2/geocode/CLAUDE.md)

## Dependencies

- google-api-python-client ^2.168.0
- google-auth ^2.39.0
- google-auth-oauthlib ^1.2.1
- pandas ^2.2.3
- cachetools ^5.5.2
- loguru ^0.7.3
- requests ^2.32.3

## Testing

```bash
pytest test/
```

Tests use real Google APIs with session-scoped fixtures and automatic cleanup.
