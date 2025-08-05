from __future__ import annotations

import atexit
import itertools
import operator
from collections import defaultdict
from collections.abc import Callable, Generator, Hashable
from typing import TYPE_CHECKING, Any

import pandas as pd
from cachetools import cachedmethod
from google.oauth2.credentials import Credentials
from googleapiclient import discovery

from googleapiutils2.sheets.misc import (
    DEFAULT_CHUNK_SIZE_BYTES,
    DEFAULT_SHEET_NAME,
    DEFAULT_SHEET_SHAPE,
    DUPE_SUFFIX,
    VERSION,
    HorizontalAlignment,
    HyperlinkDisplayType,
    InsertDataOption,
    SheetsDimension,
    SheetsFormat,
    SheetsValues,
    TextDirection,
    ValueInputOption,
    ValueRenderOption,
    VerticalAlignment,
    WrapStrategy,
)
from googleapiutils2.sheets.sheets_slice import (
    SheetSlice,
    SheetSliceT,
    SheetsRange,
    to_sheet_slice,
)
from googleapiutils2.utils import (
    EXECUTE_TIME,
    THROTTLE_TIME,
    DriveBase,
    ServiceAccountCredentials,
    Throttler,
    deep_update,
    hex_to_rgb,
    named_methodkey,
    nested_defaultdict,
    parse_file_id,
)

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import (  # type: ignore
        AddSheetRequest,
        AppendValuesResponse,
        BatchUpdateSpreadsheetRequest,
        BatchUpdateSpreadsheetResponse,
        BatchUpdateValuesRequest,
        BatchUpdateValuesResponse,
        CellData,
        CellFormat,
        ClearValuesResponse,
        Color,
        CopySheetToAnotherSpreadsheetRequest,
        DeleteSheetRequest,
        NumberFormat,
        Padding,
        Request,
        Sheet,
        SheetProperties,
        SheetsResource,
        Spreadsheet,
        TextFormat,
        UpdateValuesResponse,
        ValueRange,
    )


class Sheets(DriveBase):
    """A wrapper around the Google Sheets API.

    Args:
        creds (Credentials, optional): The credentials to use. If None, the following paths will be tried:
            - ~/auth/credentials.json
            - env var: GOOGLE_API_CREDENTIALS
        execute_time (float, optional): The time to wait between requests. Defaults to EXECUTE_TIME (0.1).
        throttle_time (float, optional): The time to wait between requests. Defaults to THROTTLE_TIME (30).
    """

    def __init__(
        self,
        creds: Credentials | ServiceAccountCredentials | None = None,
        execute_time: float = EXECUTE_TIME,
        throttle_time: float = THROTTLE_TIME,
    ):
        super().__init__(creds=creds, execute_time=execute_time, throttle_time=throttle_time)

        self.service: SheetsResource = discovery.build(  # type: ignore
            "sheets", VERSION, credentials=self.creds
        )
        self.spreadsheets: SheetsResource.SpreadsheetsResource = self.service.spreadsheets()

        self._batched_data: defaultdict[str, dict[str | Any, SheetsValues]] = defaultdict(dict)

        self._batch_update_throttler = Throttler(throttle_time)

        atexit.register(self.batch_update_remaining_auto)

    def _reset_sheet_cache(
        self,
        cache_key: str,
        spreadsheet_id: str,
        name: str | None = None,
        sheet_id: int | None = None,
    ):
        sheet_id = self._get_sheet_id(spreadsheet_id, sheet_name=name, sheet_id=sheet_id)

        key = (cache_key, spreadsheet_id, name)

        if key in self._cache:
            self._cache.pop(key)

        return sheet_id

    def _set_sheet_cache(
        self,
        cache_key: str,
        value: Any,
        spreadsheet_id: str,
        name: str | None = None,
        sheet_id: int | None = None,
    ):
        sheet_id = self._get_sheet_id(spreadsheet_id, sheet_name=name, sheet_id=sheet_id)

        key = (cache_key, spreadsheet_id, name)

        self._cache[key] = value

        return sheet_id

    def batch_update_spreadsheet(
        self,
        spreadsheet_id: str,
        body: BatchUpdateSpreadsheetRequest,
        **kwargs: Any,
    ) -> BatchUpdateSpreadsheetResponse:
        """Executes a batch update spreadsheet request.

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            body (BatchUpdateSpreadsheetRequest): The request body.
            **kwargs: Additional arguments to pass to self.sheets.batchUpdate.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        request = self.spreadsheets.batchUpdate(spreadsheetId=spreadsheet_id, body=body, **kwargs)
        return self.execute(request)  # type: ignore

    def create(
        self,
        title: str,
        sheet_names: list[str] | None = None,
        body: Spreadsheet | None = None,  # type: ignore
    ) -> Spreadsheet:
        body: Spreadsheet = nested_defaultdict(body if body else {})  # type: ignore
        sheet_names = sheet_names if sheet_names is not None else [DEFAULT_SHEET_NAME]

        body["properties"]["title"] = title  # type: ignore
        for n, sheet_name in enumerate(sheet_names):
            body["sheets"][n]["properties"]["title"] = sheet_name  # type: ignore

        body["sheets"] = list(body["sheets"].values())  # type: ignore

        return self.execute(self.spreadsheets.create(body=body))  # type: ignore

    def copy_to(
        self,
        from_spreadsheet_id: str,
        to_spreadsheet_id: str,
        from_sheet_id: int | None = None,
        from_sheet_name: str | None = None,
    ) -> Sheet:
        """Copy a sheet from one spreadsheet to another.

        Args:
            from_spreadsheet_id (str): The ID of the spreadsheet containing the sheet to copy.
            to_spreadsheet_id (str): The ID of the spreadsheet to copy the sheet to.
            from_sheet_id (int, optional): The ID of the sheet to copy. Defaults to None.
            from_sheet_name (str, optional): The name of the sheet to copy. Defaults to None.
        """
        from_spreadsheet_id, to_spreadsheet_id = (
            parse_file_id(from_spreadsheet_id),
            parse_file_id(to_spreadsheet_id),
        )
        from_sheet_id = self._get_sheet_id(
            spreadsheet_id=from_spreadsheet_id,
            sheet_name=from_sheet_name,
            sheet_id=from_sheet_id,
        )

        body: CopySheetToAnotherSpreadsheetRequest = {"destinationSpreadsheetId": to_spreadsheet_id}

        return self.execute(
            self.spreadsheets.sheets().copyTo(  # type: ignore
                spreadsheetId=from_spreadsheet_id,
                sheetId=from_sheet_id,  # type: ignore
                body=body,
            )
        )

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

    def create_range_url(self, file_id: str, sheet_slice: SheetSliceT) -> str:
        file_id = parse_file_id(file_id)

        sheet_name, range_name = sheet_slice.sheet_name, sheet_slice.range_name

        sheet_id = self._get_sheet_id(spreadsheet_id=file_id, sheet_name=sheet_name)

        return f"https://docs.google.com/spreadsheets/d/{file_id}/edit#gid={sheet_id}&range={range_name}"

    def get_spreadsheet(
        self,
        spreadsheet_id: str,
        include_grid_data: bool = False,
        range_names: SheetsRange | list[SheetsRange] | None = None,
    ) -> Spreadsheet:
        spreadsheet_id = parse_file_id(spreadsheet_id)

        range_names = range_names if range_names is not None else []
        range_names = range_names if isinstance(range_names, list) else [range_names]
        range_names = [str(range_name) for range_name in range_names]

        kwargs = {
            "spreadsheetId": spreadsheet_id,
            "includeGridData": include_grid_data,
        }
        if len(range_names) > 0:
            kwargs["ranges"] = range_names

        return self.execute(self.spreadsheets.get(**kwargs))  # type: ignore

    def _get_sheet_id(
        self,
        spreadsheet_id: str,
        sheet_name: str | None = None,
        sheet_id: int | None = None,
    ):
        """Get the ID of a sheet from a spreadsheet.
        Either the name or the ID of the sheet must be provided.
        If neither is provided or found, a ValueError is raised.

        Args:
            spreadsheet_id (str): The ID of the spreadsheet containing the sheet to get.
            name (str, optional): The name of the sheet to get. Defaults to None.
            sheet_id (int, optional): The ID of the sheet to get. Defaults to None.
        """
        if sheet_id is not None:
            return sheet_id
        elif sheet_name is None:
            raise ValueError("Either the name or the ID of the sheet must be provided.")

        def inner():
            t_name = sheet_name.strip("'") if sheet_name.startswith("'") and sheet_name.endswith("'") else sheet_name
            spreadsheet = self.get_spreadsheet(spreadsheet_id)

            for sheet in spreadsheet["sheets"]:
                properties = sheet["properties"]
                if properties["title"] == t_name:
                    return properties["sheetId"]

        key = ("sheet_id", spreadsheet_id, sheet_name)

        try:
            return self._cache[key]
        except KeyError:
            pass

        sheet_id = inner()

        if sheet_id is None:
            raise ValueError(f"Sheet {sheet_name} not found in spreadsheet.")

        self._cache[key] = sheet_id

        return sheet_id

    def has(
        self,
        spreadsheet_id: str,
        sheet_name: str | None = None,
        sheet_id: int | None = None,
    ):
        """Check if a sheet exists in a spreadsheet.
        Either the name or the ID of the sheet must be provided.

        Args:
            spreadsheet_id (str): The ID of the spreadsheet containing the sheet to check.
            name (str, optional): The name of the sheet to check. Defaults to None.
            sheet_id (int, optional): The ID of the sheet to check. Defaults to None.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)

        try:
            self._get_sheet_id(spreadsheet_id, sheet_name=sheet_name, sheet_id=sheet_id)
            return True
        except ValueError:
            return False

    def get(
        self,
        spreadsheet_id: str,
        sheet_name: str | None = None,
        sheet_id: int | None = None,
        include_grid_data: bool = False,
        range_names: SheetsRange | list[SheetsRange] | None = None,
    ) -> Sheet:
        """Get a sheet from a spreadsheet. Either the name or the ID of the sheet must be provided.

        Args:
            spreadsheet_id (str): The ID of the spreadsheet containing the sheet to get.
            name (str, optional): The name of the sheet to get. Defaults to None.
            sheet_id (int, optional): The ID of the sheet to get. Defaults to None.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        spreadsheet = self.get_spreadsheet(
            spreadsheet_id=spreadsheet_id,
            include_grid_data=include_grid_data,
            range_names=range_names,
        )
        sheet_id = self._get_sheet_id(spreadsheet_id, sheet_name=sheet_name, sheet_id=sheet_id)

        for sheet in spreadsheet["sheets"]:
            if sheet["properties"]["sheetId"] == sheet_id:
                return sheet

        raise ValueError(f"Sheet {sheet_name or sheet_id} not found in spreadsheet.")

    def rename(
        self,
        spreadsheet_id: str,
        new_sheet_name: str,
        old_sheet_name: str | None = None,
        sheet_id: int | None = None,
    ):
        """Rename a sheet in a spreadsheet.

        Args:
            spreadsheet_id (str): The ID of the spreadsheet containing the sheet to rename.
            new_sheet_name (str): The new name for the sheet.
            old_sheet_name (str, optional): The current name of the sheet to rename. Defaults to None.
            sheet_id (int, optional): The ID of the sheet to rename. Defaults to None.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        sheet_id = self._get_sheet_id(spreadsheet_id, sheet_name=old_sheet_name, sheet_id=sheet_id)

        body: BatchUpdateSpreadsheetRequest = {
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {"sheetId": sheet_id, "title": new_sheet_name},  # type: ignore
                        "fields": "title",
                    }
                }
            ]
        }
        return self.batch_update_spreadsheet(spreadsheet_id=spreadsheet_id, body=body)

    def add(
        self,
        spreadsheet_id: str,
        sheet_names: str | list[str],
        row_count: int = DEFAULT_SHEET_SHAPE[0],
        col_count: int = DEFAULT_SHEET_SHAPE[1],
        index: int | None = None,
        ignore_existing: bool = True,
    ):
        """Add one or more sheets to a spreadsheet.

        Args:
            spreadsheet_id (str): The ID of the spreadsheet to add sheets to.
            names (str | list[str]): The name(s) of the sheet(s) to add.
            row_count (int, optional): The number of rows in the new sheet(s). Defaults to DEFAULT_SHEET_SHAPE[0].
            col_count (int, optional): The number of columns in the new sheet(s). Defaults to DEFAULT_SHEET_SHAPE[1].
            index (int, optional): The index at which to insert the sheet(s). Defaults to None.
            ignore_existing (bool, optional): Whether to ignore sheets that already exist. Defaults to True.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)

        if isinstance(sheet_names, str):
            sheet_names = [sheet_names]
        sheet_names = [
            name for name in sheet_names if not ignore_existing or not self.has(spreadsheet_id, sheet_name=name)
        ]

        if len(sheet_names) == 0:
            return

        def make_body(name: str):
            body: SheetProperties = {
                "title": name,
                "gridProperties": {
                    "rowCount": row_count,
                    "columnCount": col_count,
                },
            }
            if index is not None:
                body["index"] = index

            request: AddSheetRequest = {
                "properties": body,
            }
            return request

        body: BatchUpdateSpreadsheetRequest = {
            "requests": [
                {
                    "addSheet": make_body(name),
                }
                for name in sheet_names
            ],
        }

        return self.batch_update_spreadsheet(
            spreadsheet_id=spreadsheet_id,
            body=body,
        )

    def delete(
        self,
        spreadsheet_id: str,
        sheet_names: str | list[str],
        ignore_not_existing: bool = True,
    ):
        """Deletes a sheet from a spreadsheet.

        Args:
            spreadsheet_id (str): The ID of the spreadsheet to delete the sheet from.
            name (str, optional): The name of the sheet to delete. Defaults to None.
            sheet_id (int, optional): The ID of the sheet to delete. Defaults to None.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)

        if isinstance(sheet_names, str):
            sheet_names = [sheet_names]
        sheet_names = [
            name for name in sheet_names if not ignore_not_existing or self.has(spreadsheet_id, sheet_name=name)
        ]

        if len(sheet_names) == 0:
            return

        def make_body(name: str):
            sheet_id = self._get_sheet_id(spreadsheet_id, sheet_name=name)

            key = ("sheet_id", spreadsheet_id, name)

            if key in self._cache:
                self._cache.pop(key)

            body: DeleteSheetRequest = {
                "sheetId": sheet_id,
            }

            request = body
            return request

        body: BatchUpdateSpreadsheetRequest = {
            "requests": [
                {
                    "deleteSheet": make_body(name),
                }
                for name in sheet_names
            ],
        }

        return self.batch_update_spreadsheet(
            spreadsheet_id=spreadsheet_id,
            body=body,
        )

    def values(
        self,
        spreadsheet_id: str,
        range_name: SheetsRange = DEFAULT_SHEET_NAME,
        value_render_option: ValueRenderOption = ValueRenderOption.unformatted,
        **kwargs: Any,
    ) -> ValueRange:
        """Get values from a spreadsheet within a range.

        Args:
            spreadsheet_id (str): The spreadsheet ID.
            range_name (SheetsRange, optional): The range to get values from. Defaults to DEFAULT_SHEET_NAME.
            value_render_option (ValueRenderOption, optional): The value render option. Defaults to ValueRenderOption.unformatted.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        sheet_slice = to_sheet_slice(range_name)

        return self.execute(
            self.spreadsheets.values().get(
                spreadsheetId=spreadsheet_id,
                range=str(sheet_slice),
                valueRenderOption=value_render_option.value,
                **kwargs,
            )
        )  # type: ignore

    def value(
        self,
        spreadsheet_id: str,
        range_name: SheetsRange = DEFAULT_SHEET_NAME,
        value_render_option: ValueRenderOption = ValueRenderOption.unformatted,
        **kwargs: Any,
    ) -> Any:
        """Get a single value from a spreadsheet within a range.

        Args:
            spreadsheet_id (str): The spreadsheet ID.
            range_name (SheetsRange, optional): The range to get values from. Defaults to DEFAULT_SHEET_NAME.
            value_render_option (ValueRenderOption, optional): The value render option. Defaults to ValueRenderOption.unformatted.
        """
        return self.values(spreadsheet_id, range_name, value_render_option, **kwargs).get("values", [[]])[0][0]

    @staticmethod
    def _add_dupe_suffix(df: pd.DataFrame, suffix: str = DUPE_SUFFIX):
        """
        Add suffix to duplicate columns in a DataFrame and return modified DataFrame and header

        Args:
            df: DataFrame to process
            suffix: Suffix to append to duplicate columns (default: '__dupe__')

        Returns:
            tuple[pd.DataFrame, list[str]]: (Modified DataFrame, list of new column names)
        """
        cols = df.columns.tolist()
        new_cols: list = []
        seen: dict = {}

        for _i, col in enumerate(cols):
            if col in seen:
                seen[col] += 1
                new_cols.append(f"{col}{suffix}{seen[col]}")
            else:
                seen[col] = 0
                new_cols.append(col)

        df.columns = new_cols  # type: ignore

        return df

    def _dict_to_values_align_columns(
        self,
        spreadsheet_id: str,
        sheet_slice: SheetSliceT,
        rows: list[dict[SheetsRange, Any]],
        align_columns: bool = True,
        insert_header: bool = True,
        update: bool = True,
    ) -> list[list[Any]] | None:
        """Transforms a list of dictionaries into a list of lists, aligning the columns with the header.
        If new columns were added, the header is appended to the right; the header of the sheet is updated.
        For existing columns not present in the input data, the original values are preserved.

        Args:
        spreadsheet_id (str): The spreadsheet ID.
        sheet_slice (SheetSliceT): The range to update.
        rows (list[dict[SheetsRange, Any]]): The rows to update.
        align_columns (bool, optional): Whether to align the columns with the header. Defaults to True.
        insert_header (bool, optional): Whether to insert the header if the range starts at the first row. Defaults to True.
        update (bool, optional): Whether to update the values in the sheet. Defaults to True.

        Returns:
            list[list[Any]]: The aligned values with original data preserved where appropriate.
        """

        if not align_columns:
            return [list(row.values()) for row in rows]

        insert_header = insert_header and (sheet_slice.rows.start == 1)

        sheet_name = sheet_slice.sheet_name

        # Get existing header and data
        header = self.header(spreadsheet_id, sheet_name)
        header = pd.Index(header).astype(str)

        # Get current values
        current_values: list = []
        if (
            update
            # Check if the slice fits within the current shape;
            # if not, skip
            and self._check_sheet_shape(
                sheet_slice=sheet_slice,
                shape=self.shape(spreadsheet_id, sheet_name),
            )[0]
        ):
            current_values = self.values(
                spreadsheet_id=spreadsheet_id,
                range_name=sheet_slice,
                value_render_option=ValueRenderOption.formula,
            ).get("values", [])

        # Create DataFrame from current values if they exist
        current_df: pd.DataFrame = None  # type: ignore
        if len(current_values) > 0:
            current_df = pd.DataFrame(current_values)  # type: ignore

            if insert_header:
                current_df.columns = current_df.iloc[0].astype(str)  # type: ignore
                current_df = current_df.drop(0).reset_index(drop=True)  # type: ignore
                current_df = self._add_dupe_suffix(current_df)
            else:
                # ensure the header is padded with empty strings to match the current data
                if len(header) < current_df.shape[1]:
                    header = header.append(pd.Index([""] * (current_df.shape[1] - len(header))))
                    current_df.columns = header
                # ensure the current data is padded with nans to match the header
                elif len(header) > current_df.shape[1]:
                    current_df.columns = header[: current_df.shape[1]]
                    current_df = current_df.reindex(columns=header)
                else:
                    current_df.columns = header
        else:
            current_df = pd.DataFrame()

        current_df = self._add_dupe_suffix(current_df)

        # Create DataFrame from new data and handle dupes
        new_df = pd.DataFrame(rows)
        new_df = self._add_dupe_suffix(new_df)

        # Convert header to list and handle dupes
        header = pd.DataFrame(columns=header)
        header = self._add_dupe_suffix(header)
        header = header.columns.tolist()

        # Check for new columns
        if len(diff := new_df.columns.difference(header)):
            header = header + list(diff)
            header_slc = SheetSlice[sheet_name, 1, ...]
            self.update(
                spreadsheet_id,
                header_slc,
                [header],
            )
            # update the header cache
            self._set_sheet_cache(
                cache_key="header",
                value=header,
                spreadsheet_id=spreadsheet_id,
                name=sheet_name,
            )

        for col in header:
            # If col doesn't exist in either df, create blank column
            if col not in current_df.columns and col not in new_df.columns:
                new_df[col] = ""
                continue

            # Skip if col already exists in new_df
            if col in new_df.columns:
                continue

            new_df[col] = current_df[col]

        # Reorder columns to match header
        new_df = new_df.reindex(columns=header)
        current_df = current_df.reindex(columns=header)

        # Strip dupe suffixes at the end
        new_df.columns = new_df.columns.str.replace(rf"{DUPE_SUFFIX}\d+", "", regex=True)
        current_df.columns = new_df.columns

        # Convert to list format, replacing None/NaN with empty string
        values: list[list] = new_df.fillna("").values.tolist()  # type: ignore

        if insert_header:
            values.insert(0, list(new_df.columns))

        # check to see if the current values (of the df) are the same as the new values
        if current_df.equals(new_df):
            return None

        return values

    def _process_sheets_values(
        self,
        spreadsheet_id: str,
        sheet_slice: SheetSliceT,
        values: SheetsValues,
        align_columns: bool = True,
        insert_header: bool = True,
        update: bool = True,
    ) -> list[list[Any]] | None:
        if all(isinstance(value, dict) for value in values):
            return self._dict_to_values_align_columns(
                spreadsheet_id=spreadsheet_id,
                sheet_slice=sheet_slice,
                rows=values,  # type: ignore
                align_columns=align_columns,
                insert_header=insert_header,
                update=update,
            )
        else:
            return values  # type: ignore

    def _check_sheet_shape(
        self,
        sheet_slice: SheetSliceT,
        shape: tuple[int, int],
    ) -> tuple[bool, tuple[int, int]]:
        """Check if a sheet slice fits within the given sheet shape.

        Args:
            sheet_slice (SheetSliceT): The sheet slice to check
            shape (tuple[int, int]): The current shape of the sheet (rows, cols)

        Returns:
            tuple[bool, tuple[int, int]]: A tuple containing:
                - bool: Whether the slice fits within the current shape
                - tuple[int, int]: The minimum shape needed to fit the slice
        """
        current_rows, current_cols = shape

        needed_rows = sheet_slice.rows.stop
        needed_rows = needed_rows if needed_rows is not ... else current_rows

        needed_cols = sheet_slice.columns.stop
        needed_cols = needed_cols if needed_cols is not ... else current_cols

        row_fit = needed_rows <= current_rows
        col_fit = needed_cols <= current_cols

        fits = row_fit and col_fit

        # this should grow by 1.25x the current size
        GROWTH_FACTOR = 1.25

        needed_rows = max(needed_rows, int(current_rows * GROWTH_FACTOR))
        needed_cols = max(needed_cols, int(current_cols * GROWTH_FACTOR))

        needed_shape = (needed_rows, needed_cols)

        return fits, needed_shape

    def _ensure_sheet_shape(self, spreadsheet_id: str, range_names: list[SheetsRange]):
        """For a given sheet, ensure that every range is within the sheet's size.
        If it's not, resize the sheet to fit the ranges.

        Args:
            spreadsheet_id (str): The spreadsheet ID.
            range_names (List[SheetsRange]): The ranges to check.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)

        sheet_slices = [to_sheet_slice(range_name) for range_name in range_names]
        sheet_names = {sheet_slice.sheet_name for sheet_slice in sheet_slices}

        # Ensure each sheet exists:
        self.add(spreadsheet_id, sheet_names=sheet_names)  # type: ignore

        shapes = {sheet_name: self.shape(spreadsheet_id, sheet_name) for sheet_name in sheet_names}
        sheet_slices = [sheet_slice.with_shape(shapes[sheet_slice.sheet_name]) for sheet_slice in sheet_slices]

        def resize_sheet(
            sheet_slice: SheetSliceT,
        ):
            sheet_name = sheet_slice.sheet_name

            fits, (rows, cols) = self._check_sheet_shape(
                sheet_slice=sheet_slice,
                shape=shapes[sheet_slice.sheet_name],
            )
            if fits:
                return

            self.resize(spreadsheet_id, sheet_name, rows=rows, cols=cols)

            shape = (rows, cols)
            self._set_sheet_cache(
                cache_key="shape",
                value=shape,
                spreadsheet_id=spreadsheet_id,
                name=sheet_name,
            )

        for sheet_slice in sheet_slices:
            resize_sheet(
                sheet_slice=sheet_slice,
            )

    @staticmethod
    def _chunk_range(
        range_name: SheetsRange,
        rows: int,
        pred: Callable[[int, int | None], bool],
    ) -> Generator[tuple[int, SheetSliceT], None, None]:
        sheet_slice = to_sheet_slice(range_name)

        start_row = sheet_slice.rows.start
        end_row = start_row

        for i in range(rows):
            if pred(start_row, i):
                yield (
                    i,
                    SheetSlice[
                        sheet_slice.sheet_name,
                        slice(start_row, end_row),
                        sheet_slice.columns,
                    ],
                )

                start_row = end_row + 1

            end_row += 1

        if start_row < end_row:
            yield (
                rows - 1,
                SheetSlice[
                    sheet_slice.sheet_name,
                    slice(start_row, rows),
                    sheet_slice.columns,
                ],
            )

    @staticmethod
    def _flatten_ranges(
        range_names: list[SheetsRange],
    ) -> list[tuple[tuple[int, int], SheetSliceT]]:
        """Flatten a list of ranges into a list of contiguous ranges, and the start and stop indexes of each range."""

        sheet_slices = [to_sheet_slice(range_name) for range_name in range_names]
        sheet_slices = sorted(sheet_slices, key=lambda x: x.rows.start)

        sheet_slice = sheet_slices[0]

        start = sheet_slices[0].rows.start
        stop = sheet_slices[0].rows.stop

        start_ix = 0
        stop_ix = 0

        flattened_ranges = []

        for i, t_sheet_slice in enumerate(sheet_slices[1:]):
            # If the sheet_slice is contiguous row-wise,
            # and equivalent column-wise, extend the stop index
            if (
                stop is not ...
                and t_sheet_slice.rows.start == stop + 1
                and t_sheet_slice.columns == sheet_slice.columns
            ):
                stop = t_sheet_slice.rows.stop
                stop_ix += 1
            else:
                flat_sheet_slice = SheetSlice[
                    sheet_slice.sheet_name,
                    slice(start, stop),
                    sheet_slice.columns,
                ]

                flattened_ranges.append(((start_ix, stop_ix + 1), flat_sheet_slice))

                sheet_slice = t_sheet_slice

                start = t_sheet_slice.rows.start
                stop = t_sheet_slice.rows.stop

                start_ix = i + 1
                stop_ix = i + 1

        flat_sheet_slice = SheetSlice[
            sheet_slice.sheet_name,
            slice(start, stop),
            sheet_slice.columns,
        ]
        flattened_ranges.append(((start_ix, stop_ix + 1), flat_sheet_slice))

        return flattened_ranges

    @staticmethod
    def _flatten_value_ranges(
        range_names: list[SheetsRange],
        values: list[SheetsValues],
    ):
        flat_ranges = Sheets._flatten_ranges(range_names)

        flat_data: dict[SheetsRange, SheetsValues] = {}

        for (start, stop), sheet_slice in flat_ranges:
            if stop > start + 1:
                flat_data[sheet_slice] = list(itertools.chain(*values[start:stop]))
            else:
                flat_data[sheet_slice] = values[start]

        return flat_data

    @staticmethod
    def _get_row_size(row: list[Any]) -> int:
        return sum(len(str(cell)) for cell in row)

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
        """Updates a range of values in chunks to avoid API timeouts.

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            range_name (SheetsRange): The range to update.
            values (SheetsValues): The values to update.
            value_input_option (ValueInputOption): How input data should be interpreted.
            align_columns (bool): Whether to align columns with header.
            chunk_size_bytes (int): Maximum size in bytes for each chunk.

        Returns:
            UpdateValuesResponse | None: Response from the update, or None if no updates made.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        sheet_slice = to_sheet_slice(range_name)

        # Process values with column alignment if needed
        processed_values = self._process_sheets_values(
            spreadsheet_id=spreadsheet_id,
            sheet_slice=sheet_slice,
            values=values,
            align_columns=align_columns,
            update=update,
        )

        if not processed_values or processed_values is None:
            return None

        sheet_slice = sheet_slice.with_shape((len(processed_values), len(processed_values[0])))
        # Estimate total size
        total_size = sum(self._get_row_size(row) for row in processed_values)

        # If under chunk size, use standard update
        if chunk_size_bytes is None or total_size <= chunk_size_bytes:
            self._ensure_sheet_shape(
                spreadsheet_id=spreadsheet_id,
                range_names=[sheet_slice],
            )
            request = self.spreadsheets.values().update(
                spreadsheetId=spreadsheet_id,
                range=str(sheet_slice),
                body={"values": processed_values},
                valueInputOption=value_input_option.value,
            )
            return self.execute(request)  # type: ignore

        # Split into chunks
        current_chunk: list[list[Any]] = []
        current_size = 0

        def chunk_size_pred(start_row, i):
            nonlocal current_size, current_chunk

            current_size += self._get_row_size(processed_values[i])
            current_chunk.append(processed_values[i])

            return current_size > chunk_size_bytes

        for _, t_sheet_slice in self._chunk_range(
            range_name=sheet_slice,
            rows=len(processed_values),
            pred=chunk_size_pred,
        ):
            self._batch_update(
                spreadsheet_id=spreadsheet_id,
                data={
                    t_sheet_slice: current_chunk,
                },
                value_input_option=value_input_option,
                align_columns=align_columns,
                ensure_shape=True,
                chunk_size_bytes=None,
                update=update,
            )
            current_size = 0
            current_chunk = []

        return None

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

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            range_name (SheetsRange): The range to update.
            values (SheetsValues): The values to update.
            value_input_option (ValueInputOption, optional): How the input data should be interpreted.
            align_columns (bool, optional): Whether to align the columns with the keys of the first row.
            ensure_shape (bool, optional): Whether to ensure the sheet has enough rows/columns.
            chunk_size_bytes (int, optional): Maximum size in bytes for each chunk. If None, no chunking is done.
            keep_values (bool, optional): Whether to keep the current sheets' values and dynamically update in-place.

        Returns:
            UpdateValuesResponse | None: Response from the update, or None if no updates made
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        values = values if values is not None else [[]]

        if ensure_shape:
            self._ensure_sheet_shape(spreadsheet_id=spreadsheet_id, range_names=[range_name])

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

    def _batch_update(
        self,
        spreadsheet_id: str,
        data: dict[SheetsRange, SheetsValues],
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        align_columns: bool = True,
        ensure_shape: bool = True,
        chunk_size_bytes: int | None = None,
        update: bool = True,
    ) -> BatchUpdateValuesResponse | None:
        spreadsheet_id = parse_file_id(spreadsheet_id)

        flat_data = self._flatten_value_ranges(
            range_names=list(data.keys()),
            values=list(data.values()),
        )

        flat_range_names: list = []
        flat_values: list = []

        for range_name, values in flat_data.items():
            sheet_slice = to_sheet_slice(range_name)
            values = self._process_sheets_values(
                spreadsheet_id=spreadsheet_id,
                sheet_slice=sheet_slice,
                values=values,
                align_columns=align_columns,
                update=update,
            )
            if values is None:
                continue

            sheet_slice = sheet_slice.with_shape((len(values), len(values[0])))

            flat_range_names.append(str(sheet_slice))
            flat_values.append(values)

        if len(flat_range_names) == 0:
            return None

        # Flatten once more to handle ellipsis expansion
        flat_data = self._flatten_value_ranges(
            range_names=flat_range_names,
            values=flat_values,
        )
        new_data: list[ValueRange] = [
            {
                "range": str(range_name),
                "values": values,
            }
            for range_name, values in flat_data.items()
        ]  # type: ignore

        if ensure_shape:
            self._ensure_sheet_shape(
                spreadsheet_id=spreadsheet_id,
                range_names=[value_range["range"] for value_range in new_data],
            )

        if chunk_size_bytes is not None:
            # Make successive calls to _update_chunked:
            for value_range in new_data:
                self._update_chunked(
                    spreadsheet_id=spreadsheet_id,
                    range_name=value_range["range"],
                    values=value_range["values"],
                    value_input_option=value_input_option,
                    align_columns=align_columns,
                    ensure_shape=ensure_shape,
                    chunk_size_bytes=chunk_size_bytes,
                    update=update,
                )
            return None
        else:
            body: BatchUpdateValuesRequest = {
                "valueInputOption": value_input_option.value,
                "data": new_data,
            }

            request = self.spreadsheets.values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body,
            )

            return self.execute(request)  # type: ignore

    def batch_update(
        self,
        spreadsheet_id: str,
        data: dict[SheetsRange, SheetsValues],
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        align_columns: bool = True,
        batch_size: int | None = None,
        ensure_shape: bool = False,
        chunk_size_bytes: int | None = None,
        keep_values: bool = True,
    ):
        """Updates a series of range values in a spreadsheet. Much faster version of calling `update` multiple times.
        See `update` for more details.

        If the `batch_size` is None, all updates will be batched together. Otherwise, the updates will be batched by the following
        rules:
        -   If the number of updates is greater than `batch_size` AND
        -   If the time between the first update and the last update is greater than `THROTTLE_TIME`.

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            data (dict[SheetsRange, SheetsValues]): The data to update.
            value_input_option (ValueInputOption, optional): How the input data should be interpreted. Defaults to ValueInputOption.user_entered.
            align_columns (bool, optional): Whether to align the columns of the spreadsheet with the keys of the first row of the values. Defaults to True.
            batch_size (int | None, optional): The number of updates to batch together. If None, all updates will be batched together. Defaults to None.
            ensure_shape (bool, optional): Whether to ensure the sheet has enough rows/columns. Defaults to False.
            chunk_size_bytes (int, optional): Maximum size in bytes for each chunk. If None, no chunking is done. Defaults to None.
            keep_values (bool, optional): Whether to keep the current sheets' values and dynamically update in-place. Defaults to True.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)

        if batch_size is None:
            return self._batch_update(
                spreadsheet_id=spreadsheet_id,
                data=data,
                value_input_option=value_input_option,
                align_columns=align_columns,
                ensure_shape=ensure_shape,
                chunk_size_bytes=chunk_size_bytes,
                update=keep_values,
            )

        batched_data = self._batched_data[spreadsheet_id]

        if data is not None:
            self._batched_data[spreadsheet_id] |= data

        if len(batched_data) >= batch_size and not (self._batch_update_throttler.dt() > 0):
            self._batch_update(
                spreadsheet_id=spreadsheet_id,
                data=self._batched_data[spreadsheet_id],
                value_input_option=value_input_option,
                align_columns=align_columns,
                ensure_shape=ensure_shape,
                chunk_size_bytes=chunk_size_bytes,
                update=keep_values,
            )
            self._batched_data[spreadsheet_id].clear()
            self._batch_update_throttler.reset()
        else:
            return None

    def batched_update_remaining(self, spreadsheet_id: str):
        """Updates any remaining batched data that's been left over from previous calls to `batch_update`."""
        spreadsheet_id = parse_file_id(spreadsheet_id)
        batched_data = self._batched_data[spreadsheet_id]

        if len(batched_data) == 0:
            return None

        res = self._batch_update(
            spreadsheet_id=spreadsheet_id,
            data=batched_data,
        )

        self._batched_data[spreadsheet_id].clear()

        return res

    def batch_update_remaining_auto(self):
        """Updates any remaining batched data that's been left over from previous calls to `batch_update`."""
        for spreadsheet_id in self._batched_data:
            self.batched_update_remaining(spreadsheet_id)

    def append(
        self,
        spreadsheet_id: str,
        range_name: SheetsRange = DEFAULT_SHEET_NAME,
        values: SheetsValues | None = None,
        insert_data_option: InsertDataOption = InsertDataOption.overwrite,
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        align_columns: bool = True,
    ) -> AppendValuesResponse | None:
        """Appends values to a spreadsheet. Like `update`, but searches for the next available range to append to.

        The next available range is determined by the last **cleared/deleted** row and column set.
        It's not enough to just clear the data therein with the delete key.

        This means rows will be added to the spreadsheet if the input values are longer than the
        number of existing rows. See: https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values/append

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            range_name (SheetsRange): The range to update.
            values (list[list[Any]]): The values to append.
            insert_data_option (InsertDataOption, optional): How the input data should be inserted. Defaults to InsertDataOption.overwrite.
            value_input_option (ValueInputOption, optional): How the input data should be interpreted. Defaults to ValueInputOption.user_entered.
            align_columns (bool, optional): Whether to align the columns of the spreadsheet with the keys of the first row of the values. Defaults to True.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        sheet_slice = to_sheet_slice(range_name)
        values = values if values is not None else [[]]

        body: ValueRange = {
            "values": self._process_sheets_values(
                spreadsheet_id=spreadsheet_id,
                sheet_slice=sheet_slice,
                values=values,
                align_columns=align_columns,
                insert_header=False,
                update=False,
            )  # type: ignore
        }  # type: ignore

        # Filter out any None values
        if body["values"] is None:
            return None

        sheet_slice = sheet_slice.with_shape((len(body["values"]), len(body["values"][0])))

        request = self.spreadsheets.values().append(
            spreadsheetId=spreadsheet_id,
            range=str(sheet_slice),
            body=body,
            insertDataOption=insert_data_option.value,
            valueInputOption=value_input_option.value,
        )

        return self.execute(request)  # type: ignore

    def get_append_range(
        self,
        spreadsheet_id: str,
        range_name: SheetsRange = DEFAULT_SHEET_NAME,
    ) -> SheetSliceT:
        """Get the range wherein Google Sheets would append data.

        This is done by first appending a null value to the sheet, checking the range of the appended value, and then deleting it.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        sheet_slice = to_sheet_slice(range_name)

        res = self.append(
            spreadsheet_id=spreadsheet_id,
            range_name=sheet_slice,
            values=[[]],
            value_input_option=ValueInputOption.user_entered,
            align_columns=False,
        )

        if res is None:
            return sheet_slice

        appended_range = res["updates"]["updatedRange"]  # type: ignore
        appended_range_slc = to_sheet_slice(appended_range)  # type: ignore

        self.clear(
            spreadsheet_id=spreadsheet_id,
            range_name=appended_range,
        )

        return appended_range_slc  # type: ignore

    def clear(
        self,
        spreadsheet_id: str,
        range_name: SheetsRange = DEFAULT_SHEET_NAME,
    ) -> ClearValuesResponse:
        """Clears a range of values in a spreadsheet.

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            range_name (SheetsRange): The range to clear.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        sheet_slice = to_sheet_slice(range_name)

        request = self.spreadsheets.values().clear(spreadsheetId=spreadsheet_id, range=str(sheet_slice))

        return self.execute(request)  # type: ignore

    def resize(
        self,
        spreadsheet_id: str,
        sheet_name: SheetsRange = DEFAULT_SHEET_NAME,
        rows: int = DEFAULT_SHEET_SHAPE[0],
        cols: int = DEFAULT_SHEET_SHAPE[1],
    ):
        """Resizes a sheet to the given number of rows and columns.

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            sheet_name (str): The name of the sheet to resize.
            rows (int, optional): The number of rows to resize to. Defaults to DEFAULT_SHEET_SHAPE[0].
            cols (int, optional): The number of columns to resize to. Defaults to DEFAULT_SHEET_SHAPE[1].
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        sheet_slice = to_sheet_slice(sheet_name)
        sheet_name = sheet_slice.sheet_name

        sheet_id = self.get(spreadsheet_id, sheet_name=sheet_name)["properties"]["sheetId"]
        body: BatchUpdateSpreadsheetRequest = {
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet_id,
                            "gridProperties": {
                                "rowCount": rows,
                                "columnCount": cols,
                            },
                        },
                        "fields": "gridProperties.rowCount,gridProperties.columnCount",
                    }
                }
            ]
        }
        return self.batch_update_spreadsheet(
            spreadsheet_id=spreadsheet_id,
            body=body,
        )

    def clear_formatting(
        self,
        spreadsheet_id: str,
        sheet_name: SheetsRange = DEFAULT_SHEET_NAME,
    ):
        """Clears all formatting from a sheet.

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            sheet_name (str): The name of the sheet to clear formatting from.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        sheet_slice = to_sheet_slice(sheet_name)
        sheet_name = sheet_slice.sheet_name

        sheet_id = self.get(spreadsheet_id, sheet_name=sheet_name)["properties"]["sheetId"]
        body: BatchUpdateSpreadsheetRequest = {
            "requests": [
                {
                    "updateCells": {
                        "range": {
                            "sheetId": sheet_id,
                        },
                        "fields": "userEnteredFormat",
                    }
                }
            ]
        }
        return self.batch_update_spreadsheet(
            spreadsheet_id=spreadsheet_id,
            body=body,
        )

    def reset_sheet(
        self,
        spreadsheet_id: str,
        sheet_name: SheetsRange = DEFAULT_SHEET_NAME,
        resize: bool = True,
        preserve_header: bool = False,
    ):
        """Resets a sheet back to a default state. This includes:
            - clearing all values
            - clearing all formatting
            - resizing the sheet to 26 columns and 1000 rows

        If `preserve_header` is True, the first row of the sheet will be *mostly* preserved.

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            sheet_name (str): The name of the sheet to reset.
            resize (bool, optional): Whether to resize the sheet back to its default column and row counts. Defaults to True.
            preserve_header (bool, optional): Whether to preserve the first row of the sheet. Defaults to False.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        sheet_slice = to_sheet_slice(sheet_name)
        sheet_name = sheet_slice.sheet_name

        header_slice = SheetSlice[sheet_name, 1, ...]

        header = self.values(spreadsheet_id=spreadsheet_id, range_name=header_slice).get("values", [])
        header_fmt = self.get_format(spreadsheet_id=spreadsheet_id, range_name=header_slice)

        self.clear(
            spreadsheet_id=spreadsheet_id,
            range_name=sheet_name,
        )

        # reset the sheet to the default shape
        if resize:
            cols = (
                max(len(header), DEFAULT_SHEET_SHAPE[1]) if len(header) and preserve_header else DEFAULT_SHEET_SHAPE[1]
            )

            self.resize(
                spreadsheet_id,
                sheet_name=sheet_name,
                rows=DEFAULT_SHEET_SHAPE[0],
                cols=cols,
            )

        # reset the columns to the default width
        self.resize_dimensions(
            spreadsheet_id,
            sheet_name=sheet_name,
            dimension=SheetsDimension.columns,
        )

        self.clear_formatting(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
        )

        if preserve_header and len(header):
            self.update(
                spreadsheet_id=spreadsheet_id,
                range_name=header_slice,
                values=header,
            )
            self.format(
                spreadsheet_id=spreadsheet_id,
                range_names=header_slice,
                sheets_format=header_fmt[0],
                update=True,
            )
        else:
            self._reset_sheet_cache(cache_key="header", spreadsheet_id=spreadsheet_id, name=sheet_name)

    @staticmethod
    def _create_format_body(
        sheet_id: int,
        start_row: int,
        start_col: int,
        cell_format: CellFormat,
        end_row: int | None = None,
        end_col: int | None = None,
    ) -> Request:
        """Creates a batch update request body for formatting a range of cells.
        The ranges herein are 1-indexed.

        Args:
            sheet_id (int): The ID of the sheet to format.
            start_row (int): The starting row of the range to format.
            start_col (int): The starting column of the range to format.
            cell_format (CellFormat): The format to apply to the range.
            end_row (int, optional): The ending row of the range to format. Defaults to None.
            end_col (int, optional): The ending column of the range to format. Defaults to None.
        """
        end_row = end_row if end_row is not None else start_row
        end_col = end_col if end_col is not None else start_col

        if start_row - 1 < 0 or start_col - 1 < 0:
            raise ValueError("The row and column indices must be greater than 0.")

        return {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": start_row - 1,
                    "endRowIndex": end_row,
                    "startColumnIndex": start_col - 1,
                    "endColumnIndex": end_col,
                },
                "cell": {
                    "userEnteredFormat": cell_format,
                },
                "fields": "userEnteredFormat",
            }
        }

    @staticmethod
    def _create_cell_format(
        bold: bool | None = None,
        italic: bool | None = None,
        underline: bool | None = None,
        strikethrough: bool | None = None,
        font_size: int | None = None,
        font_family: str | None = None,
        text_color: Color | str | None = None,
        background_color: Color | str | None = None,
        padding: Padding | int | None = None,
        horizontal_alignment: HorizontalAlignment | None = None,
        vertical_alignment: VerticalAlignment | None = None,
        wrap_strategy: WrapStrategy | None = None,
        text_direction: TextDirection | None = None,
        hyperlink_display_type: HyperlinkDisplayType | None = None,
        number_format: NumberFormat | None = None,
        cell_format: CellFormat | None = None,
    ) -> CellFormat:
        text_format: TextFormat = {}
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
        if text_color is not None:
            text_format["foregroundColor"] = hex_to_rgb(text_color) if isinstance(text_color, str) else text_color

        cell_format_dict: CellFormat = {}
        if background_color is not None:
            cell_format_dict["backgroundColor"] = (
                hex_to_rgb(background_color) if isinstance(background_color, str) else background_color
            )

        if padding is not None:
            padding_dict: Padding = {}
            if isinstance(padding, int):
                padding_dict = {
                    "top": padding,
                    "bottom": padding,
                    "left": padding,
                    "right": padding,
                }
            elif isinstance(padding, dict):
                padding_dict = padding
            cell_format_dict["padding"] = padding_dict

        if horizontal_alignment is not None:
            cell_format_dict["horizontalAlignment"] = horizontal_alignment.value

        if vertical_alignment is not None:
            cell_format_dict["verticalAlignment"] = vertical_alignment.value

        if wrap_strategy is not None:
            cell_format_dict["wrapStrategy"] = wrap_strategy.value

        if text_direction is not None:
            cell_format_dict["textDirection"] = text_direction.value

        if hyperlink_display_type is not None:
            cell_format_dict["hyperlinkDisplayType"] = hyperlink_display_type.value

        if number_format is not None:
            cell_format_dict["numberFormat"] = number_format

        if cell_format is not None:
            cell_format_dict.update(cell_format)

        return {"textFormat": text_format, **cell_format_dict}  # type: ignore

    # TODO! fix hyperlink formatting update - does not preserve extant hyperlinks
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
        text_color: Color | str | None = None,
        background_color: Color | str | None = None,
        padding: Padding | int | None = None,
        horizontal_alignment: HorizontalAlignment | None = None,
        vertical_alignment: VerticalAlignment | None = None,
        wrap_strategy: WrapStrategy | None = None,
        text_direction: TextDirection | None = None,
        hyperlink_display_type: HyperlinkDisplayType | None = None,
        number_format: NumberFormat | None = None,
        cell_format: CellFormat | None = None,
        sheets_format: SheetsFormat | None = None,
    ):
        """Formats a range of cells in a spreadsheet.

        If a SheetsFormat object is provided, this will take precedence over the other arguments.
        A SheetsFormat object contains formatting and dimension information:
            -  column_sizes: a list of column sizes
            -  row_sizes: a list of row sizes
            -  cell_format: a CellFormat object containing formatting information

        This function works bidirectionally with `get_format`.

        See "CellFormat" in the Sheets API for more details.
        See the formatting API for more details: https://developers.google.com/sheets/api/guides/formats

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            range_names (list[SheetsRange] | SheetsRange): The ranges to update.
            ...
            sheets_format (SheetsFormat, optional): A SheetsFormat object containing the formatting to apply. Defaults to None.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)

        if not isinstance(range_names, list):
            range_names = [range_names]

        sheets_format = sheets_format if sheets_format is not None else SheetsFormat()

        cell_format = self._create_cell_format(
            bold=bold,
            italic=italic,
            underline=underline,
            strikethrough=strikethrough,
            font_size=font_size,
            font_family=font_family,
            text_color=text_color,
            background_color=background_color,
            padding=padding,
            horizontal_alignment=horizontal_alignment,
            vertical_alignment=vertical_alignment,
            wrap_strategy=wrap_strategy,
            text_direction=text_direction,
            hyperlink_display_type=hyperlink_display_type,
            number_format=number_format,
            cell_format=(
                sheets_format.cell_formats[0][0]
                if (
                    sheets_format.cell_formats is not None
                    and len(sheets_format.cell_formats)
                    and len(sheets_format.cell_formats[0])
                )
                else cell_format
                if cell_format is not None
                else None
            ),
        )

        def resize_and_create_request(sheet_id: int, sheet_slice: SheetSliceT):
            rows, cols = sheet_slice.rows, sheet_slice.columns

            if sheets_format.column_sizes is not None:
                # if overflow is enabled, don't resize the columns:
                if cell_format.get("wrapStrategy") != WrapStrategy.OVERFLOW_CELL:
                    self.resize_dimensions(
                        spreadsheet_id=spreadsheet_id,
                        sheet_name=sheet_slice.sheet_name,
                        sizes=sheets_format.column_sizes,
                        dimension=SheetsDimension.columns,
                    )

            if sheets_format.row_sizes is not None:
                # if wrapping is enabled, don't resize the rows
                if cell_format.get("wrapStrategy") != WrapStrategy.WRAP:
                    self.resize_dimensions(
                        spreadsheet_id=spreadsheet_id,
                        sheet_name=sheet_slice.sheet_name,
                        sizes=sheets_format.row_sizes,
                        dimension=SheetsDimension.rows,
                    )

            formats = [
                self._create_format_body(
                    sheet_id,
                    start_row=rows.start,
                    end_row=rows.stop,
                    start_col=cols.start,
                    end_col=cols.stop,
                    cell_format=cell_format,
                )
            ]

            if not update:
                return formats

            t_sheets_formats = self.get_format(
                spreadsheet_id=spreadsheet_id,
                range_name=sheet_slice,
            )

            if not len(t_sheets_formats) or t_sheets_formats[0].cell_formats is None:
                return formats

            formats = []
            cell_formats = t_sheets_formats[0].cell_formats

            for n in range(rows.start - 1, rows.stop):
                for m in range(cols.start - 1, cols.stop):
                    format = None

                    if n < len(cell_formats) and m < len(cell_formats[n]):
                        format = cell_formats[n][m]

                        t_cell_format = cell_format.copy()

                        deep_update(format, t_cell_format)  # type: ignore
                    else:
                        format = cell_format

                    formats.append(
                        self._create_format_body(
                            sheet_id,
                            start_row=n + 1,
                            end_row=n + 1,
                            start_col=m + 1,
                            end_col=m + 1,
                            cell_format=format,
                        )
                    )

            return formats

        requests = []
        for range_name in range_names:
            sheet_slice = to_sheet_slice(range_name)

            sheet_id = self.id(spreadsheet_id=spreadsheet_id, sheet_name=sheet_slice.sheet_name)

            shape = self.shape(spreadsheet_id=spreadsheet_id, sheet_name=sheet_slice.sheet_name)

            sheet_slice = sheet_slice.with_shape(shape)

            requests.extend(resize_and_create_request(sheet_id=sheet_id, sheet_slice=sheet_slice))

        body: BatchUpdateSpreadsheetRequest = {"requests": requests}

        self.batch_update_spreadsheet(
            spreadsheet_id=spreadsheet_id,
            body=body,
        )

        return None

    @staticmethod
    def _destructure_row_format_data(cell_data: CellData) -> CellFormat | None:
        if "effectiveFormat" not in cell_data or "userEnteredFormat" not in cell_data:
            return None

        cell_format: CellFormat = cell_data.get("effectiveFormat", cell_data.get("userEnteredFormat"))  # type: ignore

        text_format: TextFormat = cell_format.get("textFormat", {})
        text_color: Color = text_format.get("foregroundColor", {})

        horizontal_alignment = cell_format.get("horizontalAlignment")
        vertical_alignment = cell_format.get("verticalAlignment")
        wrap_strategy = cell_format.get("wrapStrategy")
        text_direction = cell_format.get("textDirection")
        hyperlink_display_type = cell_format.get("hyperlinkDisplayType")

        cell_format = Sheets._create_cell_format(
            bold=text_format.get("bold"),
            italic=text_format.get("italic"),
            underline=text_format.get("underline"),
            strikethrough=text_format.get("strikethrough"),
            font_size=text_format.get("fontSize"),
            font_family=text_format.get("fontFamily"),
            text_color=text_color,
            background_color=cell_format.get("backgroundColor", {}),
            padding=cell_format.get("padding"),
            horizontal_alignment=(
                HorizontalAlignment(horizontal_alignment) if horizontal_alignment is not None else None
            ),
            vertical_alignment=(VerticalAlignment(vertical_alignment) if vertical_alignment is not None else None),
            wrap_strategy=(WrapStrategy(wrap_strategy) if wrap_strategy is not None else None),
            text_direction=(TextDirection(text_direction) if text_direction is not None else None),
            hyperlink_display_type=(
                HyperlinkDisplayType(hyperlink_display_type) if hyperlink_display_type is not None else None
            ),
        )

        return cell_format

    def get_format(self, spreadsheet_id: str, range_name: SheetsRange) -> list[SheetsFormat]:
        """Get the formatting of the **first** cell of a range of cells.

        A SheetsFormat object contains formatting and dimension information:
            -  column_sizes: a list of column sizes
            -  row_sizes: a list of row sizes
            -  cell_format: a CellFormat object containing formatting information

        This function works bidirectionally with `format`.

        See "CellFormat" in the Sheets API for more details.

        Args:
            spreadsheet_id (str): The spreadsheet to get.
            range_name (str): The range to get formatting from."""
        sheet_slice = to_sheet_slice(range_name)
        response = self.get(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_slice.sheet_name,
            include_grid_data=True,
            range_names=range_name,
        )

        sheets_formats = []

        for data in response["data"]:
            column_metadata = data["columnMetadata"]
            row_metadata = data["rowMetadata"]

            column_sizes = [metadata["pixelSize"] for metadata in column_metadata]
            row_sizes = [metadata["pixelSize"] for metadata in row_metadata]

            # Row data may be missing if the sheet is empty
            if "rowData" not in data:
                sheets_formats.append(
                    SheetsFormat(
                        cell_formats=None,
                        column_sizes=column_sizes,
                        row_sizes=row_sizes,
                    )
                )
                continue

            cell_formats: list[list[CellFormat]] = []

            row_data = data["rowData"]
            for row in row_data:
                if "values" not in row:
                    continue

                row_formats: list[CellFormat] = []

                for value in row["values"]:
                    if (t_cell_format := self._destructure_row_format_data(value)) is not None:
                        row_formats.append(t_cell_format)

                cell_formats.append(row_formats)

            sheets_formats.append(
                SheetsFormat(
                    cell_formats=cell_formats if len(cell_formats) else None,
                    column_sizes=column_sizes,
                    row_sizes=row_sizes,
                )
            )

        return sheets_formats

    @staticmethod
    def to_frame(
        values: ValueRange,
        columns: list[str] | None = None,
        dtypes: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Converts a ValueRange to a DataFrame.

        Useful for working with the data in Pandas after a call to sheets.values().
        If one of the keyword arguments to the dataframe is "columns",
        the first row of the values will be used as the column names, aligned to the data.

        All string values that are empty will be converted to pd.NA,
        and the data types of the columns will be inferred.

        Args:
            values (ValueRange): The values to convert.
            columns (list[str], optional): The column names to use. Defaults to None.
            dtypes (dict[str, type], optional): The data types to use. Defaults to None.
            **kwargs: Additional arguments to pass to pd.DataFrame.

        Example:
            >>> import sheets
            >>> import pandas as pd
            >>> df = sheets.to_frame(sheets.values(
                SHEET_ID, "Sheet1!A1:B2"))
            >>> df
        """
        dtypes = dtypes if dtypes is not None else {}

        def convert_dtypes(df: pd.DataFrame) -> pd.DataFrame:
            for col, dtype in dtypes.items():
                df[col] = df[col].astype(dtype)

            return df

        # No values
        if not len(rows := values.get("values", [])):
            return pd.DataFrame()

        columns = columns if columns is not None else []
        # if we have extant columns, append to them instead of replacing them
        columns += rows[0]  # type: ignore

        rows = rows[1:] if len(rows) > 1 else []  # type: ignore

        df = pd.DataFrame(rows, **kwargs)

        # Only headers
        if not len(df) and len(columns):
            df = pd.DataFrame(columns=columns, **kwargs)
            convert_dtypes(df)
            return df

        mapper = dict(enumerate(columns))
        df.rename(columns=mapper, inplace=True)

        df = df.convert_dtypes()
        # Set object columns to pd.StringDtype:
        df = df.astype({col: pd.StringDtype() for col in df.select_dtypes("object")})
        # Replace empty strings with pd.NA; infer the data types
        df.select_dtypes(include=["object", "string"]).replace(r"^\s*$", pd.NA, regex=True, inplace=True)
        df = convert_dtypes(df)

        return df

    @staticmethod
    def from_frame(df: pd.DataFrame, as_dict: bool = True) -> list[list[Any]] | list[dict[Hashable, Any]]:
        """Converts a DataFrame to a list of lists to be used with sheets.update() & c.
        If `as_dict` is True, the list of lists will be converted to a list of dicts,
        which is useful for aligning the columns with the header.

        Args:
            df (pd.DataFrame): The DataFrame to convert.
            as_dict (bool, optional): Whether to return a list of dicts instead of a list of lists. Defaults to False.
        """
        t_df = df.astype(str)
        t_df[df.isna()] = ""

        df = t_df

        if as_dict:
            return df.to_dict(orient="records")

        data: list = df.values.tolist()  # type: ignore
        data.insert(0, list(df.columns))
        return data

    @staticmethod
    def _resize_dimension(
        sheet: Sheet,
        sizes: list[int] | list[int | None] | int | None = None,
        dimension: SheetsDimension = SheetsDimension.columns,
    ) -> list:
        """Internal method to create dimension resize requests.

        Args:
            sheet: Sheet object containing properties
            sizes: If None, auto-resize all columns/rows. If int, set all to that size.
                If list, can contain None to auto-resize specific columns/rows.
            dimension: Whether to resize rows or columns
        """
        sheet_id = sheet["properties"]["sheetId"]
        grid_properties = sheet["properties"]["gridProperties"]
        count = grid_properties["columnCount"] if dimension == SheetsDimension.columns else grid_properties["rowCount"]

        # Helper to create dimension range
        def make_range(start: int, end: int | None = None) -> dict:
            return {
                "sheetId": sheet_id,
                "dimension": dimension.value,
                "startIndex": start,
                "endIndex": end if end is not None else start + 1,
            }

        # Case 1: Auto-resize all
        if sizes is None:
            return [{"autoResizeDimensions": {"dimensions": make_range(0, count)}}]

        # Case 2: Single size for all
        if isinstance(sizes, int):
            return [
                {
                    "updateDimensionProperties": {
                        "range": make_range(0, count),
                        "properties": {"pixelSize": sizes},
                        "fields": "pixelSize",
                    }
                }
            ]

        # Case 3: List of sizes with possible None values
        requests: list = []

        # Group consecutive None values for batch auto-resize
        i = 0
        while i < min(len(sizes), count):
            if sizes[i] is None:
                # Find end of None sequence
                j = i + 1
                while j < min(len(sizes), count) and sizes[j] is None:
                    j += 1
                requests.append({"autoResizeDimensions": {"dimensions": make_range(i, j)}})
                i = j
            else:
                requests.append(
                    {
                        "updateDimensionProperties": {
                            "range": make_range(i),
                            "properties": {"pixelSize": sizes[i]},
                            "fields": "pixelSize",  # type: ignore
                        }
                    }
                )
                i += 1

        return requests

    def resize_dimensions(
        self,
        spreadsheet_id: str,
        sheet_name: SheetsRange = DEFAULT_SHEET_NAME,
        sizes: list[int] | list[int | None] | int | None = 100,
        dimension: SheetsDimension = SheetsDimension.columns,
    ) -> BatchUpdateSpreadsheetResponse | None:
        """Resizes the dimensions of a sheet.

        Args:
            spreadsheet_id: The spreadsheet to update
            sheet_name: The name of the sheet to resize
            sizes: The sizes to resize to:
                - If None, auto-resize all columns/rows
                - If int, set all columns/rows to that size
                - If list, can contain None to auto-resize specific columns/rows
            dimension: Whether to resize rows or columns
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        sheet_slice = to_sheet_slice(sheet_name)
        sheet_name = sheet_slice.sheet_name
        sheet = self.get(spreadsheet_id, sheet_name=sheet_name)

        # Create and execute resize request
        body: BatchUpdateSpreadsheetRequest = {
            "requests": self._resize_dimension(
                sheet=sheet,
                sizes=sizes,
                dimension=dimension,
            )
        }

        return self.batch_update_spreadsheet(
            spreadsheet_id=spreadsheet_id,
            body=body,
        )  # type: ignore

    def freeze(
        self,
        spreadsheet_id: str,
        sheet_name: str = DEFAULT_SHEET_NAME,
        rows: int = 0,
        columns: int = 0,
    ):
        """Freezes rows and/or columns in a sheet.

        Args:
            spreadsheet_id (str): The ID of the spreadsheet
            sheet_name (str, optional): Name of the sheet to freeze. Defaults to DEFAULT_SHEET_NAME.
            rows (int, optional): Number of rows to freeze from top. Defaults to 0.
            columns (int, optional): Number of columns to freeze from left. Defaults to 0.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        sheet_id = self.id(spreadsheet_id, sheet_name)

        body: BatchUpdateSpreadsheetRequest = {
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet_id,
                            "gridProperties": {
                                "frozenRowCount": rows,
                                "frozenColumnCount": columns,
                            },
                        },
                        "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
                    }
                }
            ]
        }

        return self.batch_update_spreadsheet(
            spreadsheet_id=spreadsheet_id,
            body=body,
        )

    def format_header(
        self,
        spreadsheet_id: str,
        sheet_name: str = DEFAULT_SHEET_NAME,
        auto_resize: bool = False,
    ):
        """Formats the header row of a sheet by freezing and bolding it, with optional column auto-resizing.

        Args:
            spreadsheet_id (str): The ID of the spreadsheet to format
            sheet_name (str, optional): Name of the sheet to format. Defaults to DEFAULT_SHEET_NAME.
            auto_resize (bool, optional): Whether to auto-resize columns. Defaults to True.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)

        # Freeze first row
        self.freeze(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            rows=1,
        )

        # Format first row bold
        sheet_slice = SheetSlice[sheet_name, 1, ...]
        self.format(
            spreadsheet_id=spreadsheet_id,
            range_names=sheet_slice,
            bold=True,
            wrap_strategy=WrapStrategy.WRAP,
        )

        # Auto-resize columns if requested
        if auto_resize:
            self.resize_dimensions(
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                sizes=None,
                dimension=SheetsDimension.columns,
            )
