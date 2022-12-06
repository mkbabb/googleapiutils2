from __future__ import annotations

import string
from enum import Enum
from typing import *

import pandas as pd
from google.oauth2.credentials import Credentials
from googleapiclient import discovery

from .utils import parse_file_id, to_base

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import (
        BatchUpdateValuesRequest,
        SheetsResource,
        UpdateValuesResponse,
        ValueRange,
        Spreadsheet,
    )

VERSION = "v4"


class ValueInputOption(Enum):
    unspecified = "INPUT_VALUE_OPTION_UNSPECIFIED"
    raw = "RAW"
    user_entered = "USER_ENTERED"


UPDATE_CHUNK_SIZE = 100


class Sheets:
    def __init__(self, creds: Credentials):
        self.creds = creds
        self.service: SheetsResource = discovery.build(
            "sheets", VERSION, credentials=self.creds
        )
        self.sheets: SheetsResource.SpreadsheetsResource = self.service.spreadsheets()

    @staticmethod
    def number_to_A1(row: int, col: int, sheet_name: str | None = None) -> str:
        t_col = "".join(
            map(
                lambda x: string.ascii_letters[x - 1].upper(),
                to_base(col, base=26),
            )
        )
        key = f"{t_col}{row}"

        if sheet_name is not None:
            return f"'{sheet_name}'!{key}"
        else:
            return key

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
        range_name: str,
        **kwargs: Any,
    ) -> ValueRange:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        return (
            self.sheets.values()
            .get(spreadsheetId=spreadsheet_id, range=range_name, **kwargs)
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

            start_row = i + row + 1
            end_row = i + chunk_size + row + 1

            start_col, end_col = col + 1, len(values) + col + 1

            start_ix, end_ix = (
                Sheets.number_to_A1(row=start_row, col=start_col),
                Sheets.number_to_A1(row=end_row, col=end_col),
            )

            range_name = f"{start_ix}:{end_ix}"

            yield range_name, t_values

    def batchUpdate(
        self,
        spreadsheet_id: str,
        data: list[ValueRange],
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        **kwargs: Any,
    ):
        spreadsheet_id = parse_file_id(spreadsheet_id)

        body: BatchUpdateValuesRequest = {
            "valueInputOption": value_input_option.value,
            "data": data,
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
        auto_batch: bool = False,
        **kwargs: Any,
    ):
        spreadsheet_id = parse_file_id(spreadsheet_id)

        body: ValueRange = {"values": values}

        if auto_batch and len(values) > UPDATE_CHUNK_SIZE:
            for t_range_name, t_values in self._chunk_values(values, row=0, col=0):
                t_range_name = f"{range_name}!{t_range_name}"

                self.update(
                    spreadsheet_id=spreadsheet_id,
                    range_name=t_range_name,
                    values=t_values,
                    **kwargs,
                )
            return None
        else:
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
    def to_frame(values: ValueRange) -> pd.DataFrame:
        df = pd.DataFrame(values["values"])
        df = df.rename(columns=df.iloc[0]).drop(df.index[0])
        return df

    @staticmethod
    def from_frame(df: pd.DataFrame) -> list[list[Any]]:
        data: list = df.fillna("").values.tolist()
        data.insert(0, list(df.columns))
        return data
