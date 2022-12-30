from __future__ import annotations

import functools
from typing import *

from ..utils import parse_file_id
from .misc import SheetSlice, ValueInputOption, ValueRenderOption, SheetSliceT
from .sheets import Sheets

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import (
        UpdateValuesResponse,
        ValueRange,
    )


class SheetsValueRange:
    def __init__(
        self,
        sheets: Sheets,
        spreadsheet_id: str,
        value_render_option: ValueRenderOption = ValueRenderOption.unformatted,
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
        sheet_name: str | None = None,
        range_name: str | None = None,
        **kwargs: Any,
    ):
        self.sheets = sheets
        self.spreadsheet_id = parse_file_id(spreadsheet_id)
        self.value_render_option = value_render_option
        self.value_input_option = value_input_option

        self._sheet_name = sheet_name
        self._range_name = range_name

        self.kwargs = kwargs

    @property
    def range_name(self) -> str:
        return str(SheetSliceT(self._sheet_name, self._range_name))

    @functools.cached_property
    def values(self) -> ValueRange:
        return self.sheets.values(
            spreadsheet_id=self.spreadsheet_id,
            range_name=self.range_name,
            value_render_option=self.value_render_option,
            **self.kwargs,
        )

    def update(self, values: list[list[Any]], **kwargs: Any) -> UpdateValuesResponse:
        return self.sheets.update(
            spreadsheet_id=self.spreadsheet_id,
            range_name=self.range_name,
            values=values,
            value_input_option=self.value_input_option,
            **kwargs,
        )

    def __getitem__(
        self,
        ixs: tuple[str, slice, slice]
        | tuple[str, slice]
        | tuple[slice, slice]
        | tuple[str, str],
    ) -> "SheetsValueRange":
        slc = SheetSlice[ixs]

        sheet_name = slc.sheet_name if slc.sheet_name is not None else self._sheet_name
        range_name = slc.range_name if slc.range_name is not None else self._range_name

        return self.__class__(
            self.sheets,
            self.spreadsheet_id,
            self.value_render_option,
            self.value_input_option,
            sheet_name,
            range_name,
            **self.kwargs,
        )
