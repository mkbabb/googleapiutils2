# sheets/

Google Sheets API wrapper: CRUD operations, slice notation, formatting, batch updates, DataFrame integration.

## File Tree

```
sheets/
├── __init__.py              # Exports Sheets, SheetsValueRange, SheetSlice, etc.
├── sheets.py                # Sheets class (CRUD, formatting, batching)
├── sheets_value_range.py    # SheetsValueRange (range wrapper with slicing)
├── sheets_slice.py          # SheetSlice singleton, slice conversions
└── misc.py                  # A1 notation, enums, constants, SheetSliceT
```

## Key Classes

### Sheets (sheets.py)
Inherits `DriveBase` for caching, throttling, retry.

**CRUD Methods:**
- `create(name, sheets)` - Create spreadsheet
- `copy_to(source_id, dest_id, sheet_id)` - Copy sheet between spreadsheets
- `get(spreadsheet_id)` - Get spreadsheet metadata
- `get_spreadsheet(spreadsheet_id)` - Alias for get
- `has(spreadsheet_id, sheet_name)` - Check if sheet exists
- `add(spreadsheet_id, sheet_name, rows, cols)` - Add new sheet
- `delete(spreadsheet_id, sheet_id)` - Delete sheet
- `rename(spreadsheet_id, sheet_id, new_name)` - Rename sheet

**Value Methods:**
- `values(spreadsheet_id, range, value_render_option)` - Read range
- `value(spreadsheet_id, range)` - Read single value
- `update(spreadsheet_id, range, values, value_input_option)` - Write range
- `batch_update(spreadsheet_id, value_ranges, batch_size)` - Batch write
- `append(spreadsheet_id, range, values, value_input_option)` - Append rows
- `clear(spreadsheet_id, range)` - Clear range

**Format Methods:**
- `format(spreadsheet_id, range, **kwargs)` - Format cells
- `get_format(spreadsheet_id, range)` - Get current format
- `freeze(spreadsheet_id, sheet_name, rows, cols)` - Freeze rows/cols
- `format_header(spreadsheet_id, sheet_name, auto_resize)` - Format first row
- `reset_sheet(spreadsheet_id, sheet_name)` - Clear and resize to (1000, 26)

**DataFrame Methods:**
- `to_frame(values, header)` - Convert values to DataFrame
- `from_frame(df, include_header, as_dict)` - Convert DataFrame to values

**Utility Methods:**
- `resize_dimensions(spreadsheet_id, sheet_name, rows, cols)` - Resize sheet
- `align_columns(header, data, update)` - Match dict keys to header order

### SheetsValueRange (sheets_value_range.py)
Hashable range wrapper with slice notation.

**Properties:**
- `header` - First row (cached)
- `shape` - (rows, cols) dimensions (cached)
- `sheet_id` - Sheet ID (cached)
- `values` - Read all values

**Methods:**
- `update(values)` - Write values
- `append(values)` - Append rows
- `clear()` - Clear range
- `rename(new_name)` - Rename sheet
- `to_frame(header)` - Convert to DataFrame
- `__getitem__(key)` - Slice notation

**Usage:**
```python
Sheet1 = SheetsValueRange(sheets, spreadsheet_id, "Sheet1")
Sheet1[1, "A"].update([["Value"]])
Sheet1[2:5, 1:3].read()
```

### SheetSliceT (misc.py)
Dataclass for sheet ranges with slice notation.

**Fields:**
- `sheet_name: str | None`
- `rows: slice | int | str | EllipsisType`
- `columns: slice | int | str | EllipsisType`

**Methods:**
- `with_shape(shape)` - Apply shape to resolve ellipsis
- `__getitem__(key)` - Further slicing
- `__repr__()` - A1 notation representation

**Singleton:** `SheetSlice` - Pre-instantiated for convenience

### SheetsFormat (misc.py)
Formatting container dataclass.

**Fields:**
- `cell_formats: list[list[CellFormat]]`
- `row_sizes: list[int]`
- `column_sizes: list[int]`

## Enums

### ValueInputOption
- `unspecified` - Default
- `raw` - No parsing (stores as-is)
- `user_entered` - Parse as if typed (formulas, dates, etc.)

### ValueRenderOption
- `formatted` - Formatted strings
- `unformatted` - Raw values
- `formula` - Show formulas

### InsertDataOption
- `insert` - Insert new rows
- `overwrite` - Replace existing

### HorizontalAlignment
- `LEFT`, `CENTER`, `RIGHT`

### VerticalAlignment
- `TOP`, `MIDDLE`, `BOTTOM`

### WrapStrategy
- `OVERFLOW_CELL` - Overflow to adjacent
- `CLIP` - Truncate
- `WRAP` - Wrap text

### TextDirection
- `LEFT_TO_RIGHT`
- `RIGHT_TO_LEFT`

### SheetsDimension
- `rows`
- `columns`

## Key Functions

### A1 Notation (misc.py)
- `int_to_A1(n)` - Column index → letter (1→A, 27→AA)
- `A1_to_int(s)` - Letter → index (A→1, AA→27)
- `rc_to_A1(row, col)` - (row, col) → "A1"
- `A1_to_rc(s)` - "A1" → (row, col)
- `A1_to_slices(range_str)` - "A1:B2" → (slice(0,2), slice(0,2))
- `expand_slices(slices, shape)` - Slices → "A1:B2"

### Range Utilities (misc.py)
- `normalize_sheet_name(name)` - Add quotes if needed
- `split_sheet_range(range_str)` - Split "Sheet1!A1:B2" → ("Sheet1", "A1:B2")
- `format_range_name(sheet_name, range_str)` - Combine → "Sheet1!A1:B2"

### Slice Utilities (misc.py)
- `ix_to_slice(ix, size)` - Index/slice → normalized slice
- `normalize_slice(slc, size)` - Resolve negative indices
- `ix_to_norm_slice(ix, size)` - Index → slice with bounds

### Caching (sheets_slice.py)
- `to_sheet_slice(range)` - Cached conversion to SheetSliceT
- `sheets_rangekey()` - Cache key generator

## Constants

### API
- `VERSION = "v4"` - Sheets API version

### Defaults
- `DEFAULT_SHEET_NAME = "'Sheet1'"` - Default sheet
- `DEFAULT_SHEET_SHAPE = (1000, 26)` - Default dimensions
- `INIT_SHEET_SHAPE = (..., ...)` - Ellipsis shape
- `DEFAULT_CHUNK_SIZE_BYTES = 1 * 1024 * 1024` - 1MB chunk limit

### A1 Notation
- `BASE = 26` - Alphabet size
- `OFFSET = 1` - 1-indexed (A=1, not 0)

### Other
- `DUPE_SUFFIX = "__dupe__"` - Duplicate column suffix

## Usage Examples

### Slice Notation
```python
from googleapiutils2 import Sheets, SheetsValueRange

sheets = Sheets()
Sheet1 = SheetsValueRange(sheets, sheet_url, "Sheet1")

# Single cell
Sheet1[1, "A"].update([["Value"]])

# Range
Sheet1[2:5, 1:3].update([[1,2,3], [4,5,6], [7,8,9]])

# Entire row/column
Sheet1[1, ...].update([["Header 1", "Header 2", "Header 3"]])
Sheet1[..., "A"].update([[1], [2], [3]])

# Read all
data = Sheet1[...].read()

# Negative indexing
Sheet1[-1, -1].update([["Bottom right"]])
```

### Batch Updates
```python
sheets.batch_update(sheet_url, {
    Sheet1[1, ...]: [["Header 1", "Header 2"]],
    Sheet1[2:4, ...]: [[1, 2], [3, 4]],
    "Sheet2!A1": [["Data"]]
})
```

### DataFrame Integration
```python
import pandas as pd

# Read to DataFrame
df = Sheet1[...].to_frame()

# Write from DataFrame
values = sheets.from_frame(df, include_header=True)
Sheet1[1:, ...].update(values)

# Column alignment (dict mode)
data = [
    {"Name": "Alice", "Age": 30},
    {"Name": "Bob", "Age": 25}
]
aligned = sheets.align_columns(Sheet1.header, data, update=True)
Sheet1[2:, ...].update(aligned)
```

### Formatting
```python
# Format header
sheets.format_header(sheet_url, "Sheet1", auto_resize=True)

# Custom format
sheets.format(
    sheet_url,
    Sheet1[1, ...],
    bold=True,
    background_color="#d48686",
    horizontal_alignment=HorizontalAlignment.CENTER,
    wrap_strategy=WrapStrategy.WRAP
)

# Get current format
fmt = sheets.get_format(sheet_url, Sheet1[1:5, 1:3])
```

### Create & Manage Sheets
```python
# Create spreadsheet
ss = sheets.create(
    name="My Spreadsheet",
    sheets=[
        {"properties": {"title": "Sheet1", "gridProperties": {"rowCount": 100, "columnCount": 10}}}
    ]
)

# Add sheet
sheets.add(ss['spreadsheetId'], "Sheet2", rows=500, cols=20)

# Rename
sheets.rename(ss['spreadsheetId'], sheet_id, "Renamed Sheet")

# Delete
sheets.delete(ss['spreadsheet

Id'], sheet_id)

# Freeze
sheets.freeze(ss['spreadsheetId'], "Sheet1", rows=1, cols=0)
```

### Column Alignment
```python
# Align dict data to header order
header = ["Name", "Age", "Email"]
data = [
    {"Email": "alice@example.com", "Name": "Alice", "Age": 30},  # Out of order
    {"Name": "Bob", "Age": 25}  # Missing Email
]

aligned = sheets.align_columns(header, data)
# Result: [["Alice", 30, "alice@example.com"], ["Bob", 25, ""]]

# Add new columns to header
aligned = sheets.align_columns(header, data, update=True)
# If data has "Phone", header becomes ["Name", "Age", "Email", "Phone"]
```

## Patterns

### Slice Notation
```python
# NumPy-like
Sheet[1:5, "A":"C"]       # Rows 1-4, cols A-C
Sheet[..., 1:3]           # All rows, cols 1-2
Sheet[-1, -1]             # Last cell

# A1 notation
Sheet["A1:B2"]            # Range
Sheet["Sheet1!A1:B2"]     # With sheet name

# Mixed
Sheet["Sheet1", 1:3, "A":"C"]
```

### Batch Operations
```python
# Auto-batching
sheets.batch_update(sheet_url, {
    range1: values1,
    range2: values2,
    # ...
}, batch_size=100)

# Flush remaining at exit
# atexit handler calls batch_update_remaining_auto()
```

### Chunking
```python
# Large updates auto-chunked (DEFAULT_CHUNK_SIZE_BYTES = 1MB)
large_data = [[...] for _ in range(10000)]
Sheet1[1:, ...].update(large_data)  # Auto-splits into chunks
```

### Auto-resizing
```python
# Sheet auto-grows if data exceeds dimensions
Sheet1[1:2000, 1:50].update(data)  # Grows to fit (2500 rows, 63 cols)
# Growth factor: 1.25x
```

### Caching
```python
# SheetsValueRange caches: header, shape, id, sheet_id
Sheet1.header  # First call: API request
Sheet1.header  # Subsequent: cached (80s TTL)

# Cache invalidated on mutations
Sheet1.update(data)  # Clears cache
```

## Internal Methods

**Sheets class:**
- `_get_sheet_id(spreadsheet_id, sheet_name)` - Get sheet ID (cached)
- `_flatten_ranges(value_ranges)` - Merge contiguous ranges
- `_flatten_value_ranges(value_ranges)` - Flatten batch dict
- `_chunk_range(range, values, predicate)` - Split into chunks
- `_create_cell_format(**kwargs)` - Build CellFormat
- `_create_format_body(range, sheet_id, **kwargs)` - Build format request
- `_destructure_row_format_data(data)` - Extract SheetsFormat
- `_resize_dimension(dimension, size)` - Build resize request
- `_ensure_sheet_shape(spreadsheet_id, range, values)` - Auto-resize
- `_add_dupe_suffix(header)` - Handle duplicate columns

## Dependencies

**External:**
- `google-api-python-client` - SpreadsheetsResource, ValuesResource
- `pandas` - DataFrame operations
- `cachetools` - cachedmethod, cached

**Internal:**
- `googleapiutils2.utils.DriveBase` - Base class
- `googleapiutils2.utils.Throttler` - Rate limiting
- `googleapiutils2.utils.parse_file_id` - URL → ID
- `googleapiutils2.utils.hex_to_rgb` - Color conversion
- `googleapiutils2.utils.deep_update` - Dict merging
- `googleapiutils2.utils.named_methodkey` - Cache keys
- `googleapiutils2.utils.nested_defaultdict` - Data structures

## Public API

**Exported from `__init__.py`:**
- `Sheets`
- `SheetsValueRange`
- `SheetSlice` (singleton)
- `SheetsFormat`
- `SheetSliceT`
- `SheetsRange` (type alias)
- `to_sheet_slice`
- Enums: `HorizontalAlignment`, `VerticalAlignment`, `WrapStrategy`, `TextDirection`, `InsertDataOption`, `ValueInputOption`, `ValueRenderOption`, `SheetsDimension`
