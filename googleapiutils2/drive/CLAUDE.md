# drive/

Google Drive API wrapper: file operations, permissions, recursive upload/download.

## File Tree

```
drive/
├── __init__.py          # Exports Drive, Permissions
├── drive.py             # Drive class (upload, download, copy, list, etc.)
└── misc.py              # Constants, pagination helpers, enums
```

## Key Classes

### Drive (drive.py)
Inherits `DriveBase` for caching, throttling, retry.

**Public Methods:**
- `get(file_id, fields)` - Get file metadata
- `get_if_exists(file_id)` - Get file or None
- `list(query, parents, fields)` - List files (generator)
- `create(name, mime_type, parents, recursive)` - Create file/folder
- `upload(filepath, name, to_mime_type, parents, update)` - Upload file/folder/DataFrame
- `download(file_id, filepath, mime_type, recursive)` - Download file/folder
- `copy(file_id, to_filename, to_folder_id)` - Copy file
- `update(file_id, content, metadata)` - Update file
- `delete(file_id)` - Delete file
- `export(file_id, mime_type)` - Export Google format to standard
- `sync(local_dir, remote_dir)` - Sync local ↔ remote
- `empty_trash()` - Empty trash
- `about_get()` - Get account info

**Features:**
- Recursive folder operations
- MD5 checksum for skip-if-unchanged
- MIME type auto-detection
- DataFrame upload to Sheets
- Markdown ↔ Google Docs conversion

### Permissions (drive.py)
Wrapper for Drive permissions API.

**Methods:**
- `get(file_id, permission_id)` - Get permission
- `list(file_id)` - List permissions
- `create(file_id, email, role, type)` - Add permission
- `update(file_id, permission_id, role)` - Update permission
- `delete(file_id, permission_id)` - Remove permission

**Roles:** `owner`, `organizer`, `fileOrganizer`, `writer`, `commenter`, `reader`

## Key Functions

### list_drive_items (misc.py)
```python
def list_drive_items(list_func: Callable) -> Generator[Any, None, None]:
    """Paginate through Drive API responses using nextPageToken."""
```

### create_listing_fields (misc.py)
```python
def create_listing_fields(fields: str) -> str:
    """Ensure pagination fields (nextPageToken, kind) in field mask."""
```

## Constants

### API Version
- `VERSION = "v3"` - Drive API version

### Download Threshold
- `DOWNLOAD_LIMIT = 4 * 10**6` - 4MB threshold for chunked downloads

### Defaults
- `DEFAULT_FIELDS = "*"` - Return all fields
- `team_drives = True` - Include Shared Drives by default

### DataFrameExportFileTypes (misc.py)
```python
class DataFrameExportFileTypes(str, Enum):
    csv = "csv"
    xlsx = "xlsx"
    json = "json"
    sheets = "sheets"  # Upload to Google Sheets
```

## Usage Examples

### Upload
```python
from googleapiutils2 import Drive, GoogleMimeTypes

drive = Drive()

# File
drive.upload(
    filepath="data.csv",
    name="Dataset",
    to_mime_type=GoogleMimeTypes.sheets,
    parents=["folder_id"],
    update=True  # Update if exists
)

# Folder (recursive)
drive.upload("./local_folder", recursive=True, update=True)

# DataFrame to Sheets
import pandas as pd
df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
drive.upload(df, name="Data", to_mime_type=GoogleMimeTypes.sheets)

# Markdown to Google Docs
drive.upload("README.md", to_mime_type=GoogleMimeTypes.docs)
```

### Download
```python
# File with MIME conversion
drive.download("file_id", "./output.pdf", mime_type=GoogleMimeTypes.pdf)

# Folder (recursive)
drive.download("folder_id", "./local_folder", recursive=True)

# Google Docs to markdown
drive.download("doc_id", "./output.md", mime_type=GoogleMimeTypes.markdown)
```

### List & Search
```python
# All files
for file in drive.list():
    print(f"{file['name']}: {file['id']}")

# Query
for file in drive.list(query="name contains 'report'"):
    print(file)

# In folder
for file in drive.list(parents=["folder_id"]):
    print(file)

# Custom fields
for file in drive.list(fields="files(id,name,mimeType,modifiedTime)"):
    print(file)
```

### Create
```python
# File
file = drive.create(
    name="New Document",
    mime_type=GoogleMimeTypes.docs
)

# Nested folders
drive.create(
    name="Projects/2024/Q4",
    mime_type=GoogleMimeTypes.folder,
    recursive=True
)
```

### Copy
```python
copied = drive.copy(
    file_id="source_id",
    to_filename="Copy of Document",
    to_folder_id="destination_folder_id"
)
```

### Update
```python
# Content
drive.update(
    file_id="file_id",
    content='{"new": "data"}',
    from_mime_type=GoogleMimeTypes.json
)

# Metadata
drive.update(
    file_id="file_id",
    metadata={"name": "Renamed", "starred": True}
)
```

### Permissions
```python
from googleapiutils2 import Permissions

perms = Permissions(drive=drive)

# Share with user
perms.create(
    file_id="file_id",
    email="user@example.com",
    role="reader",
    type="user"
)

# Make public
perms.create(
    file_id="file_id",
    role="reader",
    type="anyone"
)

# List
for perm in perms.list("file_id"):
    print(perm['emailAddress'], perm['role'])

# Remove
perms.delete("file_id", permission_id="perm_id")
```

### Sync
```python
# Sync local directory to Drive
drive.sync(
    local_dir="./data",
    remote_dir="My Drive/Backups"
)
```

## Patterns

### MIME Type Handling
```python
# Auto-detection on upload
drive.upload("file.docx")  # Infers GoogleMimeTypes.docx

# Explicit conversion
drive.upload("file.csv", to_mime_type=GoogleMimeTypes.sheets)

# Download with conversion
drive.download("sheets_id", "./out.xlsx", mime_type=GoogleMimeTypes.xlsx)
```

### Recursive Operations
```python
# Upload entire folder structure
drive.upload("./project", recursive=True)

# Download folder hierarchy
drive.download("folder_id", "./local", recursive=True)
```

### Update vs Upload
```python
# Skips if MD5 matches
drive.upload("file.txt", update=True)  # No-op if unchanged

# Force re-upload
drive.upload("file.txt", update=False)  # Always uploads
```

### URL Acceptance
```python
# All these work
drive.get("1a2b3c4d5e")
drive.get("https://drive.google.com/file/d/1a2b3c4d5e/view")
drive.get("https://drive.google.com/drive/folders/1a2b3c4d5e")
```

## Internal Methods

**Drive class:**
- `_upload(filepath, ...)` - Dispatch to file/data/frame handlers
- `_upload_file(filepath, ...)` - Upload single file
- `_upload_data(data, ...)` - Upload BytesIO/string
- `_upload_frame(df, ...)` - Upload DataFrame
- `_download(file_id, ...)` - Download file
- `_download_nested_filepath(file_id, ...)` - Recursive download
- `_download_file(file, ...)` - Single file download
- `_download_data(file, ...)` - Download to BytesIO
- `_query_children(file_id)` - List folder contents
- `_create_nested_folders(name, ...)` - Create folder hierarchy
- `_team_drives_payload()` - Shared Drive parameters

**Permissions class:**
- `_permission_get_if_exists(file_id, email)` - Get permission or None
- `_sanitize_update_permission(permission)` - Remove read-only fields

## Dependencies

**External:**
- `google-api-python-client` - DriveResource, FilesResource, PermissionsResource
- `pandas` - DataFrame operations

**Internal:**
- `googleapiutils2.utils.DriveBase` - Base class
- `googleapiutils2.utils.GoogleMimeTypes` - MIME type enum
- `googleapiutils2.utils.parse_file_id` - URL → ID
- `googleapiutils2.utils.download_large_file` - Streaming download
- `googleapiutils2.utils.export_mime_type` - Format conversion

## Public API

**Exported from `__init__.py`:**
- `Drive`
- `Permissions`

**TYPE_CHECKING only:**
- `DriveList`, `DriveResource`, `File`, `FileList`, `Permission`, `PermissionList`
