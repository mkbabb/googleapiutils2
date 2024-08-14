import json
import multiprocessing as mp
import re
from functools import lru_cache
from multiprocessing import Queue
from multiprocessing.managers import SyncManager
from multiprocessing.pool import Pool
from queue import Empty
from typing import *

import numpy as np
import pandas as pd
from litellm import ModelResponse, completion
from loguru import logger

from googleapiutils2 import Sheets, SheetSlice, get_oauth2_creds
from googleapiutils2.sheets.misc import SheetSliceT

USAC_FORM_471_URL = "https://legacy.fundsforlearning.com/471/"


Model = Literal[
    "claude-3-5-sonnet-20240620",
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-4o-mini",
    "groq/llama-3.1-8b-instant",
    "groq/llama-3.1-70b-versatile",
    "groq/llama-3.1-405b-reasoning",
]


T = TypeVar("T")


class QueuePool(Generic[T], Pool):
    def __init__(
        self: "QueuePool[T]",
        *args,
        sentinel: Any | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self._qp_queue: Queue[T] | None = None
        self._qp_sentinel = sentinel
        self._qp_num_complete: int = 0
        self._qp_manager: SyncManager | None = None

    @property
    def queue(self):
        return self._qp_queue

    def __enter__(self) -> "QueuePool[T]":
        self._qp_manager = mp.Manager()
        self._qp_queue = self._qp_manager.Queue()  # type: ignore
        self._qp_num_complete = 0

        return super().__enter__()

    def __exit__(self, *args, **kwargs):
        self._qp_manager.__exit__(*args, **kwargs)  # type: ignore

        return super().__exit__(*args, **kwargs)

    def results(self) -> Iterator[T]:
        while self._qp_num_complete < self._processes:  # type: ignore
            try:
                if (item := self._qp_queue.get()) is self._qp_sentinel:  # type: ignore
                    self._qp_num_complete += 1
                else:
                    yield item
            except Empty:
                pass


def normalize_str(s: str) -> str:
    """Normalize a string by removing extra whitespace and converting to lowercase."""
    return re.sub(r"\s+", " ", s).strip().lower()


def row_has_data(row_slice: SheetSliceT, spreadsheet_id: str, sheets: Sheets) -> bool:
    """Check if a row has data in a Google Sheet."""

    try:
        return bool(sheets.values(spreadsheet_id=spreadsheet_id, range_name=row_slice))
    except Exception as e:
        return False


def get_frns(
    svf_url: str,
    frn_status_tagging_url: str,
    sheets: Sheets,
) -> pd.DataFrame:
    svf_leas_df = sheets.to_frame(
        sheets.values(spreadsheet_id=svf_url, range_name="LEA LIST"),
        dtypes={"District Entity Number": str},
    )
    # Remove the last duplicate "District Entity Number" column
    svf_leas_df = svf_leas_df.loc[:, ~svf_leas_df.columns.duplicated()]

    # Filter out rows with empty District Entity Numbers
    svf_leas_df = svf_leas_df[
        ~(
            svf_leas_df["District Entity Number"].isna()
            | svf_leas_df["District Entity Number"]
            == ""
        )
    ]

    frn_status_df = sheets.to_frame(
        sheets.values(spreadsheet_id=frn_status_tagging_url, range_name="FRN Status"),
        dtypes={"Billed Entity Number": str},
    )

    # Inner join the FRN Status and SVF LEA List DataFrames on the Billed Entity Number and District Entity Number columns
    # But only take the District Entity Number, LEA Number, and LEA Name columns from the SVF LEA List DataFrame
    frn_status_df = frn_status_df.merge(
        svf_leas_df[
            [
                "District Entity Number",
                "LEA Number",
                "LEA Name",
            ]
        ],
        how="inner",
        left_on="Billed Entity Number",
        right_on="District Entity Number",
    )

    sheets.update(
        spreadsheet_id=frn_status_tagging_url,
        range_name="SVF FRNs",
        values=sheets.from_frame(frn_status_df),
    )

    return frn_status_df


def handle_response(response: ModelResponse) -> dict[str, str] | None:
    """Wrapper function to handle the response from the OpenAI API.

    If the result can be parsed as JSON, it returns the result as a JSON object.
    Else, it returns None.
    """
    if not len(response.choices):
        return None

    content = response.choices[0].message.content  # type: ignore

    if content is None:
        return None

    try:
        if len(data := json.loads(content)):
            return data
    except Exception as e:
        pass

    return None


@lru_cache
def call_model(
    content: str, system_msg: str, model: Model, **kwargs: Any
) -> dict[str, Any] | None:
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

    if (data := handle_response(response=response)) is not None:
        return data
    else:
        return None


def tag_frn(
    data: dict[str, Any],
    tags: str,
    prompt: str,
    model: Model,
) -> dict[str, Any] | None:
    content = json.dumps(data, indent=2)
    content = normalize_str(content)

    system_msg = prompt.format(tags=tags)

    output_data = call_model(
        content=content,
        system_msg=system_msg,
        model=model,
    )

    if output_data is None:
        return None

    tags = output_data.get("tags", [])  # type: ignore

    if not len(tags) or not isinstance(tags, list):
        return None

    return tags


def process_row(
    row: pd.Series,
    output_sheet_name: str,
    frn_tags_str: str,
    frn_prompt: str,
    models: list[Model],
):
    n = int(row.name) + 2  # type: ignore
    row_slice = SheetSlice[output_sheet_name, n, ...]

    frn_data = {
        "FRN Nickname": row["FRN Nickname"],
        "Funding Request Narrative": row["Funding Request Narrative"],
        "Service Type": row["Service Type"],
        "Categories of Service": row["Categories of Service"],
    }

    frn_url = f"{USAC_FORM_471_URL}{row['Application Number']}"

    output_data: dict = {
        "Funding Request Number": row["Funding Request Number"],
        **frn_data,
        "FRN URL": frn_url,
    }

    for model in models:
        try:
            tags = tag_frn(
                data=frn_data, tags=frn_tags_str, prompt=frn_prompt, model=model
            )
            if tags is None:
                logger.warning(
                    f"No tags found for FRN {row['Funding Request Number']} with model {model}"
                )
                continue

            logger.info(
                f"Tagged FRN {row['Funding Request Number']} with model {model}"
            )
            output_data[model] = json.dumps(tags)
        except Exception:
            logger.error(
                f"Error tagging FRN {row['Funding Request Number']} with model {model}"
            )
            pass

    return row_slice, output_data


def worker(chunk: pd.DataFrame, queue: Queue, **kwargs: Any) -> None:
    for _, row in chunk.iterrows():
        queue.put(
            process_row(
                row=row,
                **kwargs,
            )
        )


def main():
    creds = get_oauth2_creds()

    sheets = Sheets(creds=creds)

    svf_url = "https://docs.google.com/spreadsheets/d/1ddRDtnz8NBCxh4hzrFieuxkTP-7vnBw0Ox6btXx_r-Y/edit?gid=1473271958#gid=1473271958"

    frn_status_tagging_url = "https://docs.google.com/spreadsheets/d/1ixwyCEB2sTA9Hem-ZwGwH3rYTQg6Ey3dEssZU3yQKrE/edit?gid=0#gid=0"

    output_sheet_name = "tmp"

    models: list[Model] = [
        "gpt-4o",
        "gpt-4o-mini",
        # "claude-3-5-sonnet-20240620",
    ]

    # frn_status_df = get_frns(
    #     svf_url=svf_url,
    #     frn_status_tagging_url=frn_status_tagging_url,
    #     sheets=sheets,
    # )

    frn_status_df = sheets.to_frame(
        sheets.values(spreadsheet_id=frn_status_tagging_url, range_name="SVF FRNs")
    )

    frn_tags = sheets.to_frame(
        sheets.values(spreadsheet_id=frn_status_tagging_url, range_name="Tags")
    )
    frn_tags_str = ", ".join(map(lambda x: f'"{x}"', frn_tags["Tag Name"].tolist()))

    frn_prompt: str = sheets.value(
        spreadsheet_id=frn_status_tagging_url, range_name="Prompt!A2"
    )

    # Determine the number of processes to use
    num_cores: int = mp.cpu_count()
    num_processes: int = max(1, num_cores - 1)

    # Split the DataFrame into chunks
    chunks: list[pd.DataFrame] = np.array_split(frn_status_df, num_processes)  # type: ignore

    with QueuePool[tuple[SheetSliceT, dict]](
        processes=num_processes, context=mp.get_context("spawn")
    ) as qp:
        for chunk in chunks:
            qp.apply_async(
                worker,
                args=(chunk, qp.queue),
                kwds=dict(
                    output_sheet_name=output_sheet_name,
                    frn_tags_str=frn_tags_str,
                    frn_prompt=frn_prompt,
                    models=models,
                ),
            )

        for row_slice, output_data in qp.results():
            sheets.batch_update(
                spreadsheet_id=frn_status_tagging_url,
                data={
                    row_slice: [output_data],
                },
                ensure_shape=True,
            )


if __name__ == "__main__":
    main()
