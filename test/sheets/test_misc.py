from __future__ import annotations

from typing import *

from googleapiutils2.sheets.misc import (
    DEFAULT_SHEET_SHAPE,
    A1_to_rc,
    A1_to_slices,
    format_range_name,
    int_to_A1,
    rc_to_A1,
    split_sheet_range,
)


def test_format_range_name():
    assert format_range_name("Sheet1", "A1") == "'Sheet1'!A1"
    assert format_range_name("'Sheet1'", "A1:B2") == "'Sheet1'!A1:B2"


def test_int_to_A1():
    assert int_to_A1(1) == "A"
    assert int_to_A1(26) == "Z"
    assert int_to_A1(27) == "AA"
    assert int_to_A1(28) == "AB"
    assert int_to_A1(52) == "AZ"
    assert int_to_A1(53) == "BA"


def test_rc_to_A1():
    assert rc_to_A1(1, 1) == "A1"
    assert rc_to_A1(1, 2) == "B1"
    assert rc_to_A1(2, 1) == "A2"
    assert rc_to_A1(2, 2) == "B2"
    assert rc_to_A1(26, 26) == "Z26"
    assert rc_to_A1(27, 27) == "AA27"
    assert rc_to_A1(28, 28) == "AB28"
    assert rc_to_A1(52, 52) == "AZ52"
    assert rc_to_A1(53, 53) == "BA53"


def test_A1_to_rc():
    assert A1_to_rc("A1") == (1, 1)
    assert A1_to_rc("B1") == (1, 2)
    assert A1_to_rc("A2") == (2, 1)
    assert A1_to_rc("B2") == (2, 2)
    assert A1_to_rc("AZ52") == (52, 52)
    assert A1_to_rc("BA53") == (53, 53)

    # row only
    assert A1_to_rc("1") == (1, None)
    assert A1_to_rc("2") == (2, None)
    # column only
    assert A1_to_rc("A") == (None, 1)
    assert A1_to_rc("B") == (None, 2)


def test_split_sheet_range():
    assert split_sheet_range("A1:B2")[1] == "A1:B2"
    assert split_sheet_range("A1")[0] == "A1"

    range_name = "Sheet1!A1:B2"
    reversed_range_name = split_sheet_range(range_name)

    assert reversed_range_name[0] == "Sheet1"
    assert reversed_range_name[1] == "A1:B2"

    # handle quoted sheet names
    range_name = "'Sheet 1'!A1:B2"
    reversed_range_name = split_sheet_range(range_name)

    assert reversed_range_name[0] == "'Sheet 1'"
    assert reversed_range_name[1] == "A1:B2"


def test_A1_to_slices():
    # Test when the range includes the first two cells in the top two rows
    assert A1_to_slices("Sheet1!A1:B2", DEFAULT_SHEET_SHAPE) == (
        slice(1, 2),
        slice(1, 2),
    )
    # Test when range includes all the cells in the first column
    assert A1_to_slices("Sheet1!A:A", DEFAULT_SHEET_SHAPE) == (
        slice(1, DEFAULT_SHEET_SHAPE[0]),
        slice(1, 1),
    )
    # Test when range includes all the cells in the first two rows
    assert A1_to_slices("Sheet1!1:2", DEFAULT_SHEET_SHAPE) == (
        slice(1, 2),
        slice(1, DEFAULT_SHEET_SHAPE[1]),
    )
    # Test when range includes all the cells of the first column, from row 5 onward
    assert A1_to_slices("Sheet1!A5:A", DEFAULT_SHEET_SHAPE) == (
        slice(5, DEFAULT_SHEET_SHAPE[0]),
        slice(1, 1),
    )
    # Test when range includes the first two cells in the top two rows of the first visible sheet
    assert A1_to_slices("A1:B2", DEFAULT_SHEET_SHAPE) == (slice(1, 2), slice(1, 2))
    # Test when range includes all cells in a sheet
    assert A1_to_slices("Sheet1", DEFAULT_SHEET_SHAPE) == (
        slice(1, DEFAULT_SHEET_SHAPE[0]),
        slice(1, DEFAULT_SHEET_SHAPE[1]),
    )
    # Test when range includes all the cells in the first column of a sheet named "My Custom Sheet"
    assert A1_to_slices("'My Custom Sheet'!A:A", DEFAULT_SHEET_SHAPE) == (
        slice(1, DEFAULT_SHEET_SHAPE[0]),
        slice(1, 1),
    )

    # Test when range includes all the cells in a sheet named "My Custom Sheet"
    assert A1_to_slices("'My Custom Sheet'", DEFAULT_SHEET_SHAPE) == (
        slice(1, DEFAULT_SHEET_SHAPE[0]),
        slice(1, DEFAULT_SHEET_SHAPE[1]),
    )
