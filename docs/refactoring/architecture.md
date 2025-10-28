# googleapiutils2 Refactoring Architecture

**Status:** Specification
**Date:** 2025-10-22
**Objective:** Decompose monolithic class files into modular, functional architecture while preserving public API

---

## Executive Summary

This refactoring transforms googleapiutils2 from monolithic class files (2,162 LOC max) into a modular, functional architecture optimized for:

- **AI consumption:** Smaller files (<300 LOC), clear naming, single responsibility
- **Developer experience:** Easy navigation, reduced merge conflicts, testable pure functions
- **Maintainability:** Add features without modifying existing files, clear domain boundaries

**Total Impact:** 4,396 LOC → ~2,900 LOC across ~25 focused modules (avg ~115 LOC per file)

**Zero Breaking Changes:** Public API signatures remain identical

---

## Core Principles

### 1. Hybrid Functional Decomposition

**Pattern:**
- **Main class:** Thin coordinator managing state, authentication, caching, throttling
- **Operations modules:** Pure functions with explicit parameters, single responsibility
- **Public methods:** Delegate to functional operations

**Not Applied:**
- Service classes remain class-based (encapsulation needed for stateful resources)
- Helper/utility classes unchanged

### 2. Coarse-Grained Modules (Not Fine-Grained)

**GOOD:** `values.py` contains all value operations (read, write, batch, process)
**BAD:** `values_read.py`, `values_write.py`, `values_batch.py` (too granular)

**Guideline:** Group by domain/feature, not by operation type

### 3. Preserve Critical Patterns

✅ **DriveBase inheritance** - All main classes still inherit
✅ **@cachedmethod decorators** - Stay on main class methods
✅ **@retry decorator** - Applied to public methods
✅ **TYPE_CHECKING blocks** - In `types.py` or inline if minimal
✅ **Custom exceptions** - Unchanged
✅ **Authentication flow** - Managed by main class
✅ **Throttling** - Coordinated by main class instance

---

## Standard Module Template

```
module_name/
├── __init__.py                    # Public API exports (unchanged)
├── module_name.py                 # Main class - thin coordinator (~200-400 LOC)
├── types.py                       # TYPE_CHECKING imports (only if substantial)
├── operations/
│   ├── __init__.py
│   ├── domain1.py                # Pure functions for domain 1 (~150-250 LOC)
│   ├── domain2.py                # Pure functions for domain 2 (~150-250 LOC)
│   └── ...                       # 3-6 total operation files
└── misc.py                        # Constants, enums (unchanged)
```

**Main Class Responsibilities:**
- Instance state (`service`, `creds`, cache, throttlers)
- Public method signatures (delegates to operations)
- Decorator application (@cachedmethod, @retry)
- Authentication context management

**Operation Module Responsibilities:**
- Pure business logic (minimal side effects)
- Explicit parameters (no instance state access)
- Comprehensive type hints
- Single domain focus

---

## Module Inventory

| Module | Current LOC | Target LOC | Operation Files | Avg LOC |
|--------|-------------|------------|-----------------|---------|
| **Sheets** | 2,162 | ~1,100 | 6 files | ~180 |
| **Drive** | 1,274 | ~700 | 4 files | ~175 |
| **Permissions** | 158 (in Drive) | ~120 | 1 file | ~120 |
| **Admin** | 380 | ~280 | 1 file | ~280 |
| **Mail** | 358 | ~260 | 2 files | ~130 |
| **Groups** | 222 | ~180 | 2 files | ~90 |
| **Geocode** | 35 | 35 | 0 (unchanged) | - |
| **DriveBase** | ~400 | ~400 | 0 (unchanged) | - |
| **Monitor** | ~200 | ~200 | 0 (unchanged) | - |

**Total:** 4,396 LOC → ~2,895 LOC distributed across ~25 files

---

## Refactored Module Structures

### 1. Sheets Module

**Before:** `sheets.py` (2,162 LOC - monolithic)

**After:**
```
sheets/
├── __init__.py                    # Exports: Sheets, SheetsValueRange, SheetSlice
├── sheets.py                      # Sheets class (~400 LOC)
├── types.py                       # TYPE_CHECKING imports
├── operations/
│   ├── __init__.py
│   ├── spreadsheet.py            # Spreadsheet ops: create, get, copy, batch_update (~150 LOC)
│   ├── sheet.py                  # Sheet ops: add, delete, rename, has, get (~120 LOC)
│   ├── metadata.py               # Metadata: header, shape, id, cache management (~100 LOC)
│   ├── values.py                 # All value ops: read, write, batch, process, chunk (~350 LOC)
│   ├── formatting.py             # Formatting: format, get_format, create_format (~200 LOC)
│   └── dimensions.py             # Dimensions: resize, freeze, clear (~120 LOC)
├── sheets_value_range.py         # SheetsValueRange (unchanged)
├── sheets_slice.py               # SheetSlice (unchanged)
└── misc.py                       # Enums, constants (unchanged)
```

**Total:** 6 operation files, avg ~173 LOC per file

---

### 2. Drive Module

**Before:** `drive.py` (1,274 LOC - Drive + Permissions classes)

**After:**
```
drive/
├── __init__.py                    # Exports: Drive, Permissions
├── drive.py                       # Drive class (~300 LOC)
├── types.py                       # TYPE_CHECKING imports
├── operations/
│   ├── __init__.py
│   ├── files.py                  # File ops: get, create, update, delete, list, copy (~200 LOC)
│   ├── transfer.py               # Transfer: upload, download (all variants) (~350 LOC)
│   ├── sync.py                   # Sync: bidirectional sync (~80 LOC)
│   └── export.py                 # Export: export, trash, about (~70 LOC)
├── permissions/
│   ├── __init__.py
│   ├── permissions.py            # Permissions class (~80 LOC)
│   └── operations.py             # Permission ops: CRUD (~80 LOC)
└── misc.py                       # Constants (unchanged)
```

**Total:** 4 operation files, avg ~175 LOC per file

---

### 3. Mail Module

**Before:** `mail.py` (358 LOC - monolithic)

**After:**
```
mail/
├── __init__.py                    # Exports: Mail
├── mail.py                        # Mail class (~120 LOC)
├── operations/
│   ├── __init__.py
│   ├── messages.py               # Message ops: send, draft, list, get, modify, trash, delete (~150 LOC)
│   └── labels.py                 # Label ops: list, get, create, delete, modify (~90 LOC)
└── misc.py                       # Constants (unchanged)
```

**Total:** 2 operation files, avg ~120 LOC per file

---

### 4. Admin Module

**Before:** `admin.py` (380 LOC - monolithic)

**After:**
```
admin/
├── __init__.py                    # Exports: Admin
├── admin.py                       # Admin class (~100 LOC)
├── operations/
│   ├── __init__.py
│   └── users.py                  # All user ops: get, list, create, delete, suspend, admin (~280 LOC)
└── misc.py                       # Constants (unchanged)
```

**Total:** 1 operation file, 280 LOC

---

### 5. Groups Module

**Before:** `groups.py` (222 LOC - monolithic)

**After:**
```
groups/
├── __init__.py                    # Exports: Groups
├── groups.py                      # Groups class (~80 LOC)
├── operations/
│   ├── __init__.py
│   ├── groups.py                 # Group ops: get, list, create, update, delete (~80 LOC)
│   └── members.py                # Member ops: list, get, insert, update, delete, has (~90 LOC)
└── misc.py                       # Constants (unchanged)
```

**Total:** 2 operation files, avg ~85 LOC per file

---

### 6. Permissions Module (Extracted)

**Before:** Inside `drive/drive.py` (158 LOC)

**After:**
```
drive/permissions/
├── __init__.py                    # Exports: Permissions
├── permissions.py                 # Permissions class (~80 LOC)
└── operations.py                  # Permission ops: get, list, create, update, delete (~80 LOC)
```

**Total:** 1 operation file, 80 LOC

---

### 7. Unchanged Modules

**No refactoring needed** (already well-sized or foundational):

- **Geocode** (35 LOC - minimal, standalone)
- **DriveBase** (~400 LOC - base class, already modular)
- **Monitor** (~200 LOC - abstract pattern, well-structured)
- **Utils** (decorators, helpers - already functional)

---

## Code Sample Pattern

### Before (Monolithic Class Method)

```python
# sheets/sheets.py (2,162 LOC total)

class Sheets(DriveBase):
    def update(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]],
        value_input_option: str = "USER_ENTERED",
        align_columns: bool = False,
        ensure_shape: bool = True,
        chunk_size_bytes: int = DEFAULT_CHUNK_SIZE_BYTES,
        keep_values: bool = False,
    ) -> UpdateValuesResponse | None:
        """Update a range of values in a spreadsheet."""
        # 50+ lines of complex logic
        if ensure_shape:
            self._ensure_sheet_shape(spreadsheet_id, {range_name: values})

        if align_columns and isinstance(values[0], dict):
            values = self._dict_to_values_align_columns(...)

        if self._needs_chunking(values, chunk_size_bytes):
            return self._update_chunked(...)

        # ... more logic

    def _dict_to_values_align_columns(self, ...):
        """Convert dict rows to aligned list format."""
        # 80+ lines of complex logic
        current_header = self.header(spreadsheet_id, sheet_name)
        # ... complex alignment logic

    def _update_chunked(self, ...):
        """Update with chunking for large data."""
        # 40+ lines of chunking logic
        for chunk in self._chunk_range(...):
            # ... chunking logic
```

### After (Modular Functional Architecture)

**Main Class (Coordinator)**

```python
# sheets/sheets.py (~400 LOC total)

from googleapiutils2.utils import DriveBase
from .operations import values, metadata

class Sheets(DriveBase):
    def update(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]],
        value_input_option: str = "USER_ENTERED",
        align_columns: bool = False,
        ensure_shape: bool = True,
        chunk_size_bytes: int = DEFAULT_CHUNK_SIZE_BYTES,
        keep_values: bool = False,
    ) -> UpdateValuesResponse | None:
        """Update a range of values in a spreadsheet (delegates to operation)."""
        return values.update_values(
            service=self.service,
            spreadsheet_id=spreadsheet_id,
            range_name=range_name,
            values=values,
            value_input_option=value_input_option,
            align_columns=align_columns,
            ensure_shape=ensure_shape,
            chunk_size_bytes=chunk_size_bytes,
            keep_values=keep_values,
            # Pass instance methods for callbacks
            get_header=lambda: self.header(spreadsheet_id, sheet_slice.sheet_name),
            ensure_shape_fn=lambda ranges: self._ensure_sheet_shape(spreadsheet_id, ranges),
        )
```

**Pure Function (Testable, Atomic)**

```python
# sheets/operations/values.py (~350 LOC total)

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import SheetsResource

def update_values(
    service: "SheetsResource",
    spreadsheet_id: str,
    range_name: str,
    values: list[list[Any]] | list[dict],
    value_input_option: str = "USER_ENTERED",
    align_columns: bool = False,
    ensure_shape: bool = True,
    chunk_size_bytes: int = DEFAULT_CHUNK_SIZE_BYTES,
    keep_values: bool = False,
    get_header: Callable[[], list[str]] | None = None,
    ensure_shape_fn: Callable[[dict], None] | None = None,
) -> dict | None:
    """Pure function: Update a range of values in a spreadsheet.

    Args:
        service: Google Sheets API service
        spreadsheet_id: Target spreadsheet ID
        range_name: A1 notation range
        values: 2D list or list of dicts
        value_input_option: How to interpret values (USER_ENTERED or RAW)
        align_columns: If True and values are dicts, align columns with existing header
        ensure_shape: If True, auto-resize sheet to fit values
        chunk_size_bytes: Max chunk size for large updates (prevents timeouts)
        keep_values: If True, preserve existing values not in dict keys
        get_header: Callback to fetch current header (for column alignment)
        ensure_shape_fn: Callback to ensure sheet has required dimensions

    Returns:
        UpdateValuesResponse dict or None if no changes needed
    """
    # Ensure shape if requested
    if ensure_shape and ensure_shape_fn:
        ensure_shape_fn({range_name: values})

    # Process dict values with column alignment
    if align_columns and values and isinstance(values[0], dict):
        if not get_header:
            raise ValueError("get_header callback required for align_columns=True")

        current_header = get_header()
        values = dict_to_values_align_columns(
            current_header=current_header,
            new_rows=values,
            keep_values=keep_values,
        )

        if values is None:  # No changes needed
            return None

    # Chunk if necessary
    if needs_chunking(values, chunk_size_bytes):
        return update_chunked(
            service=service,
            spreadsheet_id=spreadsheet_id,
            range_name=range_name,
            values=values,
            value_input_option=value_input_option,
            chunk_size_bytes=chunk_size_bytes,
        )

    # Single update
    body = {"values": values}
    return service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption=value_input_option,
        body=body,
    ).execute()


def dict_to_values_align_columns(
    current_header: list[str],
    new_rows: list[dict],
    keep_values: bool = False,
) -> list[list[Any]] | None:
    """Pure function: Convert dict rows to aligned 2D list format.

    Args:
        current_header: Existing column headers
        new_rows: List of dicts to convert
        keep_values: If True, preserve existing values for unmapped columns

    Returns:
        Aligned 2D list or None if no changes needed
    """
    # Extract all keys from new rows
    new_keys = set()
    for row in new_rows:
        new_keys.update(row.keys())

    # Merge headers (existing + new columns)
    merged_header = current_header.copy()
    for key in new_keys:
        if key not in merged_header:
            merged_header.append(key)

    # Convert dicts to aligned rows
    aligned_rows = []
    for row_dict in new_rows:
        row = []
        for col in merged_header:
            row.append(row_dict.get(col, "" if not keep_values else None))
        aligned_rows.append(row)

    # Check if any changes were made
    if aligned_rows == [[""] * len(merged_header)] * len(new_rows):
        return None

    return aligned_rows


def update_chunked(
    service: "SheetsResource",
    spreadsheet_id: str,
    range_name: str,
    values: list[list[Any]],
    value_input_option: str,
    chunk_size_bytes: int,
) -> dict:
    """Pure function: Update with chunking for large datasets.

    Args:
        service: Google Sheets API service
        spreadsheet_id: Target spreadsheet
        range_name: A1 notation range
        values: 2D list of values
        value_input_option: USER_ENTERED or RAW
        chunk_size_bytes: Max bytes per chunk

    Returns:
        Combined UpdateValuesResponse
    """
    chunks = chunk_values_by_size(values, chunk_size_bytes)
    responses = []

    for chunk_start_row, chunk_values in chunks:
        # Calculate chunk range
        chunk_range = adjust_range_for_chunk(range_name, chunk_start_row)

        # Update chunk
        response = update_values(
            service=service,
            spreadsheet_id=spreadsheet_id,
            range_name=chunk_range,
            values=chunk_values,
            value_input_option=value_input_option,
            align_columns=False,  # Already aligned
            ensure_shape=False,   # Already ensured
        )
        responses.append(response)

    # Combine responses
    return combine_update_responses(responses)


def needs_chunking(values: list[list[Any]], chunk_size_bytes: int) -> bool:
    """Pure function: Check if values need chunking."""
    import sys
    total_size = sys.getsizeof(values)
    return total_size > chunk_size_bytes
```

---

## Migration Strategy

### Phase 1: Create Operations Modules (Non-Breaking)

For each module:
1. Create `operations/` subdirectory
2. Extract logic to pure functions in operation modules
3. **Keep original methods intact** (parallel implementation)
4. Add comprehensive type hints to functions

**Validation:** Existing tests still pass (unchanged code)

### Phase 2: Refactor Class Methods (Delegate)

For each module:
1. Update class methods to call operational functions
2. Preserve all decorators (@cachedmethod, @retry)
3. Maintain instance state management in class
4. Pass callbacks for stateful operations (e.g., `get_header`)

**Validation:** Existing tests still pass (same behavior)

### Phase 3: Testing & Validation

1. Run existing integration tests (should pass 100%)
2. Add unit tests for pure functions (easy to test)
3. Verify API compatibility with example scripts
4. Check type hints with mypy

### Phase 4: Cleanup & Documentation

1. Remove any duplicated code
2. Update internal imports
3. Run linting with autofix (ruff, black)
4. Update docstrings with references to operation modules

---

## Implementation Order

1. **Sheets** (highest complexity, biggest win) - 6 operation files
2. **Drive** (foundational, high impact) - 4 operation files
3. **Permissions** (extract from Drive) - 1 operation file
4. **Mail** (medium complexity) - 2 operation files
5. **Admin** (medium complexity) - 1 operation file
6. **Groups** (low complexity, good practice) - 2 operation files

**Total:** 16 operation files across 6 modules

---

## Benefits Summary

### For AI Consumption
- ✅ Files <350 LOC (vs 2,162 LOC monoliths)
- ✅ Clear, descriptive names (`values.py`, `formatting.py`)
- ✅ Single domain responsibility per file
- ✅ Pure functions easier to parse than stateful methods

### For Developers
- ✅ Easier navigation (domain-based organization)
- ✅ Reduced merge conflicts (changes isolated)
- ✅ Testable pure functions (no mocking required)
- ✅ Clear dependencies (explicit parameters)
- ✅ Add features without modifying existing files

### For Maintainability
- ✅ Refactor individual operations independently
- ✅ Clear domain boundaries (spreadsheet vs sheet vs values)
- ✅ Easier onboarding (smaller files to understand)
- ✅ Better code reuse (functions callable from multiple contexts)

---

## Testing Strategy

### Unit Tests (New)
Pure functions are trivially testable without mocking:

```python
def test_dict_to_values_align_columns():
    current_header = ["name", "age"]
    new_rows = [{"name": "Alice", "age": 30, "city": "NYC"}]

    result = dict_to_values_align_columns(current_header, new_rows)

    assert result == [["Alice", 30, "NYC"]]
```

### Integration Tests (Existing)
All existing integration tests remain unchanged and should pass:

```python
def test_sheets_update(sheets: Sheets, test_spreadsheet: str):
    sheets.update(test_spreadsheet, "A1", [["value"]])
    # ... existing test logic
```

---

## Rollout Plan

### Week 1: Sheets + Drive
- Day 1-2: Sheets refactoring (6 operation files)
- Day 3-4: Drive refactoring (4 operation files)
- Day 5: Permissions extraction (1 operation file)
- Continuous: Run tests after each module

### Week 2: Remaining Modules
- Day 1: Mail refactoring (2 operation files)
- Day 2: Admin refactoring (1 operation file)
- Day 3: Groups refactoring (2 operation files)
- Day 4-5: Cleanup, linting, documentation

**Total Time:** ~10 days (conservative estimate)

---

## Success Criteria

1. ✅ All existing tests pass (100% compatibility)
2. ✅ No breaking changes to public API
3. ✅ All files <350 LOC
4. ✅ Type hints pass mypy validation
5. ✅ Linting passes (ruff, black)
6. ✅ Code coverage maintained or improved
7. ✅ Documentation updated

---

## File Size Distribution (After Refactoring)

| File Type | Count | Avg LOC | Total LOC |
|-----------|-------|---------|-----------|
| Main classes | 6 | ~200 | ~1,200 |
| Operation files | 16 | ~140 | ~2,240 |
| Supporting files | 8 | ~100 | ~800 |
| **TOTAL** | **30** | **~140** | **~4,240** |

**Distribution:**
- Smallest: `groups/operations/groups.py` (~80 LOC)
- Largest: `sheets/operations/values.py` (~350 LOC)
- Average: ~140 LOC per file

---

## Appendix: Pattern Examples

See individual module specs:
- [`sheets.md`](./sheets.md) - Sheets module refactoring spec
- [`drive.md`](./drive.md) - Drive module refactoring spec
- [`permissions.md`](./permissions.md) - Permissions module refactoring spec
- [`mail.md`](./mail.md) - Mail module refactoring spec
- [`admin.md`](./admin.md) - Admin module refactoring spec
- [`groups.md`](./groups.md) - Groups module refactoring spec
