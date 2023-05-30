from __future__ import annotations

import logging
import operator
from typing import *

import pandas as pd
from cachetools import TTLCache, cachedmethod
from google.oauth2.credentials import Credentials
from googleapiclient import discovery

from ..utils import nested_defaultdict, parse_file_id
from .misc import (
    DEFAULT_SHEET_NAME,
    VERSION,
    InsertDataOption,
    SheetSlice,
    SheetSliceT,
    ValueInputOption,
    ValueRenderOption,
    reverse_sheet_range,
)

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import File
    from googleapiclient._apis.sheets.v4.resources import (
        AppendValuesResponse,
        BatchUpdateSpreadsheetRequest,
        BatchUpdateValuesRequest,
        BatchUpdateValuesResponse,
        ClearValuesResponse,
        CopySheetToAnotherSpreadsheetRequest,
        Sheet,
        SheetProperties,
        SheetsResource,
        Spreadsheet,
        SpreadsheetProperties,
        UpdateValuesResponse,
        ValueRange,
    )

logger = logging.getLogger(__name__)


class Sheets:
    def __init__(self, creds: Credentials):
        self.creds = creds
        self.service: SheetsResource = discovery.build(  # type: ignore
            "sheets", VERSION, credentials=self.creds
        )
        self.sheets: SheetsResource.SpreadsheetsResource = self.service.spreadsheets()

        self._cache: TTLCache = TTLCache(maxsize=128, ttl=80)

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

        return self.sheets.create(body=body).execute()

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
            self.sheets.sheets()
            .copyTo(
                spreadsheetId=from_spreadsheet_id,
                sheetId=from_sheet_id,
                body=body,
            )
            .execute()
        )

    def get(
        self,
        spreadsheet_id: str,
    ) -> Spreadsheet:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        return self.sheets.get(spreadsheetId=spreadsheet_id).execute()

    def get_sheet(
        self,
        spreadsheet_id: str,
        name: str | None = None,
        sheet_id: int | None = None,
    ) -> Sheet | None:
        """Get a sheet from a spreadsheet. Either the name or the ID of the sheet must be provided.

        Args:
            spreadsheet_id (str): The ID of the spreadsheet containing the sheet to get.
            name (str, optional): The name of the sheet to get. Defaults to None.
            sheet_id (int, optional): The ID of the sheet to get. Defaults to None.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        spreadsheet = self.get(spreadsheet_id)

        for sheet in spreadsheet["sheets"]:
            if sheet_id is not None and sheet["properties"]["sheetId"] == sheet_id:
                return sheet
            if name is not None and sheet["properties"]["title"] == name:
                return sheet

        return None

    def rename_sheet(
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
        return self.sheets.batchUpdate(
            spreadsheetId=spreadsheet_id, body=body
        ).execute()

    def add_sheet(
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

        return self.sheets.batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body,
            **kwargs,
        ).execute()

    def delete_sheet(
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
        return self.sheets.batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body,
            **kwargs,
        ).execute()

    def values(
        self,
        spreadsheet_id: str,
        range_name: str | Any = DEFAULT_SHEET_NAME,
        value_render_option: ValueRenderOption = ValueRenderOption.unformatted,
        **kwargs: Any,
    ):
        """Get values from a spreadsheet within a range.

        Args:
            spreadsheet_id (str): The spreadsheet ID.
            range_name (str | Any, optional): The range to get values from. Defaults to DEFAULT_SHEET_NAME.
            value_render_option (ValueRenderOption, optional): The value render option. Defaults to ValueRenderOption.unformatted.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(range_name)
        return (
            self.sheets.values()
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
        """Get the header of a sheet; cache the result"""
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(SheetSlice[sheet_name, 1, ...])
        return self.values(spreadsheet_id=spreadsheet_id, range_name=range_name).get(
            "values", [[]]
        )[0]

    def _dict_to_values_align_columns(
        self,
        spreadsheet_id: str,
        range_name: str,
        rows: list[dict],
        align_columns: bool = True,
    ):
        if align_columns:
            sheet_name, _ = reverse_sheet_range(range_name)
            header = self._header(spreadsheet_id, sheet_name)
            header = pd.Index(header).astype(str)

            frame = pd.DataFrame(rows)
            frame = frame.reindex(
                list(rows[0].keys()), axis=1
            )  # preserve the insertion order
            frame.index = frame.index.astype(str)

            if len(diff := frame.columns.difference(header)):
                # only align columns if there are new columns
                header = header.append(diff)
                sheet_name, _ = reverse_sheet_range(range_name)
                self.update(
                    spreadsheet_id,
                    SheetSlice[sheet_name, 1, ...],
                    [header.tolist()],
                )
                self._cache[(spreadsheet_id, sheet_name)] = list(header)

            other = pd.DataFrame(columns=header)
            frame = pd.concat([other, frame], ignore_index=True).fillna("")
            return frame.values.tolist()
        else:
            logger.debug("align_columns is False, skipping column alignment")
            return [list(row.values()) for row in rows]

    def _process_values(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]] | list[dict],
        align_columns: bool = True,
    ) -> list[list[Any]] | list[dict]:
        if all(isinstance(value, dict) for value in values):
            return self._dict_to_values_align_columns(
                spreadsheet_id=spreadsheet_id,
                range_name=range_name,
                rows=values,  # type: ignore
                align_columns=align_columns,
            )
        else:
            return values

    def update(
        self,
        spreadsheet_id: str,
        range_name: str | Any,
        values: list[list[Any]] | list[dict] | list[Any],
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        align_columns: bool = True,
    ):
        """Updates a range of values in a spreadsheet.

        If `values` is a list of dicts, the keys of the first dict will be used as the header row.
        Further, if the input is a list of dicts and `align_columns` is True, the columns of the spreadsheet
        will be aligned with the keys of the first dict.

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            range_name (str | Any): The range to update. Can be a string or a SheetSlice.
            values (list[list[Any]] | list[dict]): The values to update.
            value_input_option (ValueInputOption, optional): How the input data should be interpreted. Defaults to ValueInputOption.user_entered.
            align_columns (bool, optional): Whether to align the columns of the spreadsheet with the keys of the first row of the values. Defaults to True.

        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(range_name)
        values = self._process_values(spreadsheet_id, range_name, values, align_columns)

        return (
            self.sheets.values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                body={"values": values},  # type: ignore
                valueInputOption=value_input_option.value,
            )
            .execute()
        )

    def batch_update(
        self,
        spreadsheet_id: str,
        data: dict[str | Any, list[list[Any]] | list[dict]],
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        align_columns: bool = True,
    ):
        """Updates a series of range values in a spreadsheet. Much faster version of calling `update` multiple times.
        See `update` for more details.

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            data (dict): A dict of {range_name: values} to update;
                        values: list[list[Any]] | list[dict].
            value_input_option (ValueInputOption, optional): How the input data should be interpreted. Defaults to ValueInputOption.user_entered.
            align_columns (bool, optional): Whether to align the columns of the spreadsheet with the keys of the first row of the values. Defaults to True.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)

        batch: list[ValueRange] = [
            {
                "range": (str_range_name := str(range_name)),
                "values": self._process_values(
                    spreadsheet_id=spreadsheet_id,
                    range_name=str_range_name,
                    values=values,
                    align_columns=align_columns,
                ),
            }
            for range_name, values in data.items()
        ]  # type: ignore

        body: BatchUpdateValuesRequest = {
            "valueInputOption": value_input_option.value,
            "data": batch,
        }
        return (
            self.sheets.values()
            .batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body,
            )
            .execute()
        )

    def append(
        self,
        spreadsheet_id: str,
        range_name: str | Any,
        values: list[list[Any]],
        insert_data_option: InsertDataOption = InsertDataOption.overwrite,
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        align_columns: bool = True,
    ):
        """Appends values to a spreadsheet. Like `update`, but appends instead of overwrites.
        This means rows will be added to the spreadsheet if the input values are longer than the
        number of existing rows.

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            range_name (str | Any): The range to update. Can be a string or a SheetSlice.
            values (list[list[Any]]): The values to append.
            insert_data_option (InsertDataOption, optional): How the input data should be inserted. Defaults to InsertDataOption.overwrite.
            value_input_option (ValueInputOption, optional): How the input data should be interpreted. Defaults to ValueInputOption.user_entered.
            align_columns (bool, optional): Whether to align the columns of the spreadsheet with the keys of the first row of the values. Defaults to True.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(range_name)
        body: ValueRange = {
            "values": self._process_values(
                spreadsheet_id, range_name, values, align_columns
            )  # type: ignore
        }

        return (
            self.sheets.values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                body=body,
                insertDataOption=insert_data_option.value,
                valueInputOption=value_input_option.value,
            )
            .execute()
        )

    def clear(self, spreadsheet_id: str, range_name: str | Any):
        """Clears a range of values in a spreadsheet.

        Args:
            spreadsheet_id (str): The spreadsheet to update.
            range_name (str | Any): The range to update. Can be a string or a SheetSlice.
        """
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(range_name)

        return (
            self.sheets.values()
            .clear(spreadsheetId=spreadsheet_id, range=range_name)
            .execute()
        )

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
    def from_frame(df: pd.DataFrame) -> list[list[Any]]:
        """Converts a DataFrame to a list of lists to be used with sheets.update() & c.

        Args:
            df (pd.DataFrame): The DataFrame to convert.
        """
        df = df.fillna("")
        df = df.astype(str)

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
        else:
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
        sheet = self.get_sheet(spreadsheet_id, name=sheet_name)
        if not sheet:
            raise ValueError(f"Sheet '{sheet_name}' not found in the given spreadsheet")

        body: BatchUpdateSpreadsheetRequest = {
            "requests": self._resize_columns(sheet, width)
        }
        return (
            self.service.spreadsheets()
            .batchUpdate(spreadsheetId=spreadsheet_id, body=body)
            .execute()
        )
