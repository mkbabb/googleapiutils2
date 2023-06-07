from __future__ import annotations

import operator
import time
from collections import defaultdict
from typing import *

import pandas as pd
from cachetools import TTLCache, cachedmethod
from google.oauth2.credentials import Credentials
from googleapiclient import discovery

from ..utils import THROTTLE_TIME, hex_to_rgb, nested_defaultdict, parse_file_id
from .misc import (
    DEFAULT_SHEET_NAME,
    DEFAULT_SHEET_SHAPE,
    VERSION,
    A1_to_slices,
    InsertDataOption,
    SheetSlice,
    SheetSliceT,
    SheetsValues,
    ValueInputOption,
    ValueRenderOption,
    split_sheet_range,
)

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import File
    from googleapiclient._apis.sheets.v4.resources import (
        AppendValuesResponse,
        BatchUpdateSpreadsheetRequest,
        BatchUpdateSpreadsheetResponse,
        BatchUpdateValuesRequest,
        BatchUpdateValuesResponse,
        CellFormat,
        ClearValuesResponse,
        CopySheetToAnotherSpreadsheetRequest,
        Request,
        Sheet,
        SheetProperties,
        SheetsResource,
        Spreadsheet,
        SpreadsheetProperties,
        TextFormat,
        UpdateValuesResponse,
        ValueRange,
    )


SheetsRange = str | SheetSliceT | Any


class Sheets:
    def __init__(self, creds: Credentials, throttle_time: float = THROTTLE_TIME):
        self.creds = creds
        self.service: SheetsResource = discovery.build(  # type: ignore
            "sheets", VERSION, credentials=self.creds
        )
        self.spreadsheets: SheetsResource.SpreadsheetsResource = (
            self.service.spreadsheets()
        )
        self.throttle_time = throttle_time

        self._cache: TTLCache = TTLCache(maxsize=128, ttl=80)

        self._batched_data: DefaultDict[
            str, dict[str | Any, SheetsValues]
        ] = defaultdict(dict)
        self._prev_time: Optional[float] = None

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
        return self.spreadsheets.batchUpdate(
            spreadsheetId=spreadsheet_id, body=body, **kwargs
        ).execute()

    def create(
        self,
        title: str,
        sheet_names: list[str] | None = None,
        body: Spreadsheet | None = None,  # type: ignore
    ):
        body: Spreadsheet = nested_defaultdict(body if body else {})  # type: ignore
        sheet_names = sheet_names if sheet_names is not None else [DEFAULT_SHEET_NAME]

        body["properties"]["title"] = title  # type: ignore
        for n, sheet_name in enumerate(sheet_names):
            body["sheets"][n]["properties"]["title"] = sheet_name  # type: ignore

        body["sheets"] = list(body["sheets"].values())  # type: ignore

        return self.spreadsheets.create(body=body).execute()  # type: ignore

    def copy_to(
        self,
        from_spreadsheet_id: str,
        from_sheet_id: int,
        to_spreadsheet_id: str,
    ):
        """Copy a sheet from one spreadsheet to another.

        Args:
            from_spreadsheet_id (str): The ID of the spreadsheet containing the sheet to copy.
            from_sheet_id (int): The ID of the sheet to copy.
            to_spreadsheet_id (str): The ID of the spreadsheet to copy the sheet to.
        """
        from_spreadsheet_id, to_spreadsheet_id = (
            parse_file_id(from_spreadsheet_id),
            parse_file_id(to_spreadsheet_id),
        )
        body: CopySheetToAnotherSpreadsheetRequest = {
            "destinationSpreadsheetId": to_spreadsheet_id
        }

        return (
            self.spreadsheets.sheets()
            .copyTo(  # type: ignore
                spreadsheetId=from_spreadsheet_id,
                sheetId=from_sheet_id,
                body=body,
            )
            .execute()
        )

    def get_spreadsheet(
        self,
        spreadsheet_id: str,
    ) -> Spreadsheet:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        return self.spreadsheets.get(spreadsheetId=spreadsheet_id).execute()

    def get(
        self,
        spreadsheet_id: str,
        name: str | None = None,
        sheet_id: int | None = None,
    ) -> Sheet:
        """Get a sheet from a spreadsheet. Either the name or the ID of the sheet must be provided.

        Args:
            spreadsheet_id (str): The ID of the spreadsheet containing the sheet to get.
            name (str, optional): The name of the sheet to get. Defaults to None.
            sheet_id (int, optional): The ID of the sheet to get. Defaults to None.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        spreadsheet = self.get_spreadsheet(spreadsheet_id)

        if name is not None and name.startswith("'") and name.endswith("'"):
            name = name[1:-1]

        for sheet in spreadsheet["sheets"]:
            if sheet_id is not None and sheet["properties"]["sheetId"] == sheet_id:
                return sheet
            if name is not None and sheet["properties"]["title"] == name:
                return sheet

        raise ValueError(f"Sheet {name or sheet_id} not found in spreadsheet.")

    def rename(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        new_name: str,
    ):
        """Rename a sheet in a spreadsheet.

        Args:
            spreadsheet_id (str): The ID of the spreadsheet containing the sheet to rename.
            sheet_id (int): The ID of the sheet to rename.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)

        body: BatchUpdateSpreadsheetRequest = {
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {"sheetId": sheet_id, "title": new_name},
                        "fields": "title",
                    }
                }
            ]
        }
        return self.batch_update_spreadsheet(spreadsheet_id=spreadsheet_id, body=body)

    def add(
        self,
        spreadsheet_id: str,
        names: str | list[str],
        rows: int = 1000,
        cols: int = 26,
        index: int | None = None,
        **kwargs: Any,
    ):
        """Add one or more sheets to a spreadsheet.

        Args:
            spreadsheet_id (str): The ID of the spreadsheet to add sheets to.
            names (str | list[str]): The name(s) of the sheet(s) to add.
            rows (int, optional): The number of rows to add to each sheet. Defaults to 1000.
            cols (int, optional): The number of columns to add to each sheet. Defaults to 26.
            index (int, optional): The index at which to insert the sheet(s). Defaults to None.
            **kwargs: Additional keyword arguments to pass to the API request."""
        spreadsheet_id = parse_file_id(spreadsheet_id)
        if isinstance(names, str):
            names = [names]

        def make_body(name: str) -> Sheet:
            body: Sheet = {
                "properties": {
                    "title": name,
                    "gridProperties": {
                        "rowCount": rows,
                        "columnCount": cols,
                    },
                },
            }
            if index is not None:
                body["properties"]["index"] = index
            return body

        body: BatchUpdateSpreadsheetRequest = {
            "requests": [
                {
                    "addSheet": make_body(name),
                }
                for name in names
            ],
        }

        return self.batch_update_spreadsheet(
            spreadsheet_id=spreadsheet_id,
            body=body,
            **kwargs,
        )

    def delete(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        **kwargs: Any,
    ):
        """Deletes a sheet from a spreadsheet.

        Args:
            spreadsheet_id (str): The ID of the spreadsheet to delete the sheet from.
            sheet_id (str): The ID of the sheet to delete.
            **kwargs: Additional keyword arguments to pass to the API request.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        body: BatchUpdateSpreadsheetRequest = {
            "requests": [
                {
                    "deleteSheet": {
                        "sheetId": sheet_id,
                    },
                },
            ],
        }
        return self.batch_update_spreadsheet(
            spreadsheet_id=spreadsheet_id,
            body=body,
            **kwargs,
        )

    def values(
        self,
        spreadsheet_id: str,
        range_name: SheetsRange = DEFAULT_SHEET_NAME,
        value_render_option: ValueRenderOption = ValueRenderOption.unformatted,
        **kwargs: Any,
    ):
        """Get values from a spreadsheet within a range.

        Args:
            spreadsheet_id (str): The spreadsheet ID.
            range_name (SheetsRange, optional): The range to get values from. Defaults to DEFAULT_SHEET_NAME.
            value_render_option (ValueRenderOption, optional): The value render option. Defaults to ValueRenderOption.unformatted.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(range_name)
        return (
            self.spreadsheets.values()
            .get(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueRenderOption=value_render_option.value,
                **kwargs,
            )
            .execute()
        )

    @cachedmethod(operator.attrgetter("_cache"))
    def _header(self, spreadsheet_id: str, sheet_name: str = DEFAULT_SHEET_NAME):
        """Get the header of a sheet; cache the result."""
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(SheetSlice[sheet_name, 1, ...])
        return self.values(spreadsheet_id=spreadsheet_id, range_name=range_name).get(
            "values", [[]]
        )[0]

    def _dict_to_values_align_columns(
        self,
        spreadsheet_id: str,
        range_name: SheetsRange,
        rows: list[dict[SheetsRange, Any]],
        align_columns: bool = True,
        insert_header: bool = True,
    ):
        """Transforms a list of dictionaries into a list of lists, aligning the columns with the header.
        If new columns were added, the header is appended to the right; the header of the sheet is updated.

        Args:
            spreadsheet_id (str): The spreadsheet ID.
            range_name (SheetsRange): The range to update.
            rows (list[dict[SheetsRange, Any]]): The rows to update.
            align_columns (bool, optional): Whether to align the columns with the header. Defaults to True.
            insert_header (bool, optional): Whether to insert the header if the range starts at the first row. Defaults to True.
        """
        if not align_columns:
            return [list(row.values()) for row in rows]

        sheet_name, t_range_name = split_sheet_range(range_name)
        row_slc, _ = A1_to_slices(t_range_name)

        header = self._header(spreadsheet_id, sheet_name)
        header = pd.Index(header).astype(str)

        frame = pd.DataFrame(rows)
        frame = frame.reindex(
            list(rows[0].keys()), axis=1
        )  # preserve the insertion order
        frame.index = frame.index.astype(str)

        if len(diff := frame.columns.difference(header)):
            header = header.append(diff)
            sheet_name, _ = split_sheet_range(range_name)
            self.update(
                spreadsheet_id,
                SheetSlice[sheet_name, 1, ...],
                [header.tolist()],
            )
            self._cache[(spreadsheet_id, sheet_name)] = list(header)

        frame = frame.reindex(columns=header)
        values = frame.fillna("").values.tolist()

        # insert the header if the range starts at the first row
        if insert_header and row_slc.start == 1:
            values.insert(0, header.tolist())

        return values

    def _process_sheets_values(
        self,
        spreadsheet_id: str,
        range_name: SheetsRange,
        values: SheetsValues,
        align_columns: bool = True,
        insert_header: bool = True,
    ) -> list[list[Any]]:
        if all(isinstance(value, dict) for value in values):
            return self._dict_to_values_align_columns(
                spreadsheet_id=spreadsheet_id,
                range_name=range_name,
                rows=values,  # type: ignore
                align_columns=align_columns,
                insert_header=insert_header,
            )
        else:
            return values  # type: ignore

    def update(
        self,
        spreadsheet_id: str,
        range_name: SheetsRange,
        values: SheetsValues,
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        align_columns: bool = True,
    ):
        """Updates a range of values in a spreadsheet.

        If `values` is a list of dicts, the keys of the first dict will be used as the header row.
        Further, if the input is a list of dicts and `align_columns` is True, the columns of the spreadsheet
        will be aligned with the keys of the first dict.

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            range_name (SheetsRange): The range to update.
            values (SheetsValues): The values to update.
            value_input_option (ValueInputOption, optional): How the input data should be interpreted. Defaults to ValueInputOption.user_entered.
            align_columns (bool, optional): Whether to align the columns of the spreadsheet with the keys of the first row of the values. Defaults to True.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(range_name)
        values = self._process_sheets_values(
            spreadsheet_id, range_name, values, align_columns
        )

        return (
            self.spreadsheets.values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                body={"values": values},  # type: ignore
                valueInputOption=value_input_option.value,
            )
            .execute()
        )

    def _batch_update(
        self,
        spreadsheet_id: str,
        data: dict[SheetsRange, SheetsValues],
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        align_columns: bool = True,
    ):
        """Internal method for batch updating values. Use `batch_update` instead."""
        new_data: list[ValueRange] = [
            {
                "range": (str_range_name := str(range_name)),
                "values": self._process_sheets_values(
                    spreadsheet_id=spreadsheet_id,
                    range_name=str_range_name,
                    values=values,
                    align_columns=align_columns,
                ),
            }
            for range_name, values in data.items()
        ]

        body: BatchUpdateValuesRequest = {
            "valueInputOption": value_input_option.value,
            "data": new_data,
        }
        return (
            self.spreadsheets.values()
            .batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body,
            )
            .execute()
        )

    def batch_update(
        self,
        spreadsheet_id: str,
        data: dict[SheetsRange, SheetsValues],
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        align_columns: bool = True,
        batch_size: int | None = None,
    ):
        """Updates a series of range values in a spreadsheet. Much faster version of calling `update` multiple times.
        See `update` for more details.

        If the `batch_size` is None, all updates will be batched together. Otherwise, the updates will be batched by the following
        rules:
        -   If the number of updates is greater than `batch_size` AND
        -   If the time between the first update and the last update is greater than `THROTTLE_TIME` OR

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            data (dict[SheetsRange, SheetsValues]): The data to update.
            value_input_option (ValueInputOption, optional): How the input data should be interpreted. Defaults to ValueInputOption.user_entered.
            align_columns (bool, optional): Whether to align the columns of the spreadsheet with the keys of the first row of the values. Defaults to True.
            batch_size (int | None, optional): The number of updates to batch together. If None, all updates will be batched together. Defaults to None.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)

        if batch_size is None:
            return self._batch_update(
                spreadsheet_id=spreadsheet_id,
                data=data,
                value_input_option=value_input_option,
                align_columns=align_columns,
            )

        batched_data = self._batched_data[spreadsheet_id]

        if data is not None:
            self._batched_data[spreadsheet_id] |= data

        curr_time = time.perf_counter()
        dt = (
            curr_time - self._prev_time
            if self._prev_time is not None
            else self.throttle_time
        )

        # If the conditions for a batch update are not met, simply return
        if not (dt >= self.throttle_time and len(batched_data) >= batch_size):
            return None

        self._prev_time = curr_time
        res = self._batch_update(
            spreadsheet_id=spreadsheet_id,
            data=batched_data,
            value_input_option=value_input_option,
            align_columns=align_columns,
        )
        self._batched_data[spreadsheet_id].clear()

        return res

    def batched_update_remaining(self, spreadsheet_id: str):
        """Updates any remaining batched data that's been left over from previous calls to `batch_update`."""
        spreadsheet_id = parse_file_id(spreadsheet_id)
        batched_data = self._batched_data[spreadsheet_id]

        res = self._batch_update(
            spreadsheet_id=spreadsheet_id,
            data=batched_data,
        )
        self._batched_data[spreadsheet_id].clear()
        return res

    def append(
        self,
        spreadsheet_id: str,
        range_name: SheetsRange,
        values: SheetsValues,
        insert_data_option: InsertDataOption = InsertDataOption.overwrite,
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        align_columns: bool = True,
    ):
        """Appends values to a spreadsheet. Like `update`, but searches for the next available row to append to.
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
        range_name = str(range_name)
        body: ValueRange = {
            "values": self._process_sheets_values(
                spreadsheet_id=spreadsheet_id,
                range_name=range_name,
                values=values,
                align_columns=align_columns,
                insert_header=False,
            )
        }

        return (
            self.spreadsheets.values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                body=body,
                insertDataOption=insert_data_option.value,
                valueInputOption=value_input_option.value,
            )
            .execute()
        )

    def clear(
        self,
        spreadsheet_id: str,
        range_name: SheetsRange,
    ):
        """Clears a range of values in a spreadsheet.

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            range_name (SheetsRange): The range to clear.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(range_name)

        return (
            self.spreadsheets.values()
            .clear(spreadsheetId=spreadsheet_id, range=range_name)
            .execute()
        )

    def resize(
        self,
        spreadsheet_id: str,
        sheet_name: str,
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

        sheet_id = self.get(spreadsheet_id, name=sheet_name)["properties"]["sheetId"]
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
        return self.batch_update_spreadsheet(spreadsheet_id=spreadsheet_id, body=body)

    def clear_formatting(self, spreadsheet_id: str, sheet_name: str):
        """Clears all formatting from a sheet.

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            sheet_name (str): The name of the sheet to clear formatting from.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)

        sheet_id = self.get(spreadsheet_id, name=sheet_name)["properties"]["sheetId"]
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
        return self.batch_update_spreadsheet(spreadsheet_id=spreadsheet_id, body=body)

    def reset_sheet(
        self,
        spreadsheet_id: str,
        sheet_name: str,
    ):
        """Resets a sheet back to a default state. This includes clearing all values and formatting.

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            sheet_name (str): The name of the sheet to reset.
        """
        # first clear all of the values, and set the bounds of the sheet to have 26 columns, and 1000 rows
        self.clear(spreadsheet_id, sheet_name)
        self.resize(spreadsheet_id, sheet_name, rows=1000, cols=26)
        # then clear all of the formatting
        self.clear_formatting(spreadsheet_id, sheet_name)

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
        end_row = end_row if end_row is not None else start_row + 1
        end_col = end_col if end_col is not None else start_col + 1

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
                "fields": f"userEnteredFormat",
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
        text_color: str | None = None,
        background_color: str | None = None,
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
            text_format["foregroundColor"] = hex_to_rgb(text_color)

        cell_format_dict: CellFormat = {}
        if background_color is not None:
            cell_format_dict["backgroundColor"] = hex_to_rgb(background_color)
        if cell_format is not None:
            cell_format_dict.update(cell_format)

        return {"textFormat": text_format, **cell_format_dict}  # type: ignore

    def format(
        self,
        spreadsheet_id: str,
        range_name: SheetsRange,
        bold: bool | None = None,
        italic: bool | None = None,
        underline: bool | None = None,
        strikethrough: bool | None = None,
        font_size: int | None = None,
        font_family: str | None = None,
        text_color: str | None = None,
        background_color: str | None = None,
        cell_format: CellFormat | None = None,
    ):
        """Formats a range of cells in a spreadsheet.

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            range_name (str): The range to format.
            ...
            cell_format (CellFormat, optional): A cell format to merge with the default format. Defaults to None.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        cell_format = self._create_cell_format(
            bold=bold,
            italic=italic,
            underline=underline,
            strikethrough=strikethrough,
            font_size=font_size,
            font_family=font_family,
            text_color=text_color,
            background_color=background_color,
            cell_format=cell_format,
        )

        sheet_name, range_name = split_sheet_range(str(range_name))  # type: ignore

        properties = self.get(spreadsheet_id, sheet_name)["properties"]
        sheet_id = properties["sheetId"]
        shape = (
            properties["gridProperties"]["rowCount"],
            properties["gridProperties"]["columnCount"],
        )

        row_slc, col_slc = A1_to_slices(range_name, shape=shape)

        body: BatchUpdateSpreadsheetRequest = {
            "requests": [
                self._create_format_body(
                    sheet_id,
                    start_row=row_slc.start,
                    end_row=row_slc.stop,
                    start_col=col_slc.start,
                    end_col=col_slc.stop,
                    cell_format=cell_format,
                )
            ]
        }
        return self.batch_update_spreadsheet(spreadsheet_id=spreadsheet_id, body=body)

    @staticmethod
    def to_frame(values: ValueRange, **kwargs: Any) -> pd.DataFrame | None:
        """Converts a ValueRange to a DataFrame.

        Useful for working with the data in Pandas after a call to sheets.values().
        If one of the keyword arguments to the dataframe is "columns",
        the first row of the values will be used as the column names, aligned to the data.

        All string values that are empty will be converted to pd.NA,
        and the data types of the columns will be inferred.

        If the sheet is empty, None will be returned.

        Args:
            values (ValueRange): The values to convert.
            **kwargs: Additional arguments to pass to pd.DataFrame.

        Example:
            >>> import sheets
            >>> import pandas as pd
            >>> df = sheets.to_frame(sheets.values(
                SHEET_ID, "Sheet1!A1:B2"))
            >>> df
        """
        if not len(rows := values.get("values", [])):
            return None

        columns = kwargs.pop("columns", []) + rows[0]
        rows = rows[1:] if len(rows) > 1 else []

        df = pd.DataFrame(rows, **kwargs)

        mapper = {i: col for i, col in enumerate(columns)}
        df.rename(columns=mapper, inplace=True)
        df.select_dtypes(include=["object"]).replace(
            r"^\s*$", pd.NA, regex=True, inplace=True
        )
        return df

    @staticmethod
    def from_frame(
        df: pd.DataFrame, as_dict: bool = False
    ) -> list[list[Any]] | list[dict[Hashable, Any]]:
        """Converts a DataFrame to a list of lists to be used with sheets.update() & c.

        Args:
            df (pd.DataFrame): The DataFrame to convert.
            as_dict (bool, optional): Whether to return a list of dicts instead of a list of lists. Defaults to False.
        """
        df = df.fillna("")
        df = df.astype(str)

        if as_dict:
            return df.to_dict(orient="records")

        data: list = df.values.tolist()
        data.insert(0, list(df.columns))
        return data

    @staticmethod
    def _resize_columns(sheet: Sheet, widths: int | list[int] | None = None) -> list:
        sheet_id = sheet["properties"]["sheetId"]
        num_columns = sheet["properties"]["gridProperties"]["columnCount"]

        make_range = lambda i: {
            "sheetId": sheet_id,
            "dimension": "COLUMNS",
            "startIndex": i,
            "endIndex": i + 1,
        }

        if widths is None:
            return [
                {
                    "autoResizeDimensions": {
                        "dimensions": make_range(i),
                    }
                }
                for i in range(num_columns)
            ]

        if isinstance(widths, int):
            widths = [widths] * num_columns
        return [
            {
                "updateDimensionProperties": {
                    "range": make_range(i),
                    "properties": {"pixelSize": widths[i]},
                    "fields": "pixelSize",
                }
            }
            for i in range(num_columns)
        ]

    def resize_columns(
        self, spreadsheet_id: str, sheet_name: str, width: int | None = 100
    ):
        """Resizes the columns of a sheet.

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            sheet_name (str): The name of the sheet to update.
            width (int, optional): The width to set the columns to. Defaults to 100. If None, will auto-resize.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        sheet = self.get(spreadsheet_id, name=sheet_name)
        if sheet is None:
            raise ValueError(f"Sheet '{sheet_name}' not found in the given spreadsheet")

        def resize():
            body: BatchUpdateSpreadsheetRequest = {
                "requests": self._resize_columns(sheet, width)  # type: ignore
            }
            return (
                self.service.spreadsheets()
                .batchUpdate(spreadsheetId=spreadsheet_id, body=body)
                .execute()
            )

        if width is None:
            header = self._header(spreadsheet_id, sheet_name)
            res = self.append(spreadsheet_id, sheet_name, [header])
            updated_range = res["updates"]["updatedRange"]

            res = resize()

            self.clear(spreadsheet_id, updated_range)
            return res
        else:
            return resize()
