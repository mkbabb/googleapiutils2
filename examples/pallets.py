import json
import re
import time
from pathlib import Path
from typing import *

import numpy as np
import pandas as pd
from litellm import ModelResponse, completion
from loguru import logger
import datetime

from googleapiutils2 import Sheets, cache_with_stale_interval

Model = Literal[
    "claude-3-5-sonnet-20240620",
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-4o-mini",
    "groq/llama-3.1-8b-instant",
    "groq/llama-3.1-70b-versatile",
    "groq/llama-3.1-405b-reasoning",
]

# Configure logger
logger.add("./log/pallets.log", rotation="10 MB")


REQUIRED_HEADERS = [
    'ERD Pallet Number',
    'Qty:',
    'Equipment',
    'Equipment Description',
]


def remove_blank_rows(df: pd.DataFrame) -> pd.DataFrame:
    # Remove fully blank rows
    initial_rows = len(df)
    df = df.replace('nan', np.nan)
    df = df.dropna(how='all')
    removed_rows = initial_rows - len(df)

    if removed_rows > 0:
        logger.debug(f"Removed {removed_rows} blank rows")

    # replace all empty strings and pure whitespace strings with nan
    df = df.replace(r'^\s*$', np.nan, regex=True)

    initial_rows = len(df)
    df = df[~df.isna().all(axis=1)]

    removed_rows = initial_rows - len(df)

    if removed_rows > 0:
        logger.debug(f"Removed {removed_rows} blank rows")

    return df.reset_index(drop=True)


def strip_response(response: str) -> str:
    """Clean and normalize responses from the API."""
    quote_chars = ['"', "'", """, """, "```", "json", "`"]
    result = response

    for char in quote_chars:
        result = result.strip().strip("\n").strip(char)

    return result


def handle_response(response: ModelResponse) -> dict[str, Any] | None:
    """Handle the response from the API."""
    if not len(response.choices):
        return None

    content = response.choices[0].message.content  # type: ignore
    if content is None:
        return None

    content = strip_response(content)
    try:
        if len(data := json.loads(content)):
            return data
    except Exception as e:
        logger.error(f"Failed to parse API response: {e}")
        return None

    return None


@cache_with_stale_interval(datetime.timedelta(days=1))
def get_completion(system_msg: str, prompt: str, model: Model) -> dict[str, Any] | None:
    """Wrapper function for making API calls with error handling."""
    try:
        response = completion(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            drop_params=True,
        )
        return handle_response(response) or None  # type: ignore
    except Exception as e:
        logger.error(f"API call failed: {e}")
        return None


def normalize_column_name(col: str, model: Model) -> str:
    """Use AI to normalize column names to standard format."""
    system_msg = f"""You are an AI that normalizes column names to a standard format. 
The required output formats are: {REQUIRED_HEADERS}.

A few mappings of anomalies to the required headers are:
- Model Number -> Equipment 

Return a JSON object with a single key 'normalized_name' containing the closest matching required header.
If no match is found, return the original name."""

    prompt = f"Normalize this column name: '{col}'"

    if result := get_completion(system_msg, prompt, model):
        return result.get("normalized_name", col)

    return col


def extract_pallet_number(text: str, model: Model) -> str | None:
    """Use AI to extract pallet number from text."""
    system_msg = """Extract the ERD pallet number from the text.

Pallet numbers are usually a number with the prefix or suffix 'ERD' or 'Pallet'.

Examples:
- ERD12345 -> 12345
- Pallet-12345 -> 12345
- 12345-ERD -> 12345
- 20220422ERD Sec. -> 20220422
- 2022-04-22 -> 20220422
- 20231123-ERDPallet_3080Warehouse.xlsx -> 20231123
- ERDPALLET3080SN_20240923.xlsx -> 20240923
- 20240718, 1, C3560CX-12PCS, Cisco 3500  Series POE Switch -> null (full valid row of data)

Return a JSON object with a single key 'pallet_number' containing just the number.

Format the pallet number as a single number without any dashes, spaces, or prefixes.

If no pallet number is found, return null.
If the input text is a full row of data, return null.
"""
    prompt = f"Extract the ERD pallet number from this text: '{text}'"

    if result := get_completion(system_msg, prompt, model):
        pallet_number = result.get("pallet_number")

        if pallet_number is not None:
            return str(pallet_number)

    return None


def validate_data_row(row: dict[str, str], model: Model) -> bool:
    """Use AI to validate if a data row is valid and meaningful."""
    system_msg = """Determine if this row of ERD pallet data is valid and meaningful.
Valid rows should have equipment information and quantities that make sense together.
Return a JSON object with a single key 'is_valid' containing true/false."""

    prompt = f"Validate this ERD pallet data row: {json.dumps(row)}"

    if result := get_completion(system_msg, prompt, model):
        return bool(result.get("is_valid", False))

    return True  # Default to accepting the row if AI fails


def validate_header_row(row: pd.Series, model: Model) -> tuple[bool, list]:
    """
    Validate that a row contains all required column headers and normalize them.

    Args:
        row: Series to check for required headers

    Returns:
        Tuple of (is_valid, normalized_headers)
    """
    normalized_headers = []

    for val in row.values:
        # skip nan values
        if pd.isna(val) or not str(val).strip() or str(val).lower() == 'nan':
            normalized_headers.append("nan")
            continue

        val = str(val).strip()

        # If the value is already a required header, keep it as is:
        if val in REQUIRED_HEADERS:
            normalized_headers.append(val)
        else:
            normalized = normalize_column_name(col=val, model=model)
            normalized_headers.append(normalized)

    # Check if all required headers are present in normalized form
    has_all_required = set(REQUIRED_HEADERS).issubset(normalized_headers)

    return has_all_required, normalized_headers


def process_single_dataset(
    df: pd.DataFrame,
    filename: str,
    model: Model,
    sheet_name: str | None = None,
) -> pd.DataFrame | None:
    """
    Process a single dataset from either a CSV or Excel sheet.

    Args:
        data: The input dataframe
        filename: Source filename
        sheet_name: Sheet name for Excel files

    Returns:
        Processed dataframe or None if invalid data
    """
    logger.info(
        f"Processing dataset from {filename}{' - ' + sheet_name if sheet_name else ''}"
    )

    # Convert all columns to string to handle mixed types
    df = df.astype(str)
    df = remove_blank_rows(df)

    # Ignore entirely blank dfs:
    if df.empty:
        logger.warning(f"Ignoring empty dataset from {filename}")
        return None

    # Find the header row containing all required columns

    header_ix: int | None = None
    normalized_headers: list | None = None

    for idx, row in df.iterrows():
        is_valid, headers = validate_header_row(row=row, model=model)

        if not is_valid:
            continue

        header_ix = int(idx)  # type: ignore
        normalized_headers = headers

        logger.debug(f"Found valid header row at index {header_ix}")
        break

    if header_ix is None or normalized_headers is None:
        logger.warning(
            f"No valid header row found in {filename}{' - ' + sheet_name if sheet_name else ''}"
        )
        return None

    # Insert the original headers as the first row:
    df = pd.concat([pd.DataFrame([df.columns], columns=df.columns), df]).reset_index(
        drop=True
    )

    # Find the overall pallet number
    overall_pallet_ix: int | None = None
    overall_pallet: str | None = None

    # only search a maximum of 20 rows:
    search_rows = min(20, len(df))
    for idx, row in df.iloc[:search_rows].iterrows():
        # Ignore all nan values, string nans too:
        if row.isna().all() or row.astype(str).str.lower().str.strip().eq('nan').all():
            continue

        row_text = ', '.join(str(val) for val in row.values)

        overall_pallet = extract_pallet_number(text=row_text, model=model)
        if overall_pallet is not None:
            logger.debug(f"Found pallet number {overall_pallet} at row {idx}")
            # remove the row with the pallet number:
            overall_pallet_ix = int(idx)  # type: ignore
            break

    # Convert the overall pallet number to a datetime
    if overall_pallet is None:
        # Try to parse it from the filename:
        overall_pallet = extract_pallet_number(text=filename, model=model)

    if overall_pallet is None:
        logger.warning(
            f"No overall pallet number found in {filename}{' - ' + sheet_name if sheet_name else ''}"
        )
        return None

    logger.success(f"Found overall pallet number: {overall_pallet}")

    # drop everything before the header row + 2 to account for the inserted header row:
    df = df.iloc[header_ix + 2 :].reset_index(drop=True)
    # if the overall pallet number was found,
    # and it was after the header, compute the new index and drop it:
    if overall_pallet_ix is not None and overall_pallet_ix > (header_ix + 1):
        overall_pallet_ix = (overall_pallet_ix - header_ix) - 2
        df = df.drop(overall_pallet_ix).reset_index(drop=True)

    # Normalize the column headers
    df.columns = normalized_headers  # type: ignore
    # Remove any columns not in the required headers
    df = df[[col for col in df.columns if col in REQUIRED_HEADERS]]

    # Forward fill the ERD Pallet Number column
    pallet_col = 'ERD Pallet Number'
    df[pallet_col] = df[pallet_col].replace('nan', np.nan)

    # If the entire column is blank, fill with the overall pallet number
    if df[pallet_col].isna().all():
        logger.info(
            f"Filling empty pallet column with overall pallet number {overall_pallet}"
        )
        df[pallet_col] = overall_pallet

    df[pallet_col] = df[pallet_col].ffill()

    # We only care about the required columns, in that order:
    filtered_headers = [col for col in df.columns if col in REQUIRED_HEADERS]
    df = df[filtered_headers]

    # Add metadata columns
    df['Overall_Pallet_Date'] = overall_pallet

    df['Sheet_Name'] = sheet_name if sheet_name else None
    df['Source_File'] = filename

    logger.success(f"Successfully processed dataset with {len(df)} rows")
    return df


def process_file(filepath: str | Path, model: Model) -> pd.DataFrame | None:
    """
    Process a single file (either CSV or Excel).

    Args:
        filepath: Path to the file

    Returns:
        Processed dataframe or None if invalid data
    """
    filename = Path(filepath).name
    logger.info(f"Processing file: {filename}")

    if str(filepath).endswith('.csv'):
        df = pd.read_csv(filepath, dtype=str)
        return process_single_dataset(df=df, filename=filename, model=model)

    elif str(filepath).endswith('.xlsx'):
        dfs: list[pd.DataFrame] = []
        excel_file = pd.ExcelFile(filepath)

        for sheet_name in excel_file.sheet_names:
            logger.debug(f"Processing sheet: {sheet_name}")
            df = pd.read_excel(filepath, sheet_name=sheet_name, dtype=str)
            processed_df = process_single_dataset(
                df=df, filename=filename, model=model, sheet_name=str(sheet_name)
            )

            if processed_df is not None:
                dfs.append(processed_df)

        if dfs:
            result = pd.concat(dfs)
            logger.success(f"Successfully processed file with {len(result)} total rows")

            return result

        return None

    return None


def process_directory(
    directory_path: str | Path,
    model: Model,
    sheet_url: str,
    sheet_name: str,
    sheets: Sheets,
) -> None:
    directory_path = Path(directory_path)
    logger.info(f"Processing directory: {directory_path}")

    # Find all CSV and Excel files in the directory using a glob pattern
    filepaths = list(directory_path.glob('*.csv')) + list(directory_path.glob('*.xlsx'))
    logger.info(f"Found {len(filepaths)} files to process")

    sheets.clear(
        spreadsheet_id=sheet_url,
        range_name=sheet_name,
    )

    for filepath in filepaths:
        # only process 20220422-SECERDPallet_3080Warehouse.xlsx:
        # if "20220422-SECERDPallet_3080Warehouse.xlsx" not in filepath.name:
        #     continue
        # if "20241014_ERDPallet_3080Warehouse.xlsx" not in filepath.name:
        #     continue
        # if "Pallet  21-02-15.xlsx" not in filepath.name:
        #     continue
        # if "20231123-ERDPallet_3080Warehouse.xlsx" not in filepath.name:
        #     continue
        # if "ERDPALLET3080SN_20240923.xlsx" not in filepath.name:
        #     continue
        # if "Pallet  21-04-06.xlsx" not in filepath.name:
        #     continue
        # if "20231123-ERDPallet_3080Warehouse.xlsx" not in filepath.name:
        #     continue
        # if "20240424-ERDPallet_3080Warehouse.xlsx" not in filepath.name:
        #     continue
        # if "Pallet  21-05-18.xlsx" not in filepath.name:
        #     continue
        # if "20241023_ERDPallet_3080Warehouse.xlsx" not in filepath.name:
        #     continue
        # if "20241011_ERDPallet_3080Warehouse.xlsx" not in filepath.name:
        #     continue

        # ignore opened xlsx files:
        if "~$" in filepath.name:
            continue

        try:
            processed_df = process_file(filepath=filepath, model=model)
            if processed_df is None or processed_df.empty:
                continue

            logger.info(f"Uploading {len(processed_df)} rows to Google Sheets")

            sheets.append(
                spreadsheet_id=sheet_url,
                range_name=sheet_name,
                values=sheets.from_frame(processed_df),
            )

            logger.success(f"Successfully uploaded data from {filepath.name}")

            time.sleep(1)  # Sleep for 1 second to avoid rate limiting

        except Exception as e:
            logger.error(f"Error processing {filepath}: {str(e)}", exception=e)


def main() -> None:
    """Entry point for the script."""
    logger.info("Starting ERD Pallet data processing")

    directory_path = Path("data/ERDPallets3080Updated_ Warehouse")
    sheets = Sheets()
    sheet_url = "https://docs.google.com/spreadsheets/d/1VzHRByH_QxtQatz1ISwEkpILHn3HK1GH-ooc1OlROMM/edit?gid=0#gid=0"
    sheet_name = "ERD Pallets"

    model: Model = "gpt-4o"

    process_directory(
        directory_path=directory_path,
        model=model,
        sheet_url=sheet_url,
        sheet_name=sheet_name,
        sheets=sheets,
    )

    logger.info("Completed ERD Pallet data processing")


if __name__ == "__main__":
    main()
