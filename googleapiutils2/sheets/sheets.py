from __future__ import annotations

from collections import defaultdict
from typing import *

import pandas as pd
from google.oauth2.credentials import Credentials
from googleapiclient import discovery

from ..utils import asyncify, nested_defaultdict, parse_file_id
from .misc import (
    DEFAULT_SHEET_NAME,
    VERSION,
    InsertDataOption,
    ValueInputOption,
    ValueRenderOption,
    SheetSlice,
    SheetSliceT,
    reverse_sheet_range,
)

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import (
        AppendValuesResponse,
        BatchUpdateValuesRequest,
        BatchUpdateValuesResponse,
        ClearValuesResponse,
        Sheet,
        SheetProperties,
        SheetsResource,
        Spreadsheet,
        SpreadsheetProperties,
        UpdateValuesResponse,
        ValueRange,
        CopySheetToAnotherSpreadsheetRequest,
    )


@asyncify()
class Sheets:
    def __init__(self, creds: Credentials):
        self.creds = creds
        self.service: SheetsResource = discovery.build(  # type: ignore
            "sheets", VERSION, credentials=self.creds
        )
        self.sheets: SheetsResource.SpreadsheetsResource = self.service.spreadsheets()

        self._batched_values: defaultdict[
            str, dict[str, list[list[Any]]]
        ] = defaultdict(dict)

    async def create(
        self,
        title: str,
        sheet_names: list[str] = None,
        body: Spreadsheet = None,
    ) -> Spreadsheet:
        body = nested_defaultdict(body if body else {})
        sheet_names = sheet_names if sheet_names is not None else [DEFAULT_SHEET_NAME]

        body["properties"]["title"] = title
        for n, sheet_name in enumerate(sheet_names):
            body["sheets"][n]["properties"]["title"] = sheet_name
        body["sheets"] = list(body["sheets"].values())

        return self.sheets.create(body=body)  # type: ignore

    async def copy_to(
        self,
        from_spreadsheet_id: str,
        from_sheet_id: int,
        to_spreadsheet_id: str,
        **kwargs: Any,
    ) -> SheetProperties:
        from_spreadsheet_id, to_spreadsheet_id = (
            parse_file_id(from_spreadsheet_id),
            parse_file_id(to_spreadsheet_id),
        )
        body: CopySheetToAnotherSpreadsheetRequest = {
            "destinationSpreadsheetId": to_spreadsheet_id
        }

        return self.sheets.sheets().copyTo(
            spreadsheetId=from_spreadsheet_id,
            sheetId=from_sheet_id,
            body=body,
            **kwargs,
        )

    async def get(
        self,
        spreadsheet_id: str,
        **kwargs: Any,
    ) -> Spreadsheet:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        return self.sheets.get(spreadsheetId=spreadsheet_id, **kwargs)  # type: ignore

    async def get_sheet(
        self,
        spreadsheet_id: str,
        name: str | None = None,
        sheet_id: int | None = None,
    ) -> Sheet | None:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        spreadsheet = await self.get(spreadsheet_id)

        for sheet in spreadsheet["sheets"]:
            if sheet_id is not None and sheet["properties"]["sheetId"] == sheet_id:
                return sheet
            if name is not None and sheet["properties"]["title"] == name:
                return sheet

        return None

    async def values(
        self,
        spreadsheet_id: str,
        range_name: str | Any = DEFAULT_SHEET_NAME,
        value_render_option: ValueRenderOption = ValueRenderOption.unformatted,
        **kwargs: Any,
    ) -> ValueRange:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(range_name)

        return self.sheets.values().get(  # type: ignore
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueRenderOption=value_render_option.value,
            **kwargs,
        )

    async def batch_update(
        self,
        spreadsheet_id: str,
        data: dict[Any, list[list[Any]]],
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        **kwargs: Any,
    ) -> BatchUpdateValuesResponse:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        body: BatchUpdateValuesRequest = {
            "valueInputOption": value_input_option.value,
            "data": [
                {"range": str(range_name), "values": values}
                for range_name, values in data.items()
            ],
        }
        return self.sheets.values().batchUpdate(  # type: ignore
            spreadsheetId=spreadsheet_id,
            body=body,
            **kwargs,
        )

    async def _header(self, spreadsheet_id: str, range_name: str = DEFAULT_SHEET_NAME):
        sheet_name, _ = reverse_sheet_range(range_name)
        return (await self.values(spreadsheet_id, SheetSlice[sheet_name, 1, ...])).get(
            "values", [[]]
        )[0]

    async def _dict_to_values_align_columns(
        self,
        spreadsheet_id: str,
        range_name: str,
        rows: list[dict[str, Any]],
        align_columns: bool = True,
    ):
        if align_columns:
            header = await self._header(spreadsheet_id, range_name)
            header = pd.Index(header).astype(str)

            other = pd.DataFrame(rows)
            other.index = other.index.astype(str)

            if len(diff := other.columns.difference(header)):
                header = header.append(diff)
                sheet_name, _ = reverse_sheet_range(range_name)
                await self.update(
                    spreadsheet_id,
                    SheetSlice[sheet_name, 1, ...],
                    [header.tolist()],
                )

            frame = pd.DataFrame(columns=header)
            frame = pd.concat([frame, other], ignore_index=True, copy=False).fillna("")
            values = frame.values.tolist()
            return values
        else:
            values = [list(rows[0].keys())]
            values += [list(row.values()) for row in rows]
            return values

    async def _process_values(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]] | list[dict[str, Any]],
        align_columns: bool = True,
    ) -> list[list[Any]]:
        if isinstance(values[0], dict):
            return await self._dict_to_values_align_columns(
                spreadsheet_id, range_name, values, align_columns
            )
        return values

    async def _send_batched_values(
        self,
        spreadsheet_id: str,
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        **kwargs: Any,
    ):
        batch = self._batched_values[spreadsheet_id]
        if not len(batch):
            return

        res = await self.batch_update(
            spreadsheet_id=spreadsheet_id,
            data=batch,
            value_input_option=value_input_option,
            **kwargs,
        )
        batch.clear()
        return res

    async def _send_all_batches(self) -> None:
        for spreadsheet_id in self._batched_values.keys():
            await self._send_batched_values(spreadsheet_id)
        self._batched_values.clear()

    async def update(
        self,
        spreadsheet_id: str,
        range_name: str | Any,
        values: list[list[Any]],
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        auto_batch_size: int = 1,
        align_columns: bool = True,
        **kwargs: Any,
    ) -> UpdateValuesResponse | None:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(range_name)
        values = await self._process_values(
            spreadsheet_id, range_name, values, align_columns
        )

        if auto_batch_size == 1:
            return self.sheets.values().update(  # type: ignore
                spreadsheetId=spreadsheet_id,
                range=range_name,
                body={"values": values},
                valueInputOption=value_input_option.value,
                **kwargs,
            )

        batch = self._batched_values[spreadsheet_id]
        batch[range_name] = values

        if len(batch) >= auto_batch_size or auto_batch_size == -1:
            return await self._send_batched_values(  # type: ignore
                spreadsheet_id, value_input_option, **kwargs
            )
        else:
            return None

    async def append(
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
        values = await self._process_values(
            spreadsheet_id, range_name, values, align_columns
        )

        return self.sheets.values().append(  # type: ignore
            spreadsheetId=spreadsheet_id,
            range=range_name,
            body={"values": values},
            insertDataOption=insert_data_option.value,
            valueInputOption=value_input_option.value,
            **kwargs,
        )

    async def clear(
        self, spreadsheet_id: str, range_name: str | Any, **kwargs: Any
    ) -> ClearValuesResponse:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(range_name)

        return self.sheets.values().clear(  # type: ignore
            spreadsheetId=spreadsheet_id, range=range_name, **kwargs
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
