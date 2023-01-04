from __future__ import annotations

import functools
from typing import *

from ..utils import parse_file_id
from .misc import (
    InsertDataOption,
    SheetSlice,
    SheetSliceT,
    ValueInputOption,
    ValueRenderOption,
)
from .sheets import Sheets

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import (
        BatchUpdateValuesRequest,
        SheetsResource,
        Spreadsheet,
        ValueRange,
    )


class SheetsValueRange:
    MAX_CACHE_SIZE = 4

    def __init__(
        self,
        sheets: Sheets,
        spreadsheet_id: str,
        sheet_name: str | None = None,
        range_name: str | None = None,
    ):
        self.sheets = sheets
        self.spreadsheet_id = parse_file_id(spreadsheet_id)

        self._sheet_name = sheet_name
        self._range_name = range_name

        self._shape: tuple[int, int] | None = None

    @property
    @functools.lru_cache(MAX_CACHE_SIZE)
    def spreadsheet(self) -> Spreadsheet:
        return self.sheets.get(self.spreadsheet_id)

    @property
    @functools.lru_cache(MAX_CACHE_SIZE)
    def shape(self):
        if self._sheet_name is None:
            return None

        for sheet in self.spreadsheet["sheets"]:
            properties = sheet["properties"]

            if properties["title"] == self._sheet_name:
                grid_properties = properties["gridProperties"]
                self._shape = (
                    grid_properties["rowCount"],
                    grid_properties["columnCount"],
                )
                break

        return self._shape

    @property
    def range_name(self) -> str:
        return str(SheetSliceT(self._sheet_name, self._range_name))

    @property
    @functools.lru_cache(MAX_CACHE_SIZE)
    def values(
        self,
        value_render_option: ValueRenderOption = ValueRenderOption.unformatted,
        **kwargs,
    ):
        return self.sheets.values(
            spreadsheet_id=self.spreadsheet_id,
            range_name=self.range_name,
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
            range_name=self.range_name,
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
            range_name=self.range_name,
            values=values,
            insert_data_option=insert_data_option,
            value_input_option=value_input_option,
            **kwargs,
        )

    def clear(self, **kwargs: Any):
        return self.sheets.clear(
            spreadsheet_id=self.spreadsheet_id, range_name=self.range_name, **kwargs
        )

    def __getitem__(self, ixs: Any) -> "SheetsValueRange":
        slc = SheetSlice[ixs]

        sheet_name = slc.sheet_name if slc.sheet_name is not None else self._sheet_name
        range_name = slc.range_name if slc.range_name is not None else self._range_name

        return self.__class__(
            self.sheets,
            self.spreadsheet_id,
            sheet_name,
            range_name,
        )

    @staticmethod
    def _update_cache():
        SheetsValueRange.spreadsheet.fget.cache_clear()
        SheetsValueRange.shape.fget.cache_clear()
        SheetsValueRange.values.fget.cache_clear()
        return
