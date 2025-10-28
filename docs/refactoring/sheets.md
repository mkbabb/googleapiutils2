# Sheets Module Refactoring Specification

**Module:** `googleapiutils2/sheets/`
**Current Size:** 2,162 LOC (monolithic)
**Target Size:** ~1,100 LOC (distributed across 6 operation files)
**Complexity:** ★★★★★ (Highest)

---

## Current Structure (BEFORE)

```
sheets/
├── __init__.py                    # Exports: Sheets, SheetsValueRange, SheetSlice
├── sheets.py                      # 2,162 LOC - MONOLITHIC
├── sheets_value_range.py          # 132 LOC - SheetsValueRange class (unchanged)
├── sheets_slice.py                # 43 LOC - SheetSlice helper (unchanged)
└── misc.py                        # 453 LOC - Enums, constants (unchanged)
```

**Problems:**
- Single file with 2,162 lines (too large for AI consumption)
- 59 methods in one class (difficult to navigate)
- Mixed concerns: spreadsheet ops, sheet lifecycle, values, formatting, dimensions
- Complex internal methods buried in monolith
- Hard to locate specific functionality

---

## Proposed Structure (AFTER)

```
sheets/
├── __init__.py                    # Public API exports (unchanged)
├── sheets.py                      # Sheets class - thin coordinator (~400 LOC)
├── types.py                       # TYPE_CHECKING imports (~50 LOC)
├── operations/
│   ├── __init__.py                # Export all operation functions
│   ├── spreadsheet.py             # Spreadsheet operations (~150 LOC)
│   ├── sheet.py                   # Sheet lifecycle operations (~120 LOC)
│   ├── metadata.py                # Metadata and caching (~100 LOC)
│   ├── values.py                  # All value operations (~350 LOC)
│   ├── formatting.py              # Cell formatting operations (~200 LOC)
│   └── dimensions.py              # Dimension management (~120 LOC)
├── sheets_value_range.py          # SheetsValueRange (unchanged)
├── sheets_slice.py                # SheetSlice (unchanged)
└── misc.py                        # Enums, constants (unchanged)
```

**Benefits:**
- Largest file now ~400 LOC (73% reduction from 2,162 LOC)
- Clear domain separation (spreadsheet vs sheet vs values vs formatting)
- Easy to locate functionality
- Testable pure functions
- AI-friendly file sizes

---

## Operation Module Breakdown

### 1. `operations/spreadsheet.py` (~150 LOC)

**Responsibility:** Spreadsheet-level operations

**Functions:**
- `create_spreadsheet()` - Create new spreadsheet
- `get_spreadsheet()` - Fetch spreadsheet metadata
- `copy_sheet_to_spreadsheet()` - Copy sheet between spreadsheets
- `batch_update_spreadsheet()` - Execute batch requests
- `create_range_url()` - Generate shareable URLs

---

### 2. `operations/sheet.py` (~120 LOC)

**Responsibility:** Sheet lifecycle management

**Functions:**
- `add_sheets()` - Add sheets to spreadsheet
- `delete_sheets()` - Delete sheets
- `rename_sheet()` - Rename sheet
- `has_sheet()` - Check sheet existence
- `get_sheet()` - Get sheet metadata

---

### 3. `operations/metadata.py` (~100 LOC)

**Responsibility:** Sheet metadata and caching

**Functions:**
- `get_sheet_id()` - Resolve sheet name to ID (cached)
- `get_header()` - Get first row (cached)
- `get_shape()` - Get dimensions (cached)
- `invalidate_cache()` - Clear cached metadata
- `set_cache()` - Update cache entry

---

### 4. `operations/values.py` (~350 LOC)

**Responsibility:** All value operations (read, write, batch, process)

**Functions:**
- `read_values()` - Read range values
- `read_single_value()` - Read single cell
- `update_values()` - Update range
- `append_values()` - Append to sheet
- `batch_update_values()` - Batch multiple updates
- `clear_values()` - Clear range
- `get_append_range()` - Calculate append position
- `process_dict_values()` - Convert dicts to aligned lists
- `chunk_values()` - Split large updates
- `flatten_ranges()` - Consolidate contiguous ranges
- `to_dataframe()` - Convert values to DataFrame
- `from_dataframe()` - Convert DataFrame to values

---

### 5. `operations/formatting.py` (~200 LOC)

**Responsibility:** Cell formatting

**Functions:**
- `apply_format()` - Apply cell formatting
- `get_format()` - Extract formatting
- `create_cell_format()` - Build CellFormat object
- `create_format_request()` - Build batch format request
- `parse_cell_format()` - Parse API format response
- `format_header()` - Quick header formatting
- `clear_formatting()` - Remove all formatting

---

### 6. `operations/dimensions.py` (~120 LOC)

**Responsibility:** Sheet dimensions (resize, freeze)

**Functions:**
- `resize_sheet()` - Resize grid dimensions
- `resize_dimensions()` - Resize rows/columns individually
- `freeze_rows_columns()` - Freeze panes
- `ensure_sheet_shape()` - Auto-resize to fit data
- `check_sheet_shape()` - Validate dimensions
- `reset_sheet()` - Clear and resize sheet

---

## Code Examples: BEFORE → AFTER

### Example 1: Update Values (Core Method)

#### BEFORE (Monolithic)

```python
# sheets/sheets.py (lines 1014-1072 of 2,162 total)

class Sheets(DriveBase):
    def update(
        self,
        spreadsheet_id: str,
        range_name: SheetsRange = DEFAULT_SHEET_NAME,
        values: SheetsValues | None = None,
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        align_columns: bool = True,
        ensure_shape: bool = True,
        chunk_size_bytes: int | None = DEFAULT_CHUNK_SIZE_BYTES,
        keep_values: bool = True,
    ) -> UpdateValuesResponse | None:
        """Updates a range of values in a spreadsheet.

        If `values` is a list of dicts, the keys of the first dict will be used as the header row.
        Further, if the input is a list of dicts and `align_columns` is True, the columns of the spreadsheet
        will be aligned with the keys of the first dict.

        Large updates are automatically chunked to avoid API timeouts.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        values = values if values is not None else [[]]

        if ensure_shape:
            self._ensure_sheet_shape(spreadsheet_id, [range_name])

        return self._update_chunked(
            spreadsheet_id=spreadsheet_id,
            range_name=range_name,
            values=values,
            value_input_option=value_input_option,
            align_columns=align_columns,
            ensure_shape=ensure_shape,
            chunk_size_bytes=chunk_size_bytes,
            update=keep_values,
        )

    def _update_chunked(
        self,
        spreadsheet_id: str,
        range_name: SheetsRange,
        values: SheetsValues,
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        align_columns: bool = True,
        ensure_shape: bool = True,
        chunk_size_bytes: int | None = DEFAULT_CHUNK_SIZE_BYTES,
        update: bool = True,
    ) -> UpdateValuesResponse | None:
        """Updates a range of values in chunks to avoid API timeouts."""
        # ... 90 lines of complex chunking logic
        # ... calls to _process_sheets_values()
        # ... calls to _get_row_size()
        # ... chunk splitting logic
        # ... batch update calls

    def _process_sheets_values(
        self,
        spreadsheet_id: str,
        sheet_slice: SheetSliceT,
        values: SheetsValues,
        align_columns: bool = True,
        insert_header: bool = True,
        update: bool = True,
    ) -> list[list[Any]] | None:
        """Process values, handling dict-to-list conversion."""
        if all(isinstance(value, dict) for value in values):
            return self._dict_to_values_align_columns(
                spreadsheet_id=spreadsheet_id,
                sheet_slice=sheet_slice,
                rows=values,
                align_columns=align_columns,
                insert_header=insert_header,
                update=update,
            )
        else:
            return values

    def _dict_to_values_align_columns(
        self,
        spreadsheet_id: str,
        sheet_slice: SheetSliceT,
        rows: list[dict],
        align_columns: bool = True,
        insert_header: bool = False,
        update: bool = True,
    ) -> list[list[Any]] | None:
        """Convert dict rows to aligned list format."""
        # ... 100+ lines of complex DataFrame manipulation
        # ... header fetching and alignment
        # ... duplicate column handling
        # ... cache updates
```

#### AFTER (Modular)

**Main Class (Thin Coordinator):**

```python
# sheets/sheets.py (~400 LOC total)

from googleapiutils2.utils import DriveBase, parse_file_id
from .operations import values as values_ops
from .operations import metadata as metadata_ops

class Sheets(DriveBase):
    def update(
        self,
        spreadsheet_id: str,
        range_name: SheetsRange = DEFAULT_SHEET_NAME,
        values: SheetsValues | None = None,
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        align_columns: bool = True,
        ensure_shape: bool = True,
        chunk_size_bytes: int | None = DEFAULT_CHUNK_SIZE_BYTES,
        keep_values: bool = True,
    ) -> UpdateValuesResponse | None:
        """Updates a range of values (delegates to operation module)."""
        spreadsheet_id = parse_file_id(spreadsheet_id)
        values = values if values is not None else [[]]

        return values_ops.update_values(
            service=self.service,
            spreadsheet_id=spreadsheet_id,
            range_name=range_name,
            values=values,
            value_input_option=value_input_option,
            align_columns=align_columns,
            ensure_shape=ensure_shape,
            chunk_size_bytes=chunk_size_bytes,
            keep_values=keep_values,
            # Pass callbacks for stateful operations
            get_header_fn=lambda sn: self.header(spreadsheet_id, sn),
            ensure_shape_fn=lambda rn: self._ensure_sheet_shape(spreadsheet_id, rn),
            get_values_fn=lambda rn, opt: self.values(spreadsheet_id, rn, opt),
            set_cache_fn=self._set_sheet_cache,
        )
```

**Pure Function (Testable, Atomic):**

```python
# sheets/operations/values.py (~350 LOC total)

from typing import TYPE_CHECKING, Callable, Any

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import SheetsResource

def update_values(
    service: "SheetsResource",
    spreadsheet_id: str,
    range_name: str,
    values: list[list[Any]] | list[dict],
    value_input_option: str = "USER_ENTERED",
    align_columns: bool = True,
    ensure_shape: bool = True,
    chunk_size_bytes: int | None = None,
    keep_values: bool = True,
    get_header_fn: Callable[[str], list[str]] | None = None,
    ensure_shape_fn: Callable[[list[str]], None] | None = None,
    get_values_fn: Callable[[str, str], dict] | None = None,
    set_cache_fn: Callable[[str, Any, str, str], None] | None = None,
) -> dict | None:
    """Pure function: Update a range of values in a spreadsheet.

    Args:
        service: Google Sheets API service
        spreadsheet_id: Target spreadsheet ID
        range_name: A1 notation range
        values: 2D list or list of dicts
        value_input_option: How to interpret values (USER_ENTERED or RAW)
        align_columns: If True and values are dicts, align columns with header
        ensure_shape: If True, auto-resize sheet to fit values
        chunk_size_bytes: Max chunk size for large updates
        keep_values: If True, preserve existing values not in dict keys
        get_header_fn: Callback to fetch current header
        ensure_shape_fn: Callback to ensure sheet dimensions
        get_values_fn: Callback to fetch current values
        set_cache_fn: Callback to update cache

    Returns:
        UpdateValuesResponse dict or None if no changes
    """
    from .dimensions import ensure_sheet_shape as ensure_shape_internal

    # Ensure shape if requested
    if ensure_shape and ensure_shape_fn:
        ensure_shape_fn([range_name])

    # Process dict values with column alignment
    if align_columns and values and isinstance(values[0], dict):
        values = process_dict_values(
            spreadsheet_id=spreadsheet_id,
            range_name=range_name,
            dict_values=values,
            keep_values=keep_values,
            get_header_fn=get_header_fn,
            get_values_fn=get_values_fn,
            set_cache_fn=set_cache_fn,
        )

        if values is None:  # No changes needed
            return None

    # Chunk if necessary
    if chunk_size_bytes and needs_chunking(values, chunk_size_bytes):
        return update_chunked(
            service=service,
            spreadsheet_id=spreadsheet_id,
            range_name=range_name,
            values=values,
            value_input_option=value_input_option,
            chunk_size_bytes=chunk_size_bytes,
            ensure_shape_fn=ensure_shape_fn,
        )

    # Single update
    body = {"values": values}
    return service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption=value_input_option,
        body=body,
    ).execute()


def process_dict_values(
    spreadsheet_id: str,
    range_name: str,
    dict_values: list[dict],
    keep_values: bool = True,
    get_header_fn: Callable[[str], list[str]] | None = None,
    get_values_fn: Callable[[str, str], dict] | None = None,
    set_cache_fn: Callable[[str, Any, str, str], None] | None = None,
) -> list[list[Any]] | None:
    """Pure function: Convert dict rows to aligned 2D list format.

    Handles column alignment, header updates, and value preservation.

    Args:
        spreadsheet_id: Target spreadsheet
        range_name: A1 notation range
        dict_values: List of dicts to convert
        keep_values: If True, preserve existing values for unmapped columns
        get_header_fn: Callback to fetch current header
        get_values_fn: Callback to fetch current values
        set_cache_fn: Callback to update header cache

    Returns:
        Aligned 2D list or None if no changes needed
    """
    import pandas as pd
    from ..sheets_slice import to_sheet_slice
    from ..misc import DUPE_SUFFIX, ValueRenderOption

    if not get_header_fn:
        raise ValueError("get_header_fn required for dict value processing")

    sheet_slice = to_sheet_slice(range_name)
    sheet_name = sheet_slice.sheet_name

    # Get existing header and data
    header = get_header_fn(sheet_name)
    header = pd.Index(header).astype(str)

    # Get current values if preserving
    current_df = pd.DataFrame()
    if keep_values and get_values_fn:
        current_values = get_values_fn(range_name, ValueRenderOption.formula).get("values", [])
        if current_values:
            current_df = pd.DataFrame(current_values)
            current_df.columns = header[: len(current_df.columns)]

    # Create DataFrame from new data
    new_df = pd.DataFrame(dict_values)

    # Add dupe suffix for duplicate columns
    new_df = _add_dupe_suffix(new_df)

    # Check for new columns and update header if needed
    new_cols = new_df.columns.difference(header)
    if len(new_cols) > 0:
        header = header.append(pd.Index(new_cols))
        # Update header in sheet (would need update callback)
        if set_cache_fn:
            set_cache_fn("header", list(header), spreadsheet_id, sheet_name)

    # Align columns
    for col in header:
        if col not in new_df.columns:
            if col in current_df.columns:
                new_df[col] = current_df[col]
            else:
                new_df[col] = ""

    # Reorder and clean
    new_df = new_df.reindex(columns=header)
    new_df.columns = new_df.columns.str.replace(rf"{DUPE_SUFFIX}\d+", "", regex=True)

    # Convert to list format
    values = new_df.fillna("").values.tolist()

    # Check if any changes were made
    if keep_values and current_df.equals(new_df):
        return None

    return values


def update_chunked(
    service: "SheetsResource",
    spreadsheet_id: str,
    range_name: str,
    values: list[list[Any]],
    value_input_option: str,
    chunk_size_bytes: int,
    ensure_shape_fn: Callable[[list[str]], None] | None = None,
) -> dict | None:
    """Pure function: Update with chunking for large datasets.

    Args:
        service: Google Sheets API service
        spreadsheet_id: Target spreadsheet
        range_name: A1 notation range
        values: 2D list of values
        value_input_option: USER_ENTERED or RAW
        chunk_size_bytes: Max bytes per chunk
        ensure_shape_fn: Callback to ensure dimensions

    Returns:
        Combined UpdateValuesResponse
    """
    from ..sheets_slice import to_sheet_slice, SheetSlice

    sheet_slice = to_sheet_slice(range_name)
    chunks = []
    current_chunk = []
    current_size = 0

    for i, row in enumerate(values):
        row_size = sum(len(str(cell)) for cell in row)

        if current_size + row_size > chunk_size_bytes and current_chunk:
            chunks.append((len(chunks), current_chunk))
            current_chunk = []
            current_size = 0

        current_chunk.append(row)
        current_size += row_size

    if current_chunk:
        chunks.append((len(chunks), current_chunk))

    # Process chunks
    responses = []
    for chunk_idx, chunk_values in chunks:
        # Calculate chunk range
        start_row = sheet_slice.rows.start + sum(len(c[1]) for c in chunks[:chunk_idx])
        chunk_slice = SheetSlice[
            sheet_slice.sheet_name,
            start_row : start_row + len(chunk_values),
            sheet_slice.columns,
        ]

        if ensure_shape_fn:
            ensure_shape_fn([str(chunk_slice)])

        # Update chunk
        response = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=str(chunk_slice),
            body={"values": chunk_values},
            valueInputOption=value_input_option,
        ).execute()
        responses.append(response)

    return responses[0] if len(responses) == 1 else {"responses": responses}


def needs_chunking(values: list[list[Any]], chunk_size_bytes: int) -> bool:
    """Pure function: Check if values need chunking."""
    total_size = sum(sum(len(str(cell)) for cell in row) for row in values)
    return total_size > chunk_size_bytes


def _add_dupe_suffix(df: "pd.DataFrame", suffix: str = "__dupe__") -> "pd.DataFrame":
    """Add suffix to duplicate column names."""
    import pandas as pd

    cols = pd.Series(df.columns)
    for dup in cols[cols.duplicated()].unique():
        dup_indices = cols[cols == dup].index.tolist()
        for i, idx in enumerate(dup_indices[1:], start=1):
            cols.iloc[idx] = f"{dup}{suffix}{i}"
    df.columns = cols
    return df
```

---

### Example 2: Formatting (Complex Method)

#### BEFORE (Monolithic)

```python
# sheets/sheets.py (lines 1600-1750 of 2,162 total)

class Sheets(DriveBase):
    def format(
        self,
        spreadsheet_id: str,
        range_names: SheetsRange | list[SheetsRange],
        update: bool = True,
        bold: bool | None = None,
        italic: bool | None = None,
        underline: bool | None = None,
        strikethrough: bool | None = None,
        font_size: int | None = None,
        font_family: str | None = None,
        text_color: str | Color | None = None,
        background_color: str | Color | None = None,
        # ... 10+ more parameters
        cell_format: CellFormat | None = None,
        sheets_format: SheetsFormat | None = None,
    ):
        """Format cells with text/layout options."""
        # ... 150+ lines of complex formatting logic
        # ... calls to _create_cell_format()
        # ... calls to _create_format_body()
        # ... batch update construction
        # ... dimension resizing

    @staticmethod
    def _create_cell_format(
        bold: bool | None = None,
        italic: bool | None = None,
        # ... 15+ parameters
        cell_format: CellFormat | None = None,
    ) -> CellFormat:
        """Build CellFormat dict from parameters."""
        # ... 80+ lines of dict construction
        # ... hex to RGB conversion
        # ... deep merging logic

    @staticmethod
    def _create_format_body(
        sheet_id: int,
        start_row: int,
        start_col: int,
        cell_format: CellFormat,
        end_row: int | None = None,
        end_col: int | None = None,
    ) -> Request:
        """Creates batch update request body."""
        # ... 40 lines of request construction
```

#### AFTER (Modular)

**Main Class:**

```python
# sheets/sheets.py

from .operations import formatting as fmt_ops

class Sheets(DriveBase):
    def format(
        self,
        spreadsheet_id: str,
        range_names: SheetsRange | list[SheetsRange],
        update: bool = True,
        **format_params,
    ):
        """Apply formatting (delegates to operation module)."""
        return fmt_ops.apply_format(
            service=self.service,
            spreadsheet_id=spreadsheet_id,
            range_names=range_names,
            update=update,
            get_sheet_id_fn=lambda sn: self._get_sheet_id(spreadsheet_id, sn),
            get_format_fn=lambda rn: self.get_format(spreadsheet_id, rn) if update else None,
            batch_update_fn=lambda body: self.batch_update_spreadsheet(spreadsheet_id, body),
            **format_params,
        )
```

**Pure Functions:**

```python
# sheets/operations/formatting.py (~200 LOC total)

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import SheetsResource

def apply_format(
    service: "SheetsResource",
    spreadsheet_id: str,
    range_names: str | list[str],
    update: bool = True,
    get_sheet_id_fn: Callable[[str], int] | None = None,
    get_format_fn: Callable[[str], dict] | None = None,
    batch_update_fn: Callable[[dict], dict] | None = None,
    **format_params,
) -> dict:
    """Pure function: Apply formatting to ranges.

    Args:
        service: Google Sheets API service
        spreadsheet_id: Target spreadsheet
        range_names: Range(s) to format
        update: If True, merge with existing format
        get_sheet_id_fn: Callback to get sheet ID
        get_format_fn: Callback to get existing format
        batch_update_fn: Callback to execute batch update
        **format_params: Formatting parameters (bold, italic, etc.)

    Returns:
        BatchUpdateSpreadsheetResponse
    """
    from ..sheets_slice import to_sheet_slice

    range_names = [range_names] if isinstance(range_names, str) else range_names
    requests = []

    for range_name in range_names:
        sheet_slice = to_sheet_slice(range_name)
        sheet_id = get_sheet_id_fn(sheet_slice.sheet_name) if get_sheet_id_fn else 0

        # Get existing format if updating
        existing_format = None
        if update and get_format_fn:
            existing_format = get_format_fn(range_name)

        # Create cell format
        cell_format = create_cell_format(
            existing_format=existing_format,
            **format_params,
        )

        # Create format request
        request = create_format_request(
            sheet_id=sheet_id,
            start_row=sheet_slice.rows.start,
            start_col=sheet_slice.columns.start,
            end_row=sheet_slice.rows.stop,
            end_col=sheet_slice.columns.stop,
            cell_format=cell_format,
        )
        requests.append(request)

    # Execute batch update
    body = {"requests": requests}
    return batch_update_fn(body) if batch_update_fn else {}


def create_cell_format(
    bold: bool | None = None,
    italic: bool | None = None,
    underline: bool | None = None,
    strikethrough: bool | None = None,
    font_size: int | None = None,
    font_family: str | None = None,
    text_color: str | dict | None = None,
    background_color: str | dict | None = None,
    horizontal_alignment: str | None = None,
    vertical_alignment: str | None = None,
    wrap_strategy: str | None = None,
    number_format: dict | None = None,
    existing_format: dict | None = None,
) -> dict:
    """Pure function: Build CellFormat dict from parameters.

    Args:
        bold, italic, etc.: Text formatting options
        text_color: Hex string or RGB dict
        background_color: Hex string or RGB dict
        existing_format: Existing format to merge with

    Returns:
        CellFormat dict
    """
    from googleapiutils2.utils import hex_to_rgb, deep_update

    cell_format = {}

    # Text format
    text_format = {}
    if bold is not None:
        text_format["bold"] = bold
    if italic is not None:
        text_format["italic"] = italic
    if underline is not None:
        text_format["underline"] = underline
    if strikethrough is not None:
        text_format["strikethrough"] = strikethrough
    if font_size is not None:
        text_format["fontSize"] = font_size
    if font_family is not None:
        text_format["fontFamily"] = font_family

    # Colors
    if text_color is not None:
        text_format["foregroundColor"] = (
            hex_to_rgb(text_color) if isinstance(text_color, str) else text_color
        )
    if background_color is not None:
        cell_format["backgroundColor"] = (
            hex_to_rgb(background_color) if isinstance(background_color, str) else background_color
        )

    if text_format:
        cell_format["textFormat"] = text_format

    # Alignment
    if horizontal_alignment or vertical_alignment or wrap_strategy:
        cell_format["horizontalAlignment"] = horizontal_alignment
        cell_format["verticalAlignment"] = vertical_alignment
        cell_format["wrapStrategy"] = wrap_strategy

    # Number format
    if number_format:
        cell_format["numberFormat"] = number_format

    # Merge with existing if update mode
    if existing_format:
        cell_format = deep_update(existing_format, cell_format)

    return cell_format


def create_format_request(
    sheet_id: int,
    start_row: int,
    start_col: int,
    end_row: int | None,
    end_col: int | None,
    cell_format: dict,
) -> dict:
    """Pure function: Create batch update format request.

    Args:
        sheet_id: Target sheet ID
        start_row, start_col: 1-indexed start position
        end_row, end_col: 1-indexed end position (exclusive)
        cell_format: CellFormat dict

    Returns:
        Request dict for batch update
    """
    # Convert 1-indexed to 0-indexed
    start_row_idx = start_row - 1 if start_row != ... else 0
    start_col_idx = start_col - 1 if start_col != ... else 0
    end_row_idx = end_row if end_row and end_row != ... else None
    end_col_idx = end_col if end_col and end_col != ... else None

    grid_range = {
        "sheetId": sheet_id,
        "startRowIndex": start_row_idx,
        "startColumnIndex": start_col_idx,
    }
    if end_row_idx is not None:
        grid_range["endRowIndex"] = end_row_idx
    if end_col_idx is not None:
        grid_range["endColumnIndex"] = end_col_idx

    return {
        "repeatCell": {
            "range": grid_range,
            "cell": {"userEnteredFormat": cell_format},
            "fields": "userEnteredFormat",
        }
    }


def clear_formatting(
    service: "SheetsResource",
    spreadsheet_id: str,
    sheet_name: str,
    get_sheet_id_fn: Callable[[str], int],
    batch_update_fn: Callable[[dict], dict],
) -> dict:
    """Pure function: Clear all formatting from a sheet."""
    sheet_id = get_sheet_id_fn(sheet_name)

    request = {
        "updateCells": {
            "range": {"sheetId": sheet_id},
            "fields": "userEnteredFormat",
        }
    }

    body = {"requests": [request]}
    return batch_update_fn(body)
```

---

### Example 3: Metadata (Cached Methods)

#### BEFORE

```python
# sheets/sheets.py (lines 210-230 of 2,162 total)

class Sheets(DriveBase):
    @cachedmethod(operator.attrgetter("_cache"), key=named_methodkey("header"))
    def header(self, spreadsheet_id: str, sheet_name: str = DEFAULT_SHEET_NAME):
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(SheetSlice[sheet_name, 1, ...])
        return self.values(spreadsheet_id=spreadsheet_id, range_name=range_name).get("values", [[]])[0]

    @cachedmethod(operator.attrgetter("_cache"), key=named_methodkey("shape"))
    def shape(self, spreadsheet_id: str, sheet_name: str = DEFAULT_SHEET_NAME):
        spreadsheet_id = parse_file_id(spreadsheet_id)
        properties = self.get(spreadsheet_id=spreadsheet_id, sheet_name=sheet_name)["properties"]
        shape = (
            properties["gridProperties"]["rowCount"],
            properties["gridProperties"]["columnCount"],
        )
        return shape

    @cachedmethod(operator.attrgetter("_cache"), key=named_methodkey("id"))
    def id(self, spreadsheet_id: str, sheet_name: str = DEFAULT_SHEET_NAME) -> int:
        sheet = self.get(spreadsheet_id=spreadsheet_id, sheet_name=sheet_name)
        return sheet["properties"]["sheetId"]
```

#### AFTER

**Main Class (Keeps Decorators):**

```python
# sheets/sheets.py

from cachetools import cachedmethod
import operator
from googleapiutils2.utils import named_methodkey
from .operations import metadata as meta_ops

class Sheets(DriveBase):
    @cachedmethod(operator.attrgetter("_cache"), key=named_methodkey("header"))
    def header(self, spreadsheet_id: str, sheet_name: str = DEFAULT_SHEET_NAME):
        """Get header row (cached, delegates to operation)."""
        return meta_ops.get_header(
            service=self.service,
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            get_values_fn=self.values,
        )

    @cachedmethod(operator.attrgetter("_cache"), key=named_methodkey("shape"))
    def shape(self, spreadsheet_id: str, sheet_name: str = DEFAULT_SHEET_NAME):
        """Get dimensions (cached, delegates to operation)."""
        return meta_ops.get_shape(
            service=self.service,
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            get_sheet_fn=self.get,
        )

    @cachedmethod(operator.attrgetter("_cache"), key=named_methodkey("id"))
    def id(self, spreadsheet_id: str, sheet_name: str = DEFAULT_SHEET_NAME) -> int:
        """Get sheet ID (cached, delegates to operation)."""
        return meta_ops.get_sheet_id(
            service=self.service,
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            get_sheet_fn=self.get,
        )
```

**Pure Functions:**

```python
# sheets/operations/metadata.py (~100 LOC total)

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import SheetsResource

def get_header(
    service: "SheetsResource",
    spreadsheet_id: str,
    sheet_name: str,
    get_values_fn: Callable[[str, str], dict],
) -> list[str]:
    """Pure function: Get first row as header.

    Args:
        service: Sheets API service
        spreadsheet_id: Target spreadsheet
        sheet_name: Sheet name
        get_values_fn: Callback to fetch values

    Returns:
        List of header values
    """
    from googleapiutils2.utils import parse_file_id
    from ..sheets_slice import SheetSlice

    spreadsheet_id = parse_file_id(spreadsheet_id)
    range_name = str(SheetSlice[sheet_name, 1, ...])
    result = get_values_fn(spreadsheet_id, range_name)
    return result.get("values", [[]])[0]


def get_shape(
    service: "SheetsResource",
    spreadsheet_id: str,
    sheet_name: str,
    get_sheet_fn: Callable[[str, str | None, int | None], dict],
) -> tuple[int, int]:
    """Pure function: Get sheet dimensions.

    Args:
        service: Sheets API service
        spreadsheet_id: Target spreadsheet
        sheet_name: Sheet name
        get_sheet_fn: Callback to fetch sheet metadata

    Returns:
        Tuple of (rows, columns)
    """
    from googleapiutils2.utils import parse_file_id

    spreadsheet_id = parse_file_id(spreadsheet_id)
    sheet = get_sheet_fn(spreadsheet_id, sheet_name, None)
    properties = sheet["properties"]["gridProperties"]
    return (properties["rowCount"], properties["columnCount"])


def get_sheet_id(
    service: "SheetsResource",
    spreadsheet_id: str,
    sheet_name: str,
    get_sheet_fn: Callable[[str, str | None, int | None], dict],
) -> int:
    """Pure function: Get sheet ID from name.

    Args:
        service: Sheets API service
        spreadsheet_id: Target spreadsheet
        sheet_name: Sheet name
        get_sheet_fn: Callback to fetch sheet metadata

    Returns:
        Sheet ID
    """
    from googleapiutils2.utils import parse_file_id

    spreadsheet_id = parse_file_id(spreadsheet_id)
    sheet = get_sheet_fn(spreadsheet_id, sheet_name, None)
    return sheet["properties"]["sheetId"]
```

---

## Migration Strategy

### Phase 1: Create Operation Modules (Week 1, Days 1-2)

1. Create `sheets/operations/` directory
2. Create `sheets/types.py` for TYPE_CHECKING imports
3. Extract pure functions to operation modules:
   - `operations/spreadsheet.py` - Day 1 morning
   - `operations/sheet.py` - Day 1 afternoon
   - `operations/metadata.py` - Day 1 evening
   - `operations/values.py` - Day 2 morning (largest)
   - `operations/formatting.py` - Day 2 afternoon
   - `operations/dimensions.py` - Day 2 evening

**Validation:** Code compiles, no imports broken

### Phase 2: Refactor Class Methods (Week 1, Days 3-4)

1. Update `Sheets` class methods to delegate to operations
2. Preserve all decorators (@cachedmethod on metadata methods)
3. Pass callbacks for stateful operations
4. Keep instance variables and initialization unchanged

**Validation:** Existing integration tests pass

### Phase 3: Testing (Week 1, Day 5)

1. Run full test suite: `pytest test/sheets/`
2. Verify no regressions
3. Add unit tests for pure functions (easy without mocking)
4. Type check with mypy

**Validation:** 100% test compatibility

### Phase 4: Cleanup (Week 2, Day 1)

1. Remove any duplicated code
2. Update `operations/__init__.py` to export functions
3. Run linting: `ruff check --fix googleapiutils2/sheets/`
4. Format code: `black googleapiutils2/sheets/`

**Validation:** Linting passes, code formatted

---

## File Size Comparison

| File | Before (LOC) | After (LOC) | Reduction |
|------|--------------|-------------|-----------|
| `sheets.py` | 2,162 | ~400 | -81% |
| `operations/spreadsheet.py` | - | ~150 | NEW |
| `operations/sheet.py` | - | ~120 | NEW |
| `operations/metadata.py` | - | ~100 | NEW |
| `operations/values.py` | - | ~350 | NEW |
| `operations/formatting.py` | - | ~200 | NEW |
| `operations/dimensions.py` | - | ~120 | NEW |
| **Total** | **2,162** | **~1,440** | **-33%** |

**Note:** Total LOC slightly increased due to:
- Explicit type hints on pure functions
- Additional docstrings for clarity
- Callback parameter definitions

**Benefits outweigh cost:** Modularity, testability, AI-consumability

---

## Testing Strategy

### Unit Tests (New)

Pure functions are trivially testable:

```python
# test/sheets/operations/test_values.py

from googleapiutils2.sheets.operations import values

def test_process_dict_values_basic():
    """Test dict-to-list conversion with column alignment."""
    dict_vals = [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25, "city": "NYC"},
    ]

    result = values.process_dict_values(
        spreadsheet_id="test",
        range_name="Sheet1!A1:C2",
        dict_values=dict_vals,
        keep_values=False,
        get_header_fn=lambda sn: ["name", "age"],
        get_values_fn=None,
        set_cache_fn=None,
    )

    assert result == [
        ["Alice", 30, ""],
        ["Bob", 25, "NYC"],
    ]

def test_needs_chunking():
    """Test chunking predicate."""
    small_values = [["a", "b"]] * 10
    large_values = [["x" * 1000] * 100] * 100

    assert not values.needs_chunking(small_values, 1_000_000)
    assert values.needs_chunking(large_values, 1_000_000)
```

### Integration Tests (Existing, Unchanged)

```python
# test/sheets/test_sheets.py

def test_sheets_update(sheets: Sheets, test_spreadsheet: str):
    """Existing integration test - should pass without changes."""
    result = sheets.update(
        test_spreadsheet,
        "Sheet1!A1:B2",
        [["Header1", "Header2"], ["Value1", "Value2"]],
    )
    assert result is not None
    assert "updatedCells" in result
```

---

## Success Criteria

1. ✅ All existing integration tests pass (100% compatibility)
2. ✅ No breaking changes to public API
3. ✅ Largest file <400 LOC (was 2,162 LOC)
4. ✅ All operation files <350 LOC
5. ✅ Type hints pass mypy validation
6. ✅ Linting passes (ruff, black)
7. ✅ New unit tests for pure functions (>80% coverage)
8. ✅ Code review approval

---

## Benefits Summary

### For AI Consumption
- ✅ Largest file reduced from 2,162 → 400 LOC (81% reduction)
- ✅ Clear domain separation (values vs formatting vs dimensions)
- ✅ Descriptive file names (`operations/values.py`)
- ✅ Pure functions easier to understand than stateful methods

### For Developers
- ✅ Easy feature location (no hunting through 2,162 lines)
- ✅ Reduced merge conflicts (changes isolated to specific domains)
- ✅ Testable pure functions (no complex mocking)
- ✅ Clear dependencies (explicit callback parameters)

### For Maintainability
- ✅ Add new operations without modifying existing files
- ✅ Refactor individual domains independently
- ✅ Clear boundaries between spreadsheet/sheet/values/formatting
- ✅ Better code reuse (functions callable from multiple contexts)

---

## Appendix: Complete Function Mapping

| Current Method | New Location | New Function Name |
|----------------|--------------|-------------------|
| `create()` | `operations/spreadsheet.py` | `create_spreadsheet()` |
| `get_spreadsheet()` | `operations/spreadsheet.py` | `get_spreadsheet()` |
| `copy_to()` | `operations/spreadsheet.py` | `copy_sheet_to_spreadsheet()` |
| `batch_update_spreadsheet()` | `operations/spreadsheet.py` | `batch_update_spreadsheet()` |
| `create_range_url()` | `operations/spreadsheet.py` | `create_range_url()` |
| `add()` | `operations/sheet.py` | `add_sheets()` |
| `delete()` | `operations/sheet.py` | `delete_sheets()` |
| `rename()` | `operations/sheet.py` | `rename_sheet()` |
| `has()` | `operations/sheet.py` | `has_sheet()` |
| `get()` | `operations/sheet.py` | `get_sheet()` |
| `_get_sheet_id()` | `operations/metadata.py` | `get_sheet_id()` |
| `header()` | `operations/metadata.py` | `get_header()` |
| `shape()` | `operations/metadata.py` | `get_shape()` |
| `id()` | `operations/metadata.py` | `get_sheet_id()` |
| `values()` | `operations/values.py` | `read_values()` |
| `value()` | `operations/values.py` | `read_single_value()` |
| `update()` | `operations/values.py` | `update_values()` |
| `append()` | `operations/values.py` | `append_values()` |
| `batch_update()` | `operations/values.py` | `batch_update_values()` |
| `clear()` | `operations/values.py` | `clear_values()` |
| `_dict_to_values_align_columns()` | `operations/values.py` | `process_dict_values()` |
| `_update_chunked()` | `operations/values.py` | `update_chunked()` |
| `_chunk_range()` | `operations/values.py` | `chunk_values()` |
| `_flatten_ranges()` | `operations/values.py` | `flatten_ranges()` |
| `to_frame()` | `operations/values.py` | `to_dataframe()` |
| `from_frame()` | `operations/values.py` | `from_dataframe()` |
| `format()` | `operations/formatting.py` | `apply_format()` |
| `get_format()` | `operations/formatting.py` | `get_format()` |
| `_create_cell_format()` | `operations/formatting.py` | `create_cell_format()` |
| `_create_format_body()` | `operations/formatting.py` | `create_format_request()` |
| `clear_formatting()` | `operations/formatting.py` | `clear_formatting()` |
| `format_header()` | `operations/formatting.py` | `format_header()` |
| `resize()` | `operations/dimensions.py` | `resize_sheet()` |
| `resize_dimensions()` | `operations/dimensions.py` | `resize_dimensions()` |
| `freeze()` | `operations/dimensions.py` | `freeze_rows_columns()` |
| `_ensure_sheet_shape()` | `operations/dimensions.py` | `ensure_sheet_shape()` |
| `_check_sheet_shape()` | `operations/dimensions.py` | `check_sheet_shape()` |
| `reset_sheet()` | `operations/dimensions.py` | `reset_sheet()` |

**Total:** 36 methods → 36 pure functions across 6 operation files
