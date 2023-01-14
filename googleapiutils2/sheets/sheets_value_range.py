from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import *

import pandas as pd
from cachetools import TTLCache, cachedmethod

from ..utils import parse_file_id
from .misc import (
    DEFAULT_SHEET_NAME,
    DEFAULT_SHEET_SHAPE,
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


@dataclass(unsafe_hash=True)
class SheetsValueRange:
    sheets: Sheets = field(hash=False)
    spreadsheet_id: str
    sheet_name: str | None = None
    range_name: str | None = None
    spreadsheet: Spreadsheet | None = field(init=False, default=None, hash=False)
    _cache: TTLCache = field(default_factory=lambda: TTLCache(maxsize=128, ttl=80))

    def __post_init__(self) -> None:
        self.spreadsheet_id = parse_file_id(self.spreadsheet_id)

    def __repr__(self) -> str:
        sheet_name = (
            self.sheet_name if self.sheet_name is not None else DEFAULT_SHEET_NAME
        )
        return format_range_name(sheet_name, self.range_name)

    @cachedmethod(operator.attrgetter("_cache"))
    def shape(self) -> tuple[int, int]:
        for sheet in self.sheets.get(self.spreadsheet_id)["sheets"]:
            properties = sheet["properties"]

            if properties["title"] == self.sheet_name:
                grid_properties = properties["gridProperties"]
                return (
                    grid_properties["rowCount"],
                    grid_properties["columnCount"],
                )
                
        return DEFAULT_SHEET_SHAPE

    def values(
        self,
        value_render_option: ValueRenderOption = ValueRenderOption.unformatted,
        **kwargs: Any,
    ):
        return self.sheets.values(
            spreadsheet_id=self.spreadsheet_id,
            range_name=str(self),
            value_render_option=value_render_option,
            **kwargs,
        )

    def update(
        self,
        values: list[list[Any]],
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        **kwargs: Any,
    ):
        return self.sheets.update(
            spreadsheet_id=self.spreadsheet_id,
            range_name=str(self),
            values=values,
            value_input_option=value_input_option,
            **kwargs,
        )

    def append(
        self,
        values: list[list[Any]],
        insert_data_option: InsertDataOption = InsertDataOption.overwrite,
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        **kwargs: Any,
    ):
        return self.sheets.append(
            spreadsheet_id=self.spreadsheet_id,
            range_name=str(self),
            values=values,
            insert_data_option=insert_data_option,
            value_input_option=value_input_option,
            **kwargs,
        )

    def clear(self, **kwargs: Any):
        return self.sheets.clear(
            spreadsheet_id=self.spreadsheet_id, range_name=str(self), **kwargs
        )

    def to_frame(self, **kwargs: Any) -> pd.DataFrame:
        return self.sheets.to_frame(self.values(), **kwargs)

    def __getitem__(self, ixs: Any) -> SheetsValueRange:
        slc = SheetSliceT(
            sheet_name=self.sheet_name, range_name=self.range_name, shape=self.shape()
        )[ixs]
        return self.__class__(
            self.sheets,
            self.spreadsheet_id,
            slc.sheet_name,
            slc.range_name,
        )
