from __future__ import annotations

import string
from enum import Enum, auto
from pathlib import Path
from typing import *

import pandas as pd
from google.oauth2.credentials import Credentials
from googleapiclient import discovery

from .utils import get_oauth2_creds, parse_file_id

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import (
        SheetsResource,
        UpdateValuesResponse,
        ValueRange,
    )

VERSION = "v4"


class ValueInputOption(Enum):
    RAW = auto()
    USER_ENTERED = auto()


class Sheets:
    def __init__(self, creds: Credentials):
        self.creds = creds
        self.service: SheetsResource = discovery.build(
            "sheets", VERSION, credentials=self.creds
        )
        self.sheets = self.service.spreadsheets()

    @staticmethod
    def number_to_A1(row: int, col: int, sheet_name: Optional[str] = None) -> str:
        t_col = "".join(
            map(
                lambda x: string.ascii_letters[x - 1],
                to_base(col, base=26),
            )
        )
        key = f"{t_col}{row}"

        if sheet_name is not None:
            return f"'{sheet_name}'!{key}"
        else:
            return key

    def create(self):
        return self.sheets.create()

    def get(
        self,
        spreadsheet_id: str,
        range_name: str,
    ) -> ValueRange:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        return (
            self.sheets.values()
            .get(spreadsheetId=spreadsheet_id, range=range_name)
            .execute()
        )

    def update(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]],
        value_input_option: Optional[ValueInputOption] = ValueInputOption.USER_ENTERED,
    ) -> UpdateValuesResponse:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        body = {"values": values}

        return (
            self.sheets.values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                body=body,
                valueInputOption=str(value_input_option),
            )
            .execute()
        )

    def clear(
        self,
        spreadsheet_id: str,
        range_name: str,
    ):
        spreadsheet_id = parse_file_id(spreadsheet_id)
        return self.sheets.values().clear(
            spreadsheetId=spreadsheet_id, range=range_name
        )


def to_base(x: str | int, base: int, from_base: int = 10) -> list[int]:
    if isinstance(x, str):
        x = int(x, base=from_base)

    y = []
    while x != 0:
        y.append(x % base)
        x //= base

    return y[::-1]


if __name__ == "__main__":
    name = Path("friday-institute-reports")
    dir = Path("auth")

    token_path = dir.joinpath(name.with_suffix(".token.pickle"))
    config_path = dir.joinpath(name.with_suffix(".credentials.json"))

    google_creds = get_oauth2_creds(
        token_path=token_path, client_config=config_path, is_service_account=True
    )

    sheets = Sheets(google_creds)

    url = "https://docs.google.com/spreadsheets/d/11hX5E0V-OwRI9wBvVRIh98mlBlN_NwVivaXhk0NTKlI/edit#gid=150061767"

    t = sheets.get(url, "Config")
    df = pd.DataFrame(t["values"])
    df = df.rename(columns=df.iloc[0]).drop(df.index[0])
    print(df)
