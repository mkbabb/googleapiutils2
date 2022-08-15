from __future__ import annotations
from typing import *

from googleapiclient import discovery

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import (
        SheetsResource,
        UpdateValuesResponse,
        ValueRange,
    )


import string
from enum import Enum, auto

from utils import CREDS_PATH, SCOPES, TOKEN_PATH, APIBase, FilePath

VERSION = "v4"

from pathlib import Path


class ValueInputOption(Enum):
    RAW = auto()
    USER_ENTERED = auto()


class Sheets(APIBase):
    def __init__(
        self,
        token_path: FilePath = TOKEN_PATH,
        creds_path: FilePath = CREDS_PATH,
        is_service_account: bool = False,
        scopes: List[str] = SCOPES,
    ):
        super().__init__(token_path, creds_path, is_service_account, scopes)

        self.service: SheetsResource = discovery.build(
            "sheets", VERSION, credentials=self.creds
        )
        self.sheets = self.service.spreadsheets()

        self.sheets.create()

    @staticmethod
    def number_to_A1(row: int, col: int, sheet_name: Optional[str] = None):
        letter = ""

    def get(
        self,
        spreadsheet_id: str,
        range_name: str,
    ) -> ValueRange:
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
        return self.sheets.values().clear(
            spreadsheetId=spreadsheet_id, range=range_name
        )


def to_base(x: str | int, base: int, from_base: int = 10):
    if isinstance(x, str):
        x = int(x, base=from_base)

    y = []
    while x > 1:
        y.append(str(x := x % base))
    return "".join(reversed(y))


if __name__ == "__main__":
    name = Path("friday-institute-reports")
    dir = Path("auth")

    token_path = dir.joinpath(name.with_suffix(".token.pickle"))
    creds_path = dir.joinpath(name.with_suffix(".credentials.json"))

    sheets = Sheets(
        token_path=token_path, creds_path=creds_path, is_service_account=True
    )

    id = sheets.get_id_from_url(
        "https://drive.google.com/drive/folders/1fyQNBMxpytjHtgjYQJIjY9dczzZgKBxJ?usp=sharing"
    )

    t = to_base(123, 26)
    print(t)
