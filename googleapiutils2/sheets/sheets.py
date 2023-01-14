from __future__ import annotations

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
    from googleapiclient._apis.sheets.v4.resources import (
        AppendValuesResponse,
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
        body: Spreadsheet | None = None,
    ):
        body: DefaultDict = nested_defaultdict(body if body else {})
        sheet_names = sheet_names if sheet_names is not None else [DEFAULT_SHEET_NAME]

        body["properties"]["title"] = title
        for n, sheet_name in enumerate(sheet_names):
            body["sheets"][n]["properties"]["title"] = sheet_name
        body["sheets"] = list(body["sheets"].values())

        return self.sheets.create(body=body).execute()

    def copy_to(
        self,
        from_spreadsheet_id: str,
        from_sheet_id: int,
        to_spreadsheet_id: str,
        **kwargs: Any,
    ):
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
                **kwargs,
            )
            .execute()
        )

    def get(
        self,
        spreadsheet_id: str,
        **kwargs: Any,
    ):
        spreadsheet_id = parse_file_id(spreadsheet_id)
        return self.sheets.get(spreadsheetId=spreadsheet_id, **kwargs).execute()

    def get_sheet(
        self,
        spreadsheet_id: str,
        name: str | None = None,
        sheet_id: int | None = None,
    ):
        spreadsheet_id = parse_file_id(spreadsheet_id)
        spreadsheet = self.get(spreadsheet_id)

        for sheet in spreadsheet["sheets"]:
            if sheet_id is not None and sheet["properties"]["sheetId"] == sheet_id:
                return sheet
            if name is not None and sheet["properties"]["title"] == name:
                return sheet

        return None

    def values(
        self,
        spreadsheet_id: str,
        range_name: str | Any = DEFAULT_SHEET_NAME,
        value_render_option: ValueRenderOption = ValueRenderOption.unformatted,
        **kwargs: Any,
    ):
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
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(SheetSlice[sheet_name, 1, ...])
        return self.values(spreadsheet_id=spreadsheet_id, range_name=range_name).get(
            "values", [[]]
        )[0]

    def _dict_to_values_align_columns(
        self,
        spreadsheet_id: str,
        range_name: str,
        rows: list[dict[str, Any]],
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
            other = pd.DataFrame(columns=header)
            frame = pd.concat([other, frame], ignore_index=True).fillna("")
            return frame.values.tolist()
        else:
            return [list(row.values()) for row in rows]

    def _process_values(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]] | list[dict[str, Any]],
        align_columns: bool = True,
    ) -> list[list[Any]]:

        if all((isinstance(value, dict) for value in values)):
            return self._dict_to_values_align_columns(
                spreadsheet_id=spreadsheet_id,
                range_name=range_name,
                rows=values,
                align_columns=align_columns,
            )
        else:
            return values

    def update(
        self,
        spreadsheet_id: str,
        range_name: str | Any,
        values: list[list[Any]] | list[dict],
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        align_columns: bool = True,
        **kwargs: Any,
    ):
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(range_name)
        values = self._process_values(spreadsheet_id, range_name, values, align_columns)

        return (
            self.sheets.values()
            .update(  # type: ignore
                spreadsheetId=spreadsheet_id,
                range=range_name,
                body={"values": values},
                valueInputOption=value_input_option.value,
                **kwargs,
            )
            .execute()
        )

    def batch_update(
        self,
        spreadsheet_id: str,
        data: dict[Any, list[list[Any]] | list[dict]],
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        align_columns: bool = True,
        **kwargs: Any,
    ) -> BatchUpdateValuesResponse:
        spreadsheet_id = parse_file_id(spreadsheet_id)

        batch: List[ValueRange] = [
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
        ]

        body: BatchUpdateValuesRequest = {
            "valueInputOption": value_input_option.value,
            "data": batch,
        }
        return (
            self.sheets.values()
            .batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body,
                **kwargs,
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
        **kwargs: Any,
    ) -> AppendValuesResponse:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(range_name)
        values = self._process_values(spreadsheet_id, range_name, values, align_columns)

        return (
            self.sheets.values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                body={"values": values},
                insertDataOption=insert_data_option.value,
                valueInputOption=value_input_option.value,
                **kwargs,
            )
            .execute()
        )

    def clear(
        self, spreadsheet_id: str, range_name: str | Any, **kwargs: Any
    ) -> ClearValuesResponse:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(range_name)

        return (
            self.sheets.values()
            .clear(spreadsheetId=spreadsheet_id, range=range_name, **kwargs)
            .execute()
        )

    @staticmethod
    def to_frame(values: ValueRange, **kwargs: Any) -> pd.DataFrame:
        if not len(rows := values.get("values", [])):
            return None

        columns = kwargs.pop("columns", []) + rows[0]
        rows = rows[1:] if len(rows) > 1 else []

        df = pd.DataFrame(rows, **kwargs)

        mapper = {i: col for i, col in enumerate(columns)}
        df.rename(columns=mapper, inplace=True)
        return df

    @staticmethod
    def from_frame(df: pd.DataFrame) -> list[list[Any]]:
        df = df.fillna("")
        df = df.astype(str)

        data: list = df.values.tolist()
        data.insert(0, list(df.columns))
        return data
