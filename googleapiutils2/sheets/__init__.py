from typing import TYPE_CHECKING

from .misc import (
    HorizontalAlignment,
    InsertDataOption,
    SheetsDimension,
    SheetsFormat,
    SheetSliceT,
    TextDirection,
    ValueInputOption,
    ValueRenderOption,
    VerticalAlignment,
    WrapStrategy,
)
from .sheets import Sheets
from .sheets_slice import SheetSlice, to_sheet_slice
from .sheets_value_range import SheetsValueRange

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import File
    from googleapiclient._apis.sheets.v4.resources import (
        AddSheetRequest,
        AppendValuesResponse,
        BatchUpdateSpreadsheetRequest,
        BatchUpdateSpreadsheetResponse,
        BatchUpdateValuesRequest,
        BatchUpdateValuesResponse,
        CellFormat,
        ClearValuesResponse,
        Color,
        ColorStyle,
        CopySheetToAnotherSpreadsheetRequest,
        DeleteSheetRequest,
        Padding,
        Request,
        Sheet,
        SheetProperties,
        SheetsResource,
        Spreadsheet,
        SpreadsheetProperties,
        TextFormat,
        UpdateDimensionPropertiesRequest,
        UpdateValuesResponse,
        ValueRange,
    )
