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
from .sheets import Sheets, SheetsValues, SheetsRange

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import (
        BatchUpdateValuesRequest,
        SheetsResource,
        Spreadsheet,
        ValueRange,
    )


@dataclass(unsafe_hash=True)
class SheetsValueRange:
    """A class representing a range of values in a Google Sheet.
    Used in conjunction with both the Sheets class (facilitating all API calls) and the SheetSliceT class (facilitating indexing)

    When indexed into, provides one with a more dynamic, or informed, SheetSliceT object,
    as live shape information is used to determine the shape of the slice.

    As such, one can use a SheetsValueRange also as a key into a dict, e.g.:
    >>> MySheet = SheetsValueRange(sheets, spreadsheet_id)["MySheet"]
    >>> d = {MySheet: 1}
    >>> assert d[MySheet] == 1
    >>> assert str(MySheet) == "MySheet"

    Convenient when using the ellipsis notation.

    Note that a SheetsValueRange object doesn't anything other than sheet metadata, such as shape, or range information;
    no values are stored. Make as many as you want, they're cheap."""

    sheets: Sheets = field(hash=False)
    spreadsheet_id: str
    sheet_name: str = DEFAULT_SHEET_NAME
    range_name: str | None = None
    spreadsheet: Spreadsheet | None = field(init=False, default=None, hash=False)
    _cache: TTLCache = field(
        hash=False, default_factory=lambda: TTLCache(maxsize=128, ttl=80)
    )

    def __post_init__(self) -> None:
        self.spreadsheet_id = parse_file_id(self.spreadsheet_id)

    def __repr__(self) -> str:
        sheet_name = (
            self.sheet_name if self.sheet_name is not None else DEFAULT_SHEET_NAME
        )
        return format_range_name(sheet_name, self.range_name)

    def header(self) -> list[str]:
        return self.sheets._header(
            spreadsheet_id=self.spreadsheet_id, sheet_name=self.sheet_name
        )

    @cachedmethod(operator.attrgetter("_cache"))
    def shape(self) -> tuple[int, int]:
        sheet = self.sheets.get(self.spreadsheet_id, name=self.sheet_name)
        if sheet is not None:
            grid_properties = sheet.get("properties", {}).get("gridProperties", {})
            return (
                grid_properties.get("rowCount", 0),
                grid_properties.get("columnCount", 0),
            )
        return DEFAULT_SHEET_SHAPE

    @cachedmethod(operator.attrgetter("_cache"))
    def sheet_id(self) -> int:
        for sheet in self.sheets.get_spreadsheet(self.spreadsheet_id).get("sheets", []):
            properties = sheet.get("properties", {})
            if properties.get("title") == self.sheet_name:
                return properties.get("sheetId", 0)
        return 0

    def values(
        self,
        value_render_option: ValueRenderOption = ValueRenderOption.unformatted,
    ):
        return self.sheets.values(
            spreadsheet_id=self.spreadsheet_id,
            range_name=str(self),
            value_render_option=value_render_option,
        )

    def update(
        self,
        values: SheetsValues,
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        align_columns: bool = True,
    ):
        return self.sheets.update(
            spreadsheet_id=self.spreadsheet_id,
            range_name=str(self),
            values=values,
            value_input_option=value_input_option,
            align_columns=align_columns,
        )

    def rename(self, new_name: str):
        return self.sheets.rename(
            spreadsheet_id=self.spreadsheet_id,
            sheet_id=self.sheet_id(),
            new_name=new_name,
        )

    def append(
        self,
        values: SheetsValues,
        insert_data_option: InsertDataOption = InsertDataOption.overwrite,
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        align_columns: bool = True,
    ):
        return self.sheets.append(
            spreadsheet_id=self.spreadsheet_id,
            range_name=str(self),
            values=values,
            insert_data_option=insert_data_option,
            value_input_option=value_input_option,
            align_columns=align_columns,
        )

    def clear(self):
        return self.sheets.clear(
            spreadsheet_id=self.spreadsheet_id, range_name=str(self)
        )

    def to_frame(self, **kwargs) -> pd.DataFrame | None:
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
