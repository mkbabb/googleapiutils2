from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

import pandas as pd
import pytest

from googleapiutils2 import Sheets, SheetSlice

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import File


@pytest.fixture
def sample_data():
    return {
        'basic': [['header1', 'header2', 'header3'], [1, 2, 3], [4, 5, 6], [7, 8, 9]],
        'dict_data': [
            {'header1': 1, 'header2': 2, 'header3': 3},
            {'header1': 4, 'header2': 5, 'header3': 6},
            {'header1': 7, 'header2': 8, 'header3': 9},
        ],
        'mixed_types': [
            ['str', 'int', 'float', 'bool', 'none'],
            ['text', 42, 3.14, True, None],
            ['more', -1, 2.718, False, ''],
        ],
    }


def assert_sheet_values(
    sheets: Sheets, sheet_id: str, range_name: str, expected_values: List[List[Any]]
):
    """Helper function to assert sheet values match expected values."""
    actual_values = sheets.values(sheet_id, range_name).get('values', [])
    assert actual_values == expected_values


@pytest.mark.parametrize(
    'slice_spec',
    [
        ('Sheet1', slice(...), slice(...)),  # Full sheet
        ('Sheet1', slice(2, ...), slice(...)),  # Skip header
        ('Sheet1', slice(2, ...), slice(1, 3)),  # First two columns, skip header
        ('Sheet1', slice(1, 3), slice(1, 3)),  # Specific range
    ],
)
def test_basic_update(
    test_sheet: File, sheets: Sheets, sample_data: Dict, slice_spec: tuple
):
    """Test basic update functionality with different slice specifications."""
    sheet_id = test_sheet['id']
    sheet_slice = SheetSlice[slice_spec]

    # First populate the sheet with basic data
    sheets.update(sheet_id, 'Sheet1', sample_data['basic'])

    values = sheets.values(sheet_id, 'Sheet1')['values']

    # Ensure the sheet is populated with the expected data
    assert len(values) == len(sample_data['basic'])

    # Update with sliced data
    update_data = [['updated'] * 3] * 2
    sheets.update(sheet_id, sheet_slice, update_data)

    # Verify update
    values = sheets.values(sheet_id, str(sheet_slice))['values']
    assert len(values) == len(update_data)


def test_dict_update(test_sheet: File, sheets: Sheets, sample_data: Dict):
    """Test updating with dictionary data and column alignment."""
    sheet_id = test_sheet['id']

    # Initial update with headers
    sheets.update(sheet_id, 'Sheet1', sample_data['basic'])

    # Update using dict data
    sheets.update(sheet_id, SheetSlice['Sheet1', 2:, ...], sample_data['dict_data'])

    # Verify update maintained column alignment
    values = sheets.values(sheet_id, 'Sheet1')['values']
    assert values[0] == sample_data['basic'][0]  # Headers unchanged
    assert len(values) == len(sample_data['dict_data']) + 1  # +1 for header


def test_mixed_type_update(test_sheet: File, sheets: Sheets, sample_data: Dict):
    """Test updating with mixed data types."""
    sheet_id = test_sheet['id']
    sheets.update(sheet_id, 'Sheet1', sample_data['mixed_types'])

    # Verify types are preserved as strings in sheet
    values = sheets.values(sheet_id, 'Sheet1')['values']
    assert all(isinstance(cell, str) for row in values[1:] for cell in row if cell)


@pytest.mark.parametrize('batch_size', [None, 1, 2, 5])
def test_batch_update(
    test_sheet: File, sheets: Sheets, sample_data: Dict, batch_size: int
):
    """Test batch update functionality with different batch sizes."""
    sheet_id = test_sheet['id']

    # Prepare batch update data
    batch_data = {
        SheetSlice['Sheet1', 1:3, :]: sample_data['basic'][1:3],
        SheetSlice['Sheet1', 3:5, :]: sample_data['basic'][1:3],
    }

    # Perform batch update
    sheets.batch_update(spreadsheet_id=sheet_id, data=batch_data, batch_size=batch_size)

    # Verify all updates were applied
    for range_name, expected_data in batch_data.items():
        actual_values = sheets.values(sheet_id, str(range_name))['values']
        assert actual_values == expected_data


def test_partial_column_update(test_sheet: File, sheets: Sheets):
    """Test updating only specific columns while preserving others."""
    sheet_id = test_sheet['id']

    # Initial data
    initial_data = [['A', 'B', 'C', 'D'], [1, 2, 3, 4], [5, 6, 7, 8]]
    sheets.update(sheet_id, 'Sheet1', initial_data)

    # Update only columns B and C
    update_data = [{'B': 20, 'C': 30}, {'B': 60, 'C': 70}]
    sheets.update(sheet_id, SheetSlice['Sheet1', 2:, ...], update_data)

    # Verify only specified columns were updated
    values = sheets.values(sheet_id, 'Sheet1')['values']
    assert values[1][0] == '1'  # Column A preserved
    assert values[1][1] == '20'  # Column B updated
    assert values[1][2] == '30'  # Column C updated
    assert values[1][3] == '4'  # Column D preserved


@pytest.mark.parametrize('dimension', ['rows', 'columns'])
def test_sparse_update(test_sheet: File, sheets: Sheets, dimension: str):
    """Test updating sparse data (skipping rows or columns)."""
    sheet_id = test_sheet['id']

    # Initial data
    initial_data = [['A', 'B', 'C', 'D'], [1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]
    sheets.update(sheet_id, 'Sheet1', initial_data)

    if dimension == 'rows':
        # Update only rows 1 and 3
        update_data = [
            {'A': 'new1', 'B': 'new2', 'C': 'new3', 'D': 'new4'},
            {'A': 'new9', 'B': 'new10', 'C': 'new11', 'D': 'new12'},
        ]
        sheets.update(sheet_id, SheetSlice['Sheet1', [2, 4], ...], update_data)
    else:
        # Update only columns A and C
        update_data = [
            {'A': 'new1', 'C': 'new3'},
            {'A': 'new5', 'C': 'new7'},
            {'A': 'new9', 'C': 'new11'},
        ]
        sheets.update(sheet_id, SheetSlice['Sheet1', 2:, ['A', 'C']], update_data)

    # Verify updates
    values = sheets.values(sheet_id, 'Sheet1')['values']
    assert len(values) == len(initial_data)


def test_update_with_formulas(test_sheet: File, sheets: Sheets):
    """Test updating cells with formulas."""
    sheet_id = test_sheet['id']

    # Initial data with formulas
    initial_data = [['A', 'B', 'Formula'], [1, 2, '=A2+B2'], [3, 4, '=A3+B3']]
    sheets.update(sheet_id, 'Sheet1', initial_data)

    # Verify formulas are preserved
    values = sheets.values(sheet_id, 'Sheet1', value_render_option='FORMULA')['values']
    assert values[1][2] == '=A2+B2'
    assert values[2][2] == '=A3+B3'


def test_error_handling(test_sheet: File, sheets: Sheets):
    """Test error handling for invalid updates."""
    sheet_id = test_sheet['id']

    with pytest.raises(ValueError):
        # Invalid sheet name
        sheets.update(sheet_id, 'NonexistentSheet', [['data']])

    with pytest.raises(ValueError):
        # Invalid range
        sheets.update(sheet_id, SheetSlice['Sheet1', -1:, ...], [['data']])


def test_concurrent_updates(test_sheet: File, sheets: Sheets):
    """Test handling of concurrent updates to the same sheet."""
    sheet_id = test_sheet['id']

    # Prepare batch updates that modify the same ranges
    batch_data_1 = {
        SheetSlice['Sheet1', 1:3, :]: [['A', 'B'], [1, 2]],
        SheetSlice['Sheet1', 3:5, :]: [['C', 'D'], [3, 4]],
    }

    batch_data_2 = {
        SheetSlice['Sheet1', 2:4, :]: [['X', 'Y'], [5, 6]],
        SheetSlice['Sheet1', 4:6, :]: [['Z', 'W'], [7, 8]],
    }

    # Perform concurrent batch updates
    sheets.batch_update(sheet_id, batch_data_1, batch_size=1)
    sheets.batch_update(sheet_id, batch_data_2, batch_size=1)

    # Verify final state
    values = sheets.values(sheet_id, 'Sheet1')['values']
    assert len(values) > 0
