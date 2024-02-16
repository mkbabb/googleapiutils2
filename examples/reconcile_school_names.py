from __future__ import annotations

import json
import os
from typing import *

import openai
import pandas as pd
from loguru import logger
from openai.types.chat import ChatCompletion

from googleapiutils2 import Drive, GoogleMimeTypes, Sheets, SheetSlice, get_oauth2_creds

# Conditional import for type checking
if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import File
    from googleapiclient._apis.sheets.v4.resources import Spreadsheet


# Function to clean and normalize responses from the OpenAI API.
# Occasionally, the API returns responses with extra quotes, newlines, or code blocks.
def strip_response(response: str) -> str:
    quote_chars = ['"', "'", "“", "”"]

    for char in quote_chars:
        response = response.strip().strip("\n")
        response = response.strip().strip(char)

    quote_chars = ["```", "json", "`"]

    for char in quote_chars:
        response = response.strip().strip("\n")
        response = response.strip().strip(char)

    return response


# Wrapper function to handle the response from the OpenAI API;
# it returns the response as a JSON object if it can be parsed, otherwise it returns None.
def handle_response(response: ChatCompletion) -> dict[str, str] | None:
    if not len(response.choices):
        return None

    content = response.choices[0].message.content

    if content is None:
        return None

    content = strip_response(content)

    try:
        if len(data := json.loads(content)):
            return data
    except Exception as e:
        pass

    return None


def find_school_name_match(school_name: str, school_names: list[str]):
    school_names_str = "\n".join(school_names)

    # the system message is a prompt for the GPT model to follow.
    # take not of the structure hereof:
    system_msg = f"""Take the following list of input school names and input school name and fuzzy-find it within the input list.
    
    Return the result as a JSON object with the following keys:
    - best_match: the best match, a list of the best match or matches from the **input list verbatim**. If no match is found, return an empty list.
"""

    # the user message is then the input
    content = f"""Input school name: {school_name}
Input school names:
{school_names_str}
"""

    response = openai.chat.completions.create(
        # gpt-3.5-turbo-1106 is the variant of 3.5 that can output JSON objects
        # gpt-4-turbo is the variant of 4 that you'd want to use other than 3.5
        # model="gpt-3.5-turbo-1106",
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": system_msg},
            {
                "role": "user",
                "content": content,
            },
        ],
        # some models are compatible with this, though most aren't
        # not necessary, but it makes structured output *much* more reliable
        response_format={"type": "json_object"},
    )

    return handle_response(response=response)


def reconcile_school_name(
    school_name: str,
    school_names_to_match_against: list[str],
):
    match = find_school_name_match(
        school_name=school_name, school_names=school_names_to_match_against
    )

    if match is None:
        return None

    best_match = match["best_match"]

    if not len(best_match) or not isinstance(best_match, list):
        return None

    best_match = best_match[0]

    if best_match not in school_names_to_match_against:
        return None

    best_match_index = school_names_to_match_against.index(best_match)

    return (best_match_index, best_match)


def reoncile_school_names(
    sheet_name: str,
    input_names: pd.DataFrame,
    input_name_col: str,
    names_to_match_against: pd.DataFrame | list[pd.DataFrame],
    name_cols: str | list[str],
    match_cols: str | list[str],
):
    if not isinstance(names_to_match_against, list):
        names_to_match_against = [names_to_match_against]

    if isinstance(name_cols, str):
        name_cols = [name_cols] * len(names_to_match_against)

    if isinstance(match_cols, str):
        match_cols = [match_cols] * len(names_to_match_against)

    for n, row in input_names.iterrows():
        name = row[input_name_col]

        logger.info(f"Processing: {name}")

        row_ix = int(n) + 2  # type: ignore

        row_slice = SheetSlice[sheet_name, row_ix, ...]

        out_row = {**row}

        for names_df, name_col, match_col in zip(
            names_to_match_against, name_cols, match_cols
        ):
            match = reconcile_school_name(
                school_name=name,
                school_names_to_match_against=names_df[name_col].tolist(),
            )

            if match is not None:
                match_index, match_name = match
                out_row[match_col] = names_df.iloc[match_index][match_col]

        data = {
            row_slice: [out_row],
        }

        sheets.batch_update(
            spreadsheet_id=file_id,
            data=data,  # type: ignore
        )


openai.api_key = os.environ["OPENAI_API_KEY"]


creds = get_oauth2_creds()

drive = Drive(creds=creds)
sheets = Sheets(creds=creds)


file_id = "https://docs.google.com/spreadsheets/d/1gKHtEhsp-eb_TUZqUhdUSmsfNAKz1n-PZf2IUukISlo/edit#gid=1560048052"


bw_df = sheets.to_frame(
    sheets.values(
        spreadsheet_id=file_id,
        range_name="BW",
    )
)

pricing_df = sheets.to_frame(
    sheets.values(
        spreadsheet_id=file_id,
        range_name="Pricing",
    )
)

# remove rows that already have a PSU code from the pricing df;check blank and na:

pricing_df = pricing_df[pricing_df["PSU Code"].isna() | pricing_df["PSU Code"].eq("")]


reoncile_school_names(
    sheet_name="Pricing",
    input_names=pricing_df,
    input_name_col="Customer",
    names_to_match_against=[bw_df],
    name_cols=["PSU"],
    match_cols=["PSU Code"],
)
