# googleapiutils2

Python wrapper for Google APIs: Drive, Sheets, Gmail, Admin, Groups, Geocoding.

## Installation

### via pip
```bash
pip install googleapiutils2
```

### via uv
```bash
uv add googleapiutils2
```

Requires Python ^3.12

## Overview

googleapiutils2 provides a unified, Pythonic interface for Google APIs with built-in:
- **Automatic retry** - 10 retries with exponential backoff
- **TTL caching** - 80s cache on frequently accessed data
- **Request throttling** - Rate limiting to prevent quota exhaustion
- **Type hints** - Full IDE support via google-api-stubs
- **URL support** - Accept file/sheet IDs or URLs interchangeably

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

# Slice notation (NumPy-like)
Sheet1[1, "A"].update([["Value"]])
Sheet1[2:5, 1:3].update([[1,2,3], [4,5,6], [7,8,9]])
data = Sheet1[...].read()

# Batch updates
sheets.batch_update(sheet_url, {
    Sheet1[1, ...]: [["Header 1", "Header 2"]],
    Sheet1[2:4, ...]: [[1, 2], [3, 4]]
})

# DataFrame integration
import pandas as pd
df = Sheet1[...].to_frame()
Sheet1.update(sheets.from_frame(df, include_header=True))

# Formatting
sheets.format(sheet_url, Sheet1[1, ...], bold=True, background_color="#d48686")
```

### Mail
```python
from googleapiutils2 import Mail

mail = Mail()

# Send email
mail.send(
    sender="me@example.com",
    to="user@example.com",
    subject="Test",
    body="Hello"
)

# List messages
for msg in mail.list_messages(query="from:user@example.com after:2024/01/01"):
    print(msg['id'], msg['snippet'])
```

### Admin (Workspace)
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

# List users
for user in admin.list_users(query="givenName:John"):
    print(user['primaryEmail'])
```

### Groups
```python
from googleapiutils2 import Groups

groups = Groups()

# Create group
group = groups.create(
    email="team@domain.com",
    name="Engineering",
    description="All engineers"
)

# Add members
groups.members_insert("team@domain.com", "user@domain.com")
for member in groups.members_list("team@domain.com"):
    print(member['email'], member['role'])
```

### Geocode
```python
from googleapiutils2 import Geocode

geocoder = Geocode(api_key="YOUR_API_KEY")

# Address to coordinates
results = geocoder.geocode("1600 Amphitheatre Parkway, Mountain View, CA")
print(results[0]['geometry']['location'])  # {'lat': 37.422, 'lng': -122.084}

# Coordinates to address
results = geocoder.reverse_geocode(lat=37.422, long=-122.084)
```

### Monitor (Change Detection)
```python
from googleapiutils2 import SheetsMonitor

def on_change(data, monitor):
    print(f"Sheet updated: {len(data)} rows")

monitor = SheetsMonitor(sheets, drive, sheet_url, on_change, interval=30)
monitor.start()
```

## Authentication

Two authentication methods supported:

### Service Account (Recommended for automation)

**When to use:**
- Automated scripts and server applications
- No user interaction needed
- Domain-wide delegation (Workspace only)

**Setup:**
1. Enable APIs: https://console.cloud.google.com/apis/library
2. Create Service Account: https://console.cloud.google.com/iam-admin/serviceaccounts
3. Download JSON key file

**Usage:**
```python
from googleapiutils2 import Drive, get_oauth2_creds

# Basic service account
creds = get_oauth2_creds(client_config="auth/service-account.json")
drive = Drive(creds=creds)

# With domain-wide delegation (Workspace only)
creds = get_oauth2_creds(client_config="auth/service-account.json")
creds = creds.with_subject("user@domain.com")  # Impersonate user
drive = Drive(creds=creds)
```

### OAuth2 Client (For user authorization)

**When to use:**
- Desktop applications
- User consent required
- Personal Google accounts

**Setup:**
1. Enable APIs: https://console.cloud.google.com/apis/library
2. Create OAuth Client: https://console.cloud.google.com/apis/credentials/oauthclient (Desktop app)
3. Configure consent screen: https://console.cloud.google.com/apis/credentials/consent

**Usage:**
```python
# First run: opens browser for authorization
# Token saved to auth/token.pickle for reuse
creds = get_oauth2_creds(
    client_config="auth/oauth2_credentials.json",
    token_path="auth/token.pickle"
)
drive = Drive(creds=creds)
```

### Auto-discovery

```python
# Auto-discovery checks ./auth/credentials.json or GOOGLE_API_CREDENTIALS env var
drive = Drive()
sheets = Sheets()
```

## Features

### Drive

**Upload:**
- Files, folders (recursive)
- DataFrames to Google Sheets
- Markdown ↔ Google Docs conversion
- MD5 checksum for skip-if-unchanged

**Download:**
- Files, folders (recursive)
- Format conversion (Sheets → xlsx, Docs → docx, etc.)
- Chunked downloads for large files

**Operations:**
- `get`, `list`, `create`, `copy`, `update`, `delete`
- `sync` - Sync local ↔ remote directories
- `empty_trash` - Empty trash
- Permissions management

### Sheets

**Slice Notation:**
```python
Sheet[1, "A"]           # Single cell
Sheet[2:5, 1:3]         # Range
Sheet[1, ...]           # Entire row
Sheet[..., "A"]         # Entire column
Sheet[-1, -1]           # Last cell
Sheet["A1:B2"]          # A1 notation
```

**Operations:**
- CRUD: create, read, update, delete, append, clear
- Formatting: bold, colors, alignment, wrap, freeze
- Batch updates with auto-chunking
- Column alignment for dict data
- Auto-resize on overflow

**DataFrame Integration:**
```python
df = Sheet1[...].to_frame()
Sheet1.update(sheets.from_frame(df, include_header=True))
```

### Mail

**Messages:**
- Send (plain text, HTML)
- Create drafts
- List, get, modify, trash, delete

**Labels:**
- List, create, delete, modify
- Apply/remove labels from messages

### Admin (Workspace)

**User Management:**
- Create, update, delete users
- Suspend/unsuspend accounts
- Password management
- Admin role management
- Search by name, email, org unit

### Groups

**Group Operations:**
- Create, update, delete groups
- List groups by domain/customer/user

**Member Operations:**
- Add, remove, update members
- List members
- Check membership
- Role management (OWNER, MANAGER, MEMBER)

### Geocode

**Operations:**
- Forward geocoding (address → coordinates)
- Reverse geocoding (coordinates → address)
- Address component parsing
- Location type (ROOFTOP, RANGE_INTERPOLATED, etc.)

## Architecture

**Base Class:** `DriveBase` - All API classes inherit (except Geocode)
- TTL caching (80s, 128 entries)
- Retry decorator (10 retries, 30s delay, exponential backoff)
- Throttling (0.1s individual, 1s batch)
- Background request queueing

**Exception Hierarchy:**
```python
GoogleAPIException
├── InvalidRequestError
├── OverQueryLimitError
├── RequestDeniedError
├── NotFoundError
└── UnknownError
```

**Key Patterns:**
- TYPE_CHECKING blocks for circular import prevention
- Generator pattern for pagination
- MIME type auto-detection and conversion
- MD5 checksum caching
- Slice notation for Sheets (NumPy-like)

## File Structure

```
googleapiutils2/
├── utils/           # Core: DriveBase, auth, caching, retry, MIME types
├── drive/           # Google Drive API
├── sheets/          # Google Sheets API
├── mail/            # Gmail API
├── admin/           # Workspace Admin API
├── groups/          # Google Groups API
├── geocode/         # Maps Geocoding API
└── monitor.py       # Change detection (DriveMonitor, SheetsMonitor)
```

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

## Documentation

- **Project Overview:** [CLAUDE.md](CLAUDE.md)
- **Utils Module:** [googleapiutils2/utils/CLAUDE.md](googleapiutils2/utils/CLAUDE.md)
- **Drive Module:** [googleapiutils2/drive/CLAUDE.md](googleapiutils2/drive/CLAUDE.md)
- **Sheets Module:** [googleapiutils2/sheets/CLAUDE.md](googleapiutils2/sheets/CLAUDE.md)
- **Mail Module:** [googleapiutils2/mail/CLAUDE.md](googleapiutils2/mail/CLAUDE.md)
- **Admin Module:** [googleapiutils2/admin/CLAUDE.md](googleapiutils2/admin/CLAUDE.md)
- **Groups Module:** [googleapiutils2/groups/CLAUDE.md](googleapiutils2/groups/CLAUDE.md)
- **Geocode Module:** [googleapiutils2/geocode/CLAUDE.md](googleapiutils2/geocode/CLAUDE.md)

## Examples

See [examples/](examples/) for more usage patterns:
- `drive_upload.py` - File/folder uploads
- `sheets_crud.py` - Sheet operations and formatting
- `mail.py` - Email sending
- `monitor.py` - Change detection
- And more...

## License

MIT

## Repository

https://github.com/mkbabb/googleapiutils2
