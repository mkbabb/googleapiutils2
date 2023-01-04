from __future__ import annotations

from dataclasses import dataclass, field
from typing import *

import pandas as pd

from ..utils import parse_file_id
from .misc import (
    DEFAULT_SHEET_NAME,
    InsertDataOption,
    SheetSliceT,
    ValueInputOption,
    ValueRenderOption,
    format_range_name,
)
from .sheets import Sheets

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import (
        BatchUpdateValuesRequest,
        SheetsResource,
        Spreadsheet,
        ValueRange,
    )

MAX_CACHE_SIZE = 4


@dataclass(unsafe_hash=True)
class SheetsValueRange:
    sheets: Sheets = field(hash=False)
    spreadsheet_id: str
    sheet_name: str | None = None
    range_name: str | None = None
    spreadsheet: Spreadsheet | None = field(init=False, default=None, hash=False)

    def __post_init__(self) -> None:
        self.spreadsheet_id = parse_file_id(self.spreadsheet_id)

    def __repr__(self) -> str:
        sheet_name = (
            self.sheet_name if self.sheet_name is not None else DEFAULT_SHEET_NAME
        )
        return format_range_name(sheet_name, self.range_name)

    async def sync(self) -> SheetsValueRange:
        self.spreadsheet = await self.sheets.get(self.spreadsheet_id)
        return self

    def shape(self) -> tuple[int, int] | None:
        if self.spreadsheet is None or self.sheet_name is None:
            return None

        for sheet in self.spreadsheet["sheets"]:
            properties = sheet["properties"]

            if properties["title"] == self.sheet_name:
                grid_properties = properties["gridProperties"]
                return (
                    grid_properties["rowCount"],
                    grid_properties["columnCount"],
                )
        return None

    async def values(
        self,
        value_render_option: ValueRenderOption = ValueRenderOption.unformatted,
        **kwargs: Any,
    ):
        return await self.sheets.values(
            spreadsheet_id=self.spreadsheet_id,
            range_name=str(self),
            value_render_option=value_render_option,
            **kwargs,
        )

    async def update(
        self,
        values: list[list[Any]],
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        **kwargs: Any,
    ):
        return await self.sheets.update(
            spreadsheet_id=self.spreadsheet_id,
            range_name=str(self),
            values=values,
            value_input_option=value_input_option,
            **kwargs,
        )

    async def append(
        self,
        values: list[list[Any]],
        insert_data_option: InsertDataOption = InsertDataOption.overwrite,
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        **kwargs: Any,
    ):
        return await self.sheets.append(
            spreadsheet_id=self.spreadsheet_id,
            range_name=str(self),
            values=values,
            insert_data_option=insert_data_option,
            value_input_option=value_input_option,
            **kwargs,
        )

    async def clear(self, **kwargs: Any):
        return await self.sheets.clear(
            spreadsheet_id=self.spreadsheet_id, range_name=str(self), **kwargs
        )

    async def to_frame(self, **kwargs: Any) -> pd.DataFrame:
        return self.sheets.to_frame(await self.values(), **kwargs)

    def __getitem__(self, ixs: Any) -> SheetsValueRange:
        slc = SheetSliceT(self.sheet_name, self.range_name, self.shape())[ixs]
        return self.__class__(
            self.sheets,
            self.spreadsheet_id,
            slc.sheet_name,
            slc.range_name,
        )
