# Drive Module Refactoring Specification

**Module:** `googleapiutils2/drive/`
**Current Size:** 1,274 LOC (Drive class + Permissions class)
**Target Size:** ~700 LOC (distributed across 4 operation files)
**Complexity:** ★★★★★ (Very High)

---

## Current Structure (BEFORE)

```
drive/
├── __init__.py                    # Exports: Drive, Permissions
├── drive.py                       # 1,274 LOC - Drive class (1,066) + Permissions class (158)
└── misc.py                        # 51 LOC - Constants (unchanged)
```

**Problems:**
- Single file with 1,274 lines
- Two unrelated classes (Drive + Permissions) in same file
- Mixed concerns: file ops, upload, download, sync, permissions
- Complex upload/download variants buried together

---

## Proposed Structure (AFTER)

```
drive/
├── __init__.py                    # Exports: Drive, Permissions (unchanged)
├── drive.py                       # Drive class - thin coordinator (~300 LOC)
├── types.py                       # TYPE_CHECKING imports (~40 LOC)
├── operations/
│   ├── __init__.py
│   ├── files.py                  # File CRUD operations (~200 LOC)
│   ├── transfer.py               # Upload/download with variants (~350 LOC)
│   ├── sync.py                   # Bidirectional sync (~80 LOC)
│   └── export.py                 # Export, trash, about (~70 LOC)
├── permissions/
│   ├── __init__.py                # Export Permissions class
│   ├── permissions.py             # Permissions class (~80 LOC)
│   └── operations.py              # Permission CRUD operations (~80 LOC)
└── misc.py                        # Constants (unchanged)
```

**Benefits:**
- Drive class reduced from 1,066 → 300 LOC (72% reduction)
- Permissions extracted to own submodule
- Clear separation: files vs transfer vs sync
- Upload/download variants grouped logically

---

## Operation Module Breakdown

### 1. `operations/files.py` (~200 LOC)

**Responsibility:** Basic file operations (CRUD)

**Functions:**
- `get_file()` - Retrieve file by ID/name/path
- `get_file_if_exists()` - Safe get (returns None)
- `create_file()` - Create file or folder
- `update_file()` - Update file metadata
- `copy_file()` - Copy file
- `delete_file()` - Delete or trash file
- `list_files()` - List/query files
- `query_children()` - Query child files
- `create_nested_folders()` - Recursive folder creation

---

### 2. `operations/transfer.py` (~350 LOC)

**Responsibility:** Upload and download operations

**Functions:**
- `upload()` - Universal upload dispatcher
- `upload_file()` - Upload from filesystem
- `upload_data()` - Upload from bytes
- `upload_frame()` - Upload DataFrame
- `upload_core()` - Core upload logic with MD5 dedup
- `download()` - Universal download dispatcher
- `download_file()` - Download to filesystem
- `download_data()` - Download to BytesIO
- `download_core()` - Core download logic
- `download_nested()` - Recursive folder download

---

### 3. `operations/sync.py` (~80 LOC)

**Responsibility:** Bidirectional sync

**Functions:**
- `sync_folder()` - Sync local folder with Drive folder

---

### 4. `operations/export.py` (~70 LOC)

**Responsibility:** Export and misc operations

**Functions:**
- `export_file()` - Export to specific MIME type
- `empty_trash()` - Empty trash
- `about_get()` - Get account info

---

## Code Examples: BEFORE → AFTER

### Example 1: Upload (Dispatcher with Variants)

#### BEFORE (Monolithic)

```python
# drive/drive.py (lines 994-1274)

class Drive(DriveBase):
    def upload(
        self,
        filepath: FilePath | pd.DataFrame | bytes,
        name: str | None = None,
        file_id: str | None = None,
        to_mime_type: GoogleMimeTypes | None = None,
        parents: list[str] | str | None = None,
        owners: list[str] | str | None = None,
        recursive: bool = False,
        body: File | None = None,
        update: bool = True,
        from_mime_type: GoogleMimeTypes | None = None,
        **kwargs: Any,
    ):
        """Universal upload supporting filepath, DataFrame, or bytes."""
        # ... 50+ lines of type checking and dispatching
        if isinstance(filepath, str | Path):
            return self._upload_file(...)
        elif isinstance(filepath, pd.DataFrame):
            return self._upload_frame(...)
        else:
            return self._upload_data(...)

    def _upload_file(self, filepath, ...):
        """Upload from filesystem path."""
        # ... 100+ lines
        # - Recursive directory handling
        # - MIME type inference
        # - Calls to _upload()

    def _upload_frame(self, df, ...):
        """Upload pandas DataFrame."""
        # ... 60+ lines
        # - Export to various formats
        # - Calls to _upload_data()

    def _upload_data(self, data, ...):
        """Upload from bytes."""
        # ... 40+ lines
        # - BytesIO handling
        # - Calls to _upload()

    def _upload(self, filepath, ...):
        """Core upload logic with MD5 deduplication."""
        # ... 90+ lines
        # - MD5 comparison
        # - Create vs update decision
        # - Media upload construction
```

#### AFTER (Modular)

**Main Class:**

```python
# drive/drive.py (~300 LOC total)

from .operations import transfer as transfer_ops

class Drive(DriveBase):
    def upload(
        self,
        filepath: FilePath | pd.DataFrame | bytes,
        name: str | None = None,
        file_id: str | None = None,
        to_mime_type: GoogleMimeTypes | None = None,
        parents: list[str] | str | None = None,
        owners: list[str] | str | None = None,
        recursive: bool = False,
        body: File | None = None,
        update: bool = True,
        from_mime_type: GoogleMimeTypes | None = None,
        **kwargs: Any,
    ):
        """Universal upload (delegates to operation module)."""
        return transfer_ops.upload(
            service=self.service,
            filepath=filepath,
            name=name,
            file_id=file_id,
            to_mime_type=to_mime_type,
            parents=parents,
            owners=owners,
            recursive=recursive,
            body=body,
            update=update,
            from_mime_type=from_mime_type,
            # Pass callbacks for stateful operations
            get_file_fn=self.get,
            get_if_exists_fn=self.get_if_exists,
            create_folders_fn=lambda fp, p, o, g: self._create_nested_folders(fp, p, o, g),
            **kwargs,
        )
```

**Pure Functions:**

```python
# drive/operations/transfer.py (~350 LOC total)

from typing import TYPE_CHECKING, Callable
import pandas as pd
from pathlib import Path
from io import BytesIO

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import DriveResource, File

def upload(
    service: "DriveResource",
    filepath: str | Path | pd.DataFrame | bytes,
    name: str | None = None,
    file_id: str | None = None,
    to_mime_type: str | None = None,
    parents: list[str] | None = None,
    owners: list[str] | None = None,
    recursive: bool = False,
    body: dict | None = None,
    update: bool = True,
    from_mime_type: str | None = None,
    get_file_fn: Callable | None = None,
    get_if_exists_fn: Callable | None = None,
    create_folders_fn: Callable | None = None,
    **kwargs,
) -> dict:
    """Pure function: Universal upload dispatcher.

    Supports three input types:
    1. File path (str/Path) - uploads file from disk
    2. DataFrame - converts to format and uploads
    3. bytes - uploads raw data

    Args:
        service: Google Drive API service
        filepath: File path, DataFrame, or bytes to upload
        name: Target filename in Drive
        file_id: Existing file ID to update
        to_mime_type: Target MIME type (for conversion)
        parents: Parent folder IDs
        owners: Owner email addresses
        recursive: Recursively upload directories
        body: Additional metadata
        update: Update if exists
        from_mime_type: Source MIME type override
        get_file_fn: Callback to get existing file
        get_if_exists_fn: Callback to check existence
        create_folders_fn: Callback to create folders

    Returns:
        File dict with metadata
    """
    # Dispatch based on type
    if isinstance(filepath, (str, Path)):
        return upload_file(
            service=service,
            filepath=Path(filepath),
            name=name,
            file_id=file_id,
            to_mime_type=to_mime_type,
            parents=parents,
            owners=owners,
            recursive=recursive,
            body=body,
            update=update,
            from_mime_type=from_mime_type,
            get_if_exists_fn=get_if_exists_fn,
            create_folders_fn=create_folders_fn,
            **kwargs,
        )
    elif isinstance(filepath, pd.DataFrame):
        if name is None or to_mime_type is None:
            raise ValueError("DataFrame upload requires name and to_mime_type")
        return upload_frame(
            service=service,
            df=filepath,
            name=name,
            to_mime_type=to_mime_type,
            file_id=file_id,
            parents=parents,
            owners=owners,
            body=body,
            update=update,
            from_mime_type=from_mime_type,
            **kwargs,
        )
    else:  # bytes
        return upload_data(
            service=service,
            data=filepath,
            name=name,
            to_mime_type=to_mime_type,
            file_id=file_id,
            parents=parents,
            owners=owners,
            body=body,
            update=update,
            from_mime_type=from_mime_type,
            **kwargs,
        )


def upload_file(
    service: "DriveResource",
    filepath: Path,
    name: str | None,
    file_id: str | None,
    to_mime_type: str | None,
    parents: list[str] | None,
    owners: list[str] | None,
    recursive: bool,
    body: dict | None,
    update: bool,
    from_mime_type: str | None,
    get_if_exists_fn: Callable | None,
    create_folders_fn: Callable | None,
    **kwargs,
) -> dict:
    """Pure function: Upload file from filesystem.

    Handles:
    - Single file upload
    - Recursive directory upload
    - MIME type inference
    - Parent folder creation

    Args:
        service: Drive API service
        filepath: Local file path
        ... (other params same as upload())

    Returns:
        File dict or list of dicts if recursive
    """
    from googleapiutils2.utils import guess_mime_type, GoogleMimeTypes

    # Handle directory upload
    if filepath.is_dir():
        if not recursive:
            raise ValueError("filepath is a directory but recursive=False")

        results = []
        for child in filepath.rglob("*"):
            if child.is_file():
                result = upload_file(
                    service=service,
                    filepath=child,
                    name=child.name,
                    file_id=None,
                    to_mime_type=to_mime_type,
                    parents=parents,
                    owners=owners,
                    recursive=False,
                    body=body,
                    update=update,
                    from_mime_type=from_mime_type,
                    get_if_exists_fn=get_if_exists_fn,
                    create_folders_fn=None,
                    **kwargs,
                )
                results.append(result)
        return results

    # Infer MIME types
    name = name or filepath.name
    from_mime_type = from_mime_type or guess_mime_type(filepath)
    to_mime_type = to_mime_type or from_mime_type

    # Create parent folders if needed
    if create_folders_fn and filepath.parent != Path("."):
        parents = create_folders_fn(filepath.parent, parents, owners, True)

    # Core upload
    return upload_core(
        service=service,
        filepath=filepath,
        name=name,
        file_id=file_id,
        to_mime_type=to_mime_type,
        from_mime_type=from_mime_type,
        parents=parents,
        owners=owners,
        body=body,
        update=update,
        get_if_exists_fn=get_if_exists_fn,
        **kwargs,
    )


def upload_core(
    service: "DriveResource",
    filepath: Path | BytesIO,
    name: str,
    file_id: str | None,
    to_mime_type: str,
    from_mime_type: str,
    parents: list[str] | None,
    owners: list[str] | None,
    body: dict | None,
    update: bool,
    get_if_exists_fn: Callable | None,
    **kwargs,
) -> dict:
    """Pure function: Core upload logic with MD5 deduplication.

    Args:
        service: Drive API service
        filepath: File path or BytesIO
        name: Target filename
        file_id: Existing file ID
        to_mime_type: Target MIME type
        from_mime_type: Source MIME type
        parents: Parent folder IDs
        owners: Owner emails
        body: Additional metadata
        update: Update if exists
        get_if_exists_fn: Callback to check existence

    Returns:
        File dict
    """
    import hashlib
    import googleapiclient.http

    # Calculate MD5 for deduplication
    if isinstance(filepath, Path):
        with open(filepath, "rb") as f:
            md5 = hashlib.md5(f.read()).hexdigest()
    else:
        filepath.seek(0)
        md5 = hashlib.md5(filepath.read()).hexdigest()
        filepath.seek(0)

    # Check if file exists and MD5 matches
    if update and get_if_exists_fn:
        existing = get_if_exists_fn(name=name, parents=parents)
        if existing and existing.get("md5Checksum") == md5:
            return existing  # Skip upload - already up to date

        if existing:
            file_id = existing["id"]

    # Build metadata
    file_metadata = body or {}
    file_metadata.update({
        "name": name,
        "mimeType": to_mime_type,
    })
    if parents:
        file_metadata["parents"] = parents
    if owners:
        file_metadata["owners"] = owners

    # Build media body
    if isinstance(filepath, Path):
        media = googleapiclient.http.MediaFileUpload(
            str(filepath),
            mimetype=from_mime_type,
            resumable=True if filepath.stat().st_size > 50_000_000 else False,
        )
    else:
        media = googleapiclient.http.MediaIoBaseUpload(
            filepath,
            mimetype=from_mime_type,
            resumable=False,
        )

    # Create or update
    if file_id:
        request = service.files().update(
            fileId=file_id,
            body=file_metadata,
            media_body=media,
            **kwargs,
        )
    else:
        request = service.files().create(
            body=file_metadata,
            media_body=media,
            **kwargs,
        )

    return request.execute()


def download(
    service: "DriveResource",
    filepath: Path | BytesIO,
    file_id: str,
    mime_type: str | None,
    recursive: bool,
    overwrite: bool,
    conversion_map: dict | None,
    **kwargs,
) -> None | bytes:
    """Pure function: Universal download dispatcher."""
    if isinstance(filepath, (str, Path)):
        return download_file(
            service=service,
            filepath=Path(filepath),
            file_id=file_id,
            mime_type=mime_type,
            recursive=recursive,
            overwrite=overwrite,
            conversion_map=conversion_map,
            **kwargs,
        )
    else:
        return download_data(
            service=service,
            buffer=filepath,
            file_id=file_id,
            mime_type=mime_type,
            **kwargs,
        )


# Additional functions: upload_frame(), upload_data(), download_file(),
# download_data(), download_core(), download_nested()
# ... (~150 more LOC)
```

---

### Example 2: File Operations (CRUD)

#### BEFORE

```python
# drive/drive.py (lines 82-680)

class Drive(DriveBase):
    def get(self, file_id, name, parents, fields, q, **kwargs):
        """Get file by ID or name/parents."""
        # ... 60+ lines
        # - File ID resolution
        # - Name/parent search
        # - Hierarchical path support

    def get_if_exists(self, ...):
        """Safe get returning None."""
        try:
            return self.get(...)
        except FileNotFoundError:
            return None

    def create(self, name, mime_type, parents, owners, recursive, ...):
        """Create file or folder."""
        # ... 50+ lines
        # - Nested folder creation
        # - Duplicate checking

    def update(self, file_id, name, mime_type, body, **kwargs):
        """Update file metadata."""
        # ... 20+ lines

    def copy(self, from_file_id, parents, name, body, **kwargs):
        """Copy file."""
        # ... 20+ lines

    def delete(self, file_id, trash, **kwargs):
        """Delete or trash file."""
        # ... 15+ lines

    def list(self, parents, query, fields, order_by):
        """List files with query."""
        # ... 30+ lines
        # - Team drives support
        # - Pagination

    def _query_children(self, parents, name, fields, q):
        """Query child files."""
        # ... 30+ lines
```

#### AFTER

```python
# drive/operations/files.py (~200 LOC total)

from typing import TYPE_CHECKING, Callable
from pathlib import Path

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import DriveResource, File

def get_file(
    service: "DriveResource",
    file_id: str | None = None,
    name: str | Path | None = None,
    parents: list[str] | None = None,
    fields: str = "*",
    q: str | None = None,
    team_drives: bool = True,
    query_children_fn: Callable | None = None,
    **kwargs,
) -> dict:
    """Pure function: Get file by ID or name/parents.

    Supports hierarchical path search: name="Projects/2024/Q4/report.pdf"

    Args:
        service: Drive API service
        file_id: File ID (direct lookup)
        name: Filename or path
        parents: Parent folder IDs
        fields: Fields to return
        q: Additional query filter
        team_drives: Include Team Drives
        query_children_fn: Callback for child queries

    Returns:
        File dict

    Raises:
        FileNotFoundError: If file not found
    """
    from googleapiutils2.utils import parse_file_id

    # Direct ID lookup
    if file_id:
        file_id = parse_file_id(file_id)
        request = service.files().get(fileId=file_id, fields=fields, **kwargs)
        return request.execute()

    # Name/parent search
    if name is None:
        raise ValueError("Either file_id or name must be provided")

    # Handle hierarchical paths
    filepath = Path(name)
    if len(filepath.parts) > 1 and query_children_fn:
        # Walk path from root to target
        current_parents = parents or []
        for part in filepath.parts[:-1]:
            folders = query_children_fn(
                parents=current_parents,
                name=part,
                q=f"mimeType='application/vnd.google-apps.folder'",
            )
            folder = next(folders, None)
            if not folder:
                raise FileNotFoundError(f"Folder '{part}' not found in path")
            current_parents = [folder["id"]]

        # Get final file
        name = filepath.name
        parents = current_parents

    # Query for file
    if query_children_fn:
        files = query_children_fn(parents=parents or [], name=name, fields=fields, q=q)
        file = next(files, None)
        if file is None:
            raise FileNotFoundError(f"File '{name}' not found")
        return file

    raise ValueError("query_children_fn required for name-based lookup")


def get_file_if_exists(
    service: "DriveResource",
    get_file_fn: Callable,
    **kwargs,
) -> dict | None:
    """Pure function: Safe get returning None if not found."""
    try:
        return get_file_fn(**kwargs)
    except FileNotFoundError:
        return None


def create_file(
    service: "DriveResource",
    name: str | Path,
    mime_type: str | None = None,
    parents: list[str] | None = None,
    owners: list[str] | None = None,
    recursive: bool = False,
    get_extant: bool = False,
    fields: str = "*",
    create_folders_fn: Callable | None = None,
    get_if_exists_fn: Callable | None = None,
    **kwargs,
) -> dict:
    """Pure function: Create file or folder.

    Args:
        service: Drive API service
        name: Filename or path
        mime_type: File MIME type
        parents: Parent folder IDs
        owners: Owner emails
        recursive: Create parent folders
        get_extant: Return existing if found
        fields: Fields to return
        create_folders_fn: Callback to create folders
        get_if_exists_fn: Callback to check existence

    Returns:
        File dict
    """
    from googleapiutils2.utils import GoogleMimeTypes

    filepath = Path(name)

    # Create parent folders if recursive
    if recursive and create_folders_fn and filepath.parent != Path("."):
        parents = create_folders_fn(filepath.parent, parents or [], owners or [], get_extant)

    # Check for existing file
    if get_extant and get_if_exists_fn:
        existing = get_if_exists_fn(name=filepath.name, parents=parents)
        if existing:
            return existing

    # Build metadata
    body = {
        "name": filepath.name,
        "mimeType": mime_type or GoogleMimeTypes.file.value,
    }
    if parents:
        body["parents"] = parents
    if owners:
        body["owners"] = owners

    # Create file
    request = service.files().create(body=body, fields=fields, **kwargs)
    return request.execute()


def delete_file(
    service: "DriveResource",
    file_id: str,
    trash: bool = True,
    **kwargs,
) -> None:
    """Pure function: Delete or trash file.

    Args:
        service: Drive API service
        file_id: File ID to delete
        trash: If True, move to trash; if False, permanently delete
    """
    from googleapiutils2.utils import parse_file_id

    file_id = parse_file_id(file_id)

    if trash:
        body = {"trashed": True}
        service.files().update(fileId=file_id, body=body, **kwargs).execute()
    else:
        service.files().delete(fileId=file_id, **kwargs).execute()


def list_files(
    service: "DriveResource",
    parents: list[str] | None = None,
    query: str | None = None,
    fields: str = "*",
    order_by: str | None = None,
    team_drives: bool = True,
    query_children_fn: Callable | None = None,
) -> list[dict]:
    """Pure function: List files with query.

    Args:
        service: Drive API service
        parents: Filter by parent folders
        query: Drive query string
        fields: Fields to return
        order_by: Sort order
        team_drives: Include Team Drives
        query_children_fn: Callback for parent filtering

    Yields:
        File dicts
    """
    from googleapiutils2.drive.misc import create_listing_fields, list_drive_items

    # Use query_children if parents specified
    if parents and query_children_fn:
        yield from query_children_fn(parents=parents, fields=fields, q=query)
        return

    # Default query
    if query is None:
        query = "trashed = false"

    # Team drives support
    kwargs = {}
    if team_drives:
        kwargs.update({
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
            "corpora": "allDrives",
        })

    # Paginated list
    list_func = lambda page_token: service.files().list(
        q=query,
        pageToken=page_token,
        fields=create_listing_fields(fields),
        orderBy=order_by,
        **kwargs,
    ).execute()

    for response in list_drive_items(list_func):
        yield from response.get("files", [])


# Additional functions: query_children(), create_nested_folders(), update_file(), copy_file()
# ... (~80 more LOC)
```

---

## Migration Strategy

### Phase 1: Create Operation Modules (Day 1)
1. Create `drive/operations/` directory
2. Create `drive/types.py`
3. Extract functions to:
   - `operations/files.py`
   - `operations/transfer.py`
   - `operations/sync.py`
   - `operations/export.py`

### Phase 2: Extract Permissions (Day 2)
1. Create `drive/permissions/` directory
2. Move Permissions class to `permissions/permissions.py`
3. Extract operations to `permissions/operations.py`

### Phase 3: Refactor Drive Class (Day 3)
1. Update Drive methods to delegate
2. Preserve instance variables and decorators
3. Pass callbacks for stateful operations

### Phase 4: Testing & Cleanup (Day 4)
1. Run tests: `pytest test/drive/`
2. Add unit tests for pure functions
3. Lint and format

---

## File Size Comparison

| File | Before (LOC) | After (LOC) | Reduction |
|------|--------------|-------------|-----------|
| `drive.py` | 1,066 | ~300 | -72% |
| `operations/files.py` | - | ~200 | NEW |
| `operations/transfer.py` | - | ~350 | NEW |
| `operations/sync.py` | - | ~80 | NEW |
| `operations/export.py` | - | ~70 | NEW |
| `permissions/permissions.py` | 158 | ~80 | -49% |
| `permissions/operations.py` | - | ~80 | NEW |
| **Total** | **1,274** | **~1,160** | **-9%** |

---

## Success Criteria

1. ✅ All existing tests pass
2. ✅ Drive class <350 LOC
3. ✅ Permissions extracted to own submodule
4. ✅ All operation files <350 LOC
5. ✅ Type hints pass mypy
6. ✅ Linting passes

---

## Benefits

- **AI Consumption:** Largest file 350 LOC (was 1,274)
- **Developer Experience:** Clear file/transfer separation
- **Maintainability:** Permissions isolated from Drive
- **Testability:** Pure upload/download functions
