# googleapiutils2

Python wrapper for Google APIs (Drive, Sheets, Gmail, Admin, Groups, Geocoding).

## Authentication

```python
from googleapiutils2 import Drive, Sheets, get_oauth2_creds

# Auto-discovery (checks ./auth/credentials.json or GOOGLE_API_CREDENTIALS env)
drive = Drive()
sheets = Sheets()

# Explicit credentials
creds = get_oauth2_creds(client_config="path/to/credentials.json")
drive = Drive(creds=creds)

# Service account with domain delegation
creds = get_oauth2_creds(client_config="auth/service-account.json")
creds = creds.with_subject("user@domain.com")
```

## Drive

```python
from googleapiutils2 import Drive, GoogleMimeTypes

# Upload
drive.upload("file.csv", name="Data", to_mime_type=GoogleMimeTypes.sheets, parents=["folder_id"])
drive.upload("./folder", recursive=True, update=True)

# List/Search
for file in drive.list(query="name contains 'report'"):
    print(f"{file['name']}: {file['id']}")

# Download
drive.download("file_id", "./output.pdf", mime_type=GoogleMimeTypes.pdf)
drive.download("folder_id", "./local_folder", recursive=True)

# Operations
drive.copy("source_id", to_filename="Copy", to_folder_id="dest_id")
drive.delete("file_id")
drive.create(name="Projects/2024/Q4", mime_type=GoogleMimeTypes.folder, recursive=True)
```

## Sheets

```python
from googleapiutils2 import Sheets, SheetsValueRange

sheets = Sheets()
sheet_url = "https://docs.google.com/spreadsheets/d/SHEET_ID/edit"

# Create range interface
Sheet1 = SheetsValueRange(sheets, sheet_url, "Sheet1")

# Slice notation
Sheet1[1, "A"].update([["Value"]])
Sheet1[2:5, 1:3].update([[1,2,3], [4,5,6], [7,8,9]])
Sheet1[...].read()  # Read all

# Batch updates
sheets.batch_update(sheet_url, {
    Sheet1[1, ...]: [["Header 1", "Header 2"]],
    Sheet1[2:4, ...]: [["Data 1", "Data 2"], ["Data 3", "Data 4"]]
})

# DataFrame integration
df = Sheet1[...].to_frame()
Sheet1.update(sheets.from_frame(df, include_header=True))

# Formatting
sheets.format(sheet_url, Sheet1[1, ...], bold=True, background_color="#d48686")
```

## Key Classes

- **DriveBase**: Base class with throttling, caching, retry logic
- **Drive**: File operations (inherits DriveBase)
- **Sheets**: Spreadsheet operations (inherits DriveBase)
- **SheetsValueRange**: Range operations with slice notation
- **Mail**: Gmail operations
- **Admin**: Workspace user management
- **Groups**: Google Groups management
- **Geocode**: Maps geocoding API
- **SheetsMonitor/DriveMonitor**: Real-time change monitoring

## Patterns

- All API classes inherit from DriveBase (throttling, caching)
- Retry decorator with exponential backoff
- TYPE_CHECKING blocks for circular import prevention
- Session-scoped pytest fixtures for integration testing
- TTL caching (80s default) on DriveBase methods
- Background threading for request queueing

## Testing

```bash
pytest test/
```

Tests use real Google APIs with automatic cleanup.

## Error Handling

```python
from googleapiutils2 import GoogleAPIException, NotFoundError

try:
    drive.get("file_id")
except NotFoundError:
    # Handle missing file
except GoogleAPIException as e:
    # Handle other API errors
```

## Dependencies

- Python ^3.12
- google-api-python-client ^2.165.0
- pandas ^2.2.3 (for DataFrame operations)
- cachetools ^5.5.2 (TTL caching)
- loguru ^0.7.3 (logging)

## Common Tasks

**Find and update files**
```python
files = drive.list(query="name = 'config.json'")
if files:
    drive.update(files[0]['id'], content='{"new": "config"}')
```

**Monitor sheet changes**
```python
from googleapiutils2 import SheetsMonitor

def on_change(data, monitor):
    print(f"Sheet updated: {len(data)} rows")

monitor = SheetsMonitor(sheets, drive, sheet_url, on_change, interval=30)
monitor.start()
```

**Bulk permissions**
```python
from googleapiutils2 import Permissions

perms = Permissions(drive)
perms.create("file_id", "user@example.com", "reader")
```