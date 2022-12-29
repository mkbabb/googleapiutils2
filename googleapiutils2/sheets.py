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
        Spreadsheet,
        UpdateValuesResponse,
        ValueRange,
    )

    from .utils import FileId

VERSION = "v4"


class ValueInputOption(Enum):
    unspecified = "INPUT_VALUE_OPTION_UNSPECIFIED"
    raw = "RAW"
    user_entered = "USER_ENTERED"


class ValueRenderOption(Enum):
    formatted = "FORMATTED_VALUE"
    unformatted = "UNFORMATTED_VALUE"
    formula = "FORMULA"


def ix_to_str(ix: int | str | Ellipsis):
    return str(ix) if ix is not ... else ""


def format_range(range_name: str, sheet_name: str | None = None) -> str:
    if sheet_name is not None:
        return f"'{sheet_name}'!{range_name}"
    else:
        return range_name


def number_to_A1(row: int, col: int, sheet_name: str | None = None) -> str:
    t_col = (
        "".join(
            map(
                lambda x: string.ascii_letters[x - 1].upper(),
                to_base(col, base=26),
            )
        )
        if col is not ...
        else ""
    )
    t_row = ix_to_str(row)

    key = f"{t_col}{t_row}"
    return format_range(key, sheet_name)


def to_slice(*slices: slice | int) -> tuple[slice, ...]:
    func = lambda slc: slc if isinstance(slc, slice) else slice(slc, slc)
    return tuple(map(func, slices))


def slices_to_a1(slices: tuple[slice, slice] | slice | int) -> tuple[str, str | None]:
    match slices:
        case row_ix, col_ix:
            r1 = number_to_A1(row_ix.start, col_ix.start)
            r2 = number_to_A1(row_ix.stop, col_ix.stop)
            return r1, r2
        case row_ix if isinstance(row_ix, slice):
            return ix_to_str(row_ix.start), ix_to_str(row_ix.stop)
        case _:
            return ix_to_str(slices), None


def parse_sheets_ixs(ixs: tuple[str, slice, slice] | slice | int) -> str:
    sheet_name = "Sheet1"
    r1, r2 = "", None

    match ixs:
        case sheet_name, *slices if isinstance(sheet_name, str):
            r1, r2 = slices_to_a1(to_slice(*slices))
        case row_ix, col_ix:
            r1, r2 = slices_to_a1(to_slice(row_ix, col_ix))
        case row_ix:
            r1 = slices_to_a1(row_ix)

    range_name = f"{r1}:{r2}" if r2 is not None else str(r1)
    return format_range(range_name, sheet_name)


class SheetsValueRange:
    def __init__(
        self,
        sheets: SheetsResource.SpreadsheetsResource,
        spreadsheet_id: str,
        value_render_option: ValueRenderOption = ValueRenderOption.unformatted,
        **kwargs: Any,
    ):
        self.sheets = sheets
        self.spreadsheet_id = parse_file_id(spreadsheet_id)
        self.value_render_option = value_render_option
        self.kwargs = kwargs

    def values(
        self,
        range_name: str,
        **kwargs: Any,
    ) -> ValueRange:
        return (
            self.sheets.values()
            .get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                **kwargs,
            )
            .execute()
        )

    def __getitem__(self, ixs: tuple[str, slice, slice] | slice | int) -> ValueRange:
        range_name = parse_sheets_ixs(ixs)
        return self.values(
            range_name=range_name,
            valueRenderOption=self.value_render_option.value,
            **self.kwargs,
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
        spreadsheet_id: FileId,
        **kwargs: Any,
    ) -> Spreadsheet:
        spreadsheet_id = parse_file_id(spreadsheet_id)
        return self.sheets.get(spreadsheetId=spreadsheet_id, **kwargs).execute()

    def values(
        self,
        spreadsheet_id: FileId,
        range_name: str,
        value_render_option: ValueRenderOption = ValueRenderOption.unformatted,
        **kwargs: Any,
    ) -> ValueRange:
        return self.sheet(
            spreadsheet_id=spreadsheet_id, value_render_option=value_render_option
        ).values(range_name=range_name, **kwargs)

    def sheet(
        self,
        spreadsheet_id: FileId,
        value_render_option: ValueRenderOption = ValueRenderOption.unformatted,
        **kwargs: Any,
    ) -> "SheetsValueRange":
        spreadsheet_id = parse_file_id(spreadsheet_id)

        return SheetsValueRange(
            sheets=self.sheets,
            spreadsheet_id=spreadsheet_id,
            value_render_option=value_render_option,
            **kwargs,
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

    def batchUpdate(
        self,
        spreadsheet_id: FileId,
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
        spreadsheet_id: FileId,
        range_name: str,
        values: list[list[Any]],
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        auto_batch: bool = False,
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

    def clear(self, spreadsheet_id: FileId, range_name: str, **kwargs: Any):
        spreadsheet_id = parse_file_id(spreadsheet_id)

        return (
            self.sheets.values()
            .clear(spreadsheetId=spreadsheet_id, range=range_name, **kwargs)
            .execute()
        )

    @staticmethod
    def to_frame(values: ValueRange, **kwargs: Any) -> pd.DataFrame | None:
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
    def from_frame(df: pd.DataFrame) -> list[list[Any]]:
        df = df.fillna("")
        df = df.astype(str)

        data: list = df.values.tolist()
        data.insert(0, list(df.columns))
        return data
