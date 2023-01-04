from __future__ import annotations

from collections import defaultdict
from typing import *

import pandas as pd
from google.oauth2.credentials import Credentials
from googleapiclient import discovery

from ..utils import asyncify, parse_file_id
from .misc import (
    DEFAULT_SHEET_NAME,
    VERSION,
    InsertDataOption,
    ValueInputOption,
    ValueRenderOption,
)

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import (
        BatchUpdateValuesRequest,
        BatchUpdateValuesResponse,
        ClearValuesResponse,
        SheetsResource,
        Spreadsheet,
        UpdateValuesResponse,
        ValueRange,
    )


@asyncify()
class Sheets:
    def __init__(self, creds: Credentials):
        self.creds = creds
        self.service: SheetsResource = discovery.build(
            "sheets", VERSION, credentials=self.creds
        )
        self.sheets: SheetsResource.SpreadsheetsResource = self.service.spreadsheets()

        self._batched_values: defaultdict[
            str, dict[str, list[list[Any]]]
        ] = defaultdict(dict)

    async def create(self) -> Spreadsheet:
        return self.sheets.create()

    async def get(
        self,
        spreadsheet_id: str,
        **kwargs: Any,
    ) -> Spreadsheet:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        return self.sheets.get(spreadsheetId=spreadsheet_id, **kwargs)

    async def values(
        self,
        spreadsheet_id: str,
        range_name: str | Any = DEFAULT_SHEET_NAME,
        value_render_option: ValueRenderOption = ValueRenderOption.unformatted,
        **kwargs: Any,
    ) -> ValueRange:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(range_name)
        return self.sheets.values().get(
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
        return self.sheets.values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body,
            **kwargs,
        )

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
        **kwargs: Any,
    ) -> UpdateValuesResponse:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(range_name)

        if auto_batch_size == 1:
            return self.sheets.values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                body={"values": values},
                valueInputOption=value_input_option.value,
                **kwargs,
            )
        batch = self._batched_values[spreadsheet_id]
        batch[range_name] = values

        if len(batch) >= auto_batch_size:
            return self._send_batched_values(
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
        **kwargs: Any,
    ):
        spreadsheet_id = parse_file_id(spreadsheet_id)
        range_name = str(range_name)
        return self.sheets.values().append(
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
        return self.sheets.values().clear(
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
