from typing import *

from googleapiclient import discovery
from googleapiclient._apis.sheets.v4.resources import (
    SheetsResource,
    UpdateValuesResponse,
    ValueRange,
)

from utils import CREDS_PATH, SCOPES, TOKEN_PATH, APIBase, FilePath

VERSION = "v4"


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
        value_input_option: Optional[str] = "USER_ENTERED",
    ) -> UpdateValuesResponse:
        body = {"values": values}

        return (
            self.sheets.values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                body=body,
                valueInputOption=value_input_option,
            )
            .execute()
        )
