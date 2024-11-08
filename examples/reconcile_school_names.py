from __future__ import annotations

import datetime
import difflib
import functools
import json
import sys
import time
from dataclasses import dataclass, field
from typing import *

import loguru
import pandas as pd
from litellm import ModelResponse, completion
from loguru import logger

from googleapiutils2 import (
    Drive,
    GoogleMimeTypes,
    Sheets,
    SheetSlice,
    cache_with_stale_interval,
    get_oauth2_creds,
)

# Conditional import for type checking
if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import File
    from googleapiclient._apis.sheets.v4.resources import Spreadsheet


def logger_format(record: loguru.Record) -> str:

    line = f"<cyan>{record['file'].name}</cyan>:<cyan>{record['line']}</cyan>"

    time = record["time"]
    level = record["level"]
    message = record["message"]

    return f"<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | {line} - <level>{message}</level>\n"


logger.remove()
logger.add(sys.stderr, format=logger_format)


Model = Literal[
    "claude-3-5-sonnet-20240620",
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-4o-mini",
    "groq/llama-3.1-8b-instant",
    "groq/llama-3.1-70b-versatile",
    "groq/llama-3.1-405b-reasoning",
]


@dataclass
class ReconcileInput:
    df: pd.DataFrame
    name: str | None

    name_col: str

    match_cols: list[str] | str | None = None

    models: Model | list[Model] | None = None


MatchFunction = Callable[[str, list[str]], list[str] | None]

ModelMatchFunction = Callable[[str, list[str], Model], list[str] | None]


def update_dict_suffixed(d: dict[str, Any], d2: dict[str, Any], suffix: str = "2"):
    for k, v in d2.items():
        suffix_key = f"{k}{suffix}"

        if d.get(k) is not None:
            d[suffix_key] = v
        else:
            d[k] = v

    return d


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
def handle_response(response: ModelResponse) -> dict[str, str] | None:
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
        pass

    return None


@cache_with_stale_interval(datetime.timedelta(days=1))
def find_name_match(
    input_name: str,
    match_list: list[str],
    model: Model,
    context: str | None = None,
) -> list[str] | None:
    match_list_str = "\n".join(match_list)

    context = context or ""

    # the system message is a prompt for the GPT model to follow.
    # take not of the structure hereof:
    system_msg = f"""Take the following input name and match list and fuzzy-find the input name within the input list.

    {context}
    
    Return the result as a JSON object with the following keys:
    - best_match: 
                The best match, a list of the best match or matches from the **input list verbatim**. 
                If no match is found, return an empty list.
"""

    # the user message is then the input
    content = f"""Input name: {input_name}
Match list:
{match_list_str}
"""

    response = completion(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {
                "role": "user",
                "content": content,
            },
        ],
        response_format={"type": "json_object"},
        drop_params=True,
    )

    data = handle_response(response=response)

    if data is None:
        return None

    best_match = data.get("best_match", [])  # type: ignore

    if not len(best_match) or not isinstance(best_match, list):
        return None

    return best_match


def reconcile_list(
    input_name: str,
    match_list_names: list[str],
    match_func: MatchFunction,
):
    match = match_func(input_name, match_list_names)

    if match is None:
        return None

    try:
        best_match = match[0]
        best_match_ix = match_list_names.index(best_match)

        return (best_match_ix, best_match)
    except Exception as e:
        logger.error(f"Error reconciling list: {e}")
        return None


def reconcile_lists(
    input_list: ReconcileInput,
    match_lists: list[ReconcileInput] | ReconcileInput,
    match_func: ModelMatchFunction,
) -> Generator[tuple[Hashable, dict], None, None]:
    if not isinstance(match_lists, list):
        match_lists = [match_lists]

    # Expand out the match lists to be per-model:
    match_lists_models: list[ReconcileInput] = []

    for match_list in match_lists:
        if match_list.models is None:
            raise ValueError("Model must be specified for each match list.")

        models = (
            match_list.models
            if isinstance(match_list.models, list)
            else [match_list.models]
        )

        for model in models:
            match_lists_models.append(
                ReconcileInput(
                    df=match_list.df,
                    name=match_list.name,
                    name_col=match_list.name_col,
                    match_cols=match_list.match_cols,
                    models=model,  # type: ignore
                )
            )

    match_lists_names_dfs = [
        match_list.df[match_list.name_col].drop_duplicates()
        for match_list in match_lists_models
    ]
    match_lists_names: list[tuple[list[int], list[str]]] = [
        (df.index.to_list(), df.to_list()) for df in match_lists_names_dfs
    ]

    for n, row in input_list.df.iterrows():
        name = row[input_list.name_col]

        logger.info(f"Processing: {name}")

        out_row = row.to_dict()

        for m, (match_list, (match_list_names_ixs, match_list_names)) in enumerate(
            zip(match_lists_models, match_lists_names)
        ):
            model = match_list.models  # type: ignore

            match = reconcile_list(
                input_name=name,  # type: ignore
                match_list_names=match_list_names,
                match_func=functools.partial(match_func, model=model),  # type: ignore
            )

            if match is None:
                logger.warning("No match found.")
                continue

            t_match_ix, match_name = match

            match_ix = match_list_names_ixs[t_match_ix]

            match_percent = difflib.SequenceMatcher(None, name, match[1]).ratio()  # type: ignore

            logger.success(f"Match found: {match_name}")

            name = match_list.name
            if name is None and model:
                name = model

            out_row[f"{match_list.name} Match"] = match_name
            out_row[f"{match_list.name} Match Index"] = match_ix
            out_row[f"{match_list.name} Match Percent"] = match_percent

            if match_list.match_cols is None:
                # Add the entire row
                # Colliding columns should be suffixed with the name of the dataframe
                suffix = f" {match_list.name}"

                out_row = update_dict_suffixed(
                    out_row,
                    match_list.df.iloc[match_ix].to_dict(),
                    suffix=suffix,
                )
            else:
                # Add only the specified columns
                for col in match_list.match_cols:
                    out_row[col] = match_list.df.iloc[match_ix][col]

        yield n, out_row


creds = get_oauth2_creds()

drive = Drive(creds=creds)
sheets = Sheets(creds=creds)


# file_id = "https://docs.google.com/spreadsheets/d/1gKHtEhsp-eb_TUZqUhdUSmsfNAKz1n-PZf2IUukISlo/edit#gid=1560048052"
# file_id = "https://docs.google.com/spreadsheets/d/1YX1kKWz6-AHKnRlf88fQtBFGh9pSQPg9dfUvKoXjKmI/edit?gid=2066933374#gid=2066933374"
file_id = "https://docs.google.com/spreadsheets/d/141XsLL8Je02MarFvIn4CEHwkBELgrCSVeJrdA-FpgSg/edit?gid=1116451230#gid=1116451230"


names_df = sheets.to_frame(
    sheets.values(
        spreadsheet_id=file_id,
        range_name="2024-471s",
    )
)

match_df = sheets.to_frame(
    sheets.values(
        spreadsheet_id=file_id,
        range_name="2408 Full Invoice $1,899,804.01",
    )
)

# remove rows that already have a PSU code from the pricing df; check blank and na:
if "LEA ID" in names_df.columns:
    names_df = names_df[names_df["LEA ID"].isna() | names_df["LEA ID"].eq("")]


match_func: ModelMatchFunction = functools.partial(
    find_name_match,
    context="""The input name and match list are school names, districts, etc.
Wherein SD = school district""",
)

match_cols = ["LEA ID", "Circuit"]

reconciled_data = reconcile_lists(
    input_list=ReconcileInput(
        df=names_df,
        name="Invoice",
        name_col="Recipient's Organization Name",
    ),
    match_lists=[
        ReconcileInput(
            df=match_df,
            name="SVF",
            name_col="LEA Name",
            models="gpt-4o",
            match_cols=match_cols,
        )
    ],
    match_func=match_func,
)

output_sheet_name = "2024-471s"

for n, data in reconciled_data:  # Start from row 2
    n = int(n) + 2  # type: ignore
    row_slice = SheetSlice[output_sheet_name, n, ...]

    # keep only LEA ID and Circuit columns from the dict
    data = {k: v for k, v in data.items() if k in match_cols}

    sheets.batch_update(
        spreadsheet_id=file_id,
        data={
            row_slice: [data],
        },  # type: ignore
        batch_size=10,
    )

sheets.batch_update_remaining_auto()
