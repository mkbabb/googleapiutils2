from __future__ import annotations

from typing import *


from google.oauth2.credentials import Credentials
from googleapiclient import discovery

from ..utils import parse_file_id
from .misc import DEFAULT_SHEET_NAME, VERSION, ValueInputOption, ValueRenderOption

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import (
        BatchUpdateValuesRequest,
        SheetsResource,
        Spreadsheet,
        ValueRange,
    )


class Sheets:
    UPDATE_CHUNK_SIZE: Final = 100

    def __init__(self, creds: Credentials):
        self.creds = creds
        self.service: SheetsResource = discovery.build(
            "sheets", VERSION, credentials=self.creds
        )
        self.sheets: SheetsResource.SpreadsheetsResource = self.service.spreadsheets()

    def create(self) -> Spreadsheet:
        return self.sheets.create().execute()

    def get(
        self,
        spreadsheet_id: str,
        **kwargs: Any,
    ) -> Spreadsheet:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        return self.sheets.get(spreadsheetId=spreadsheet_id, **kwargs).execute()

    def values(
        self,
        spreadsheet_id: str,
        range_name: str = DEFAULT_SHEET_NAME,
        value_render_option: ValueRenderOption = ValueRenderOption.unformatted,
        **kwargs: Any,
    ) -> ValueRange:
        spreadsheet_id = parse_file_id(spreadsheet_id)
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

    @staticmethod
    def _chunk_values(
        values: list[list[Any]],
        row: int = 0,
        col: int = 0,
        chunk_size: int = UPDATE_CHUNK_SIZE,
    ) -> Iterable[tuple[str, list[list]]]:
        chunk_size = min(len(values), chunk_size)

        for i in range(0, len(values), chunk_size):
            t_values = values[i : i + chunk_size]
            # TODO! use new logic from slicing
            start_row, end_row = i + row + 1, i + chunk_size + row + 1
            start_col, end_col = col + 1, len(values) + col + 1

            start_ix, end_ix = (
                number_to_A1(row=start_row, col=start_col),
                number_to_A1(row=end_row, col=end_col),
            )
            range_name = f"{start_ix}:{end_ix}"

            yield range_name, t_values

    def batch_update(
        self,
        spreadsheet_id: str,
        data: dict[str, list[list[Any]]],
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        **kwargs: Any,
    ):
        spreadsheet_id = parse_file_id(spreadsheet_id)
        body: BatchUpdateValuesRequest = {
            "valueInputOption": value_input_option.value,
            "data": [
                {"range": str(range_name), "values": values}
                for range_name, values in data.items()
            ],
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

    def update(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]],
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        **kwargs: Any,
    ):
        spreadsheet_id = parse_file_id(spreadsheet_id)
        body: ValueRange = {"values": values}
        return (
            self.sheets.values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                body=body,
                valueInputOption=value_input_option.value,
                **kwargs,
            )
            .execute()
        )

    def clear(self, spreadsheet_id: str, range_name: str, **kwargs: Any):
        spreadsheet_id = parse_file_id(spreadsheet_id)
        return (
            self.sheets.values()
            .clear(spreadsheetId=spreadsheet_id, range=range_name, **kwargs)
            .execute()
        )

    @staticmethod
    def to_frame(values: ValueRange, **kwargs: Any):
        import pandas as pd

        if not len(rows := values.get("values", [])):
            return None

        columns = kwargs.pop("columns", []) + rows[0]
        rows = rows[1:] if len(rows) > 1 else []

        df = pd.DataFrame(rows, **kwargs)

        cols = df.shape[1]
        left_cols = columns[:cols]
        df.columns = left_cols
        df = df.reindex(columns=columns)

        return df

    @staticmethod
    def from_frame(df) -> list[list[Any]]:
        df = df.fillna("")
        df = df.astype(str)

        data: list = df.values.tolist()
        data.insert(0, list(df.columns))
        return data
