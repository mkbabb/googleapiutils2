from __future__ import annotations

import atexit
import json
import pathlib
import time
from datetime import timedelta
from functools import cache
from typing import Any

import ipinfo  # type: ignore
import jinja2
import openai
import tomllib
from jinja_markdown2 import MarkdownExtension  # type: ignore
from loguru import logger

from examples.dns_analysis.src.utils import (
    get_dns_info_for_domain,
    sanitize_row,
    upload_html_to_google_doc,
)
from googleapiutils2 import (
    Drive,
    Sheets,
    SheetSlice,
    get_oauth2_creds,
)
from googleapiutils2.utils.decorators import cache_with_stale_interval

# Initialize Jinja environment
jinja_env = jinja2.Environment(loader=jinja2.loaders.FileSystemLoader("."))
jinja_env.add_extension(MarkdownExtension)

# Constants
DEFAULT_NS = "152.45.127.1"

TEMPLATE_PATH = pathlib.Path("examples/dns_analysis/template.md")

DOCS_DIR = pathlib.Path("examples/dns_analysis/docs")


def create_dns_report(
    template_path: pathlib.Path,
    **params: Any,
):
    """
    Create a DNS report from a template.

    Args:
        template_path: Path to the template file
        **params: Parameters to pass to the template

    Returns:
        Rendered HTML report
    """
    YES_TAG = "<span style='color: #5cc75f;'>Yes</span>"
    NO_TAG = "<span style='color: #f72a2a;'>No</span>"

    template = jinja_env.get_template(str(template_path))

    return template.render(
        **params,
        YES_TAG=YES_TAG,
        NO_TAG=NO_TAG,
    )


@cache_with_stale_interval(stale_interval=timedelta(days=1))
def process_document_files(
    client: openai.Client, docs_dir: pathlib.Path = DOCS_DIR
) -> str | None:
    """
    Process document files in a directory and upload them to OpenAI.

    Args:
        docs_dir: Directory containing documents to process

    Returns:
        List of uploaded file IDs
    """
    if not docs_dir.exists() or not docs_dir.is_dir():
        logger.warning(
            f"Documents directory {docs_dir} does not exist or is not a directory"
        )
        return None

    vector_store = client.beta.vector_stores.create(
        name="dns-analyzer",
    )

    file_paths: list[pathlib.Path] = []

    for file_path in docs_dir.iterdir():
        if not file_path.is_file():
            continue

        file_type = file_path.suffix.lower()

        # Only process supported file types
        if file_type in ['.pdf', '.doc', '.docx', '.txt']:
            file_paths.append(file_path)

    file_streams = [
        open(file_path, "rb") for file_path in file_paths if file_path.is_file()
    ]

    client.beta.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id,
        files=file_streams,
    )

    logger.info(f"Uploaded {len(file_streams)} files to vector store {vector_store.id}")

    return vector_store.id


def cleanup_uploaded_files(
    assistant_id: str, client: openai.Client, vector_store_id: str | None = None
) -> None:
    """
    Clean up uploaded files after use.

    Args:
        assistant_id: ID of the assistant to clean up
        vector_store_id: ID of the vector store to clean up
    """
    if vector_store_id is not None:
        logger.info(f"Deleting vector store {vector_store_id}")
        client.beta.vector_stores.delete(vector_store_id=vector_store_id)

    logger.info(f"Deleting assistant {assistant_id}")
    client.beta.assistants.delete(assistant_id=assistant_id)


@cache_with_stale_interval(stale_interval=timedelta(days=1))
def create_dns_analyzer_assistant(
    client: openai.Client, system_prompt: str, vector_store_id: str | None = None
):
    """
    Create an assistant for DNS analysis.

    Args:
        client: OpenAI client
        system_prompt: Instructions for the assistant
        file_ids: Optional list of file IDs to attach to the assistant

    Returns:
        Assistant ID
    """
    if vector_store_id is None:
        logger.warning("No vector store ID provided, assistant will not have context")

        assistant = client.beta.assistants.create(
            name="DNS Analyzer",
            instructions=system_prompt,
            model="o3-mini",
            response_format={"type": "json_object"},
            reasoning_effort="high",
        )
    else:
        assistant = client.beta.assistants.create(
            name="DNS Analyzer",
            instructions=system_prompt,
            tools=[
                {"type": "file_search"},
            ],
            tool_resources={
                "file_search": {
                    "vector_store_ids": [vector_store_id],
                }
            },
            model="o3-mini",
            response_format={"type": "json_object"},
            reasoning_effort="high",
        )

    logger.debug(f"Created assistant {assistant.id}")

    return assistant.id


def run_assistant_analysis(
    client: openai.Client, assistant_id: str, thread_id: str, prompt: str
):
    """
    Run the assistant on a thread and get the response.

    Args:
        client: OpenAI client
        assistant_id: ID of the assistant to run
        thread_id: ID of the thread to run on
        prompt: Prompt to add to the thread

    Returns:
        Assistant's response
    """
    # Add the user message to the thread
    client.beta.threads.messages.create(
        thread_id=thread_id, role="user", content=prompt
    )

    # Run the assistant
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        response_format={"type": "json_object"},
    )

    # Wait for the run to complete
    timeout = 10 * 60  # 10 minute timeout

    start_time = time.time()

    while True:
        if time.time() - start_time > timeout:
            logger.warning("Timeout waiting for assistant response")

            return "Timeout waiting for assistant response"

        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

        if run.status == "completed":
            break

        if run.status in ["failed", "expired", "cancelled"]:
            logger.error(f"Run failed with status: {run.status}")
            return f"Run failed with status: {run.status}"

        # Wait before checking again
        time.sleep(2)

    # Get the assistant's response
    messages = client.beta.threads.messages.list(
        thread_id=thread_id, order="desc", limit=1
    )

    # Extract and parse the response
    if not messages.data:
        return "No response from assistant"

    message = messages.data[0]
    if message.role != "assistant":
        return "No assistant response found"

    if not message.content:
        return "Empty response from assistant"

    content_block = message.content[0]
    if content_block.type == "text":
        text_content = content_block.text.value
        try:
            return json.loads(text_content)
        except json.JSONDecodeError:
            return text_content

    return "Unexpected response format from assistant"


# @cache_with_stale_interval(stale_interval=timedelta(days=1))
def analyze_dns_records(
    domain: str,
    records: dict[str, str],
    prompt: str,
    assistant_id: str,
    client: openai.Client,
):
    """
    Analyze DNS records using OpenAI's Assistants API.

    Args:
        domain: Domain name being analyzed
        records: Dictionary of DNS records
        system_prompt: System prompt for the OpenAI assistant
        prompt: User prompt template for the OpenAI assistant
        file_ids: Optional list of OpenAI file IDs to include as context

    Returns:
        Parsed response from OpenAI Assistant
    """
    records_str = json.dumps(records, indent=2)

    formatted_prompt = prompt.format(domain=domain, records_str=records_str)

    thread_id = None

    try:
        # Create thread
        thread = client.beta.threads.create()
        thread_id = thread.id

        logger.debug(f"Created thread {thread_id}")

        # Run analysis
        result = run_assistant_analysis(
            client=client,
            assistant_id=assistant_id,
            thread_id=thread_id,
            prompt=formatted_prompt,
        )

        return result

    except Exception as e:
        logger.error(f"Error using Assistants API: {e}")
        return f"Error: {str(e)}"
    finally:
        # Clean up resources
        try:
            if thread_id:
                client.beta.threads.delete(thread_id=thread_id)

                logger.debug(f"Deleted thread {thread_id}")
        except Exception as e:
            logger.warning(f"Failed to clean up resources: {e}")


def main():
    """Main function to run the DNS analysis process."""

    # Load configuration
    config_path = pathlib.Path("./auth/config.toml")
    config = tomllib.loads(config_path.read_text())

    # Initialize API clients
    creds = get_oauth2_creds()
    drive = Drive(creds=creds)
    sheets = Sheets(creds=creds)

    ipinfo_api = ipinfo.getHandler(
        access_token=config["ipinfo"]["access_token"],
    )

    openai.api_key = config["openai"]["api_key"]

    # Constants
    reports_folder = (
        "https://drive.google.com/drive/u/0/folders/10m37Y2BQ-L9m2QIj3ay_6s4mdzBhF9go"
    )
    sheet_url = "https://docs.google.com/spreadsheets/d/1YMIIldmiclGQciVqkU_9PjqX4mS4bWQejvRIEUHjMlU/edit#gid=0"

    # Load domains and prompt data
    addresses_df = sheets.to_frame(
        sheets.values(
            spreadsheet_id=sheet_url,
            range_name="Cleaned Domain List",
        )
    )
    logger.info(f"Got {len(addresses_df)} domains")

    dig_df = sheets.to_frame(
        sheets.values(
            spreadsheet_id=sheet_url,
            range_name="DIG",
        )
    )

    prompt_df = sheets.to_frame(
        sheets.values(
            spreadsheet_id=sheet_url,
            range_name="Prompt",
        )
    )
    system_prompt = prompt_df.iloc[0]["system_prompt"]
    prompt = prompt_df.iloc[0]["prompt"]

    openai_client = openai.Client()

    vector_store_id = process_document_files(client=openai_client, docs_dir=DOCS_DIR)

    assistant_id = create_dns_analyzer_assistant(
        client=openai_client,
        system_prompt=system_prompt,
        vector_store_id=vector_store_id,
    )

    cleanup_fn = lambda: cleanup_uploaded_files(
        assistant_id=assistant_id,
        client=openai_client,
        vector_store_id=vector_store_id,
    )  # type: ignore

    atexit.register(cleanup_fn)

    # Process each domain
    for n, row in addresses_df.iterrows():
        row_ix = int(n) + 2  # type: ignore

        row_slice = SheetSlice["DIG", row_ix, ...]

        range_url = sheets.create_range_url(
            file_id=sheet_url,
            sheet_slice=row_slice,
        )

        lea_number = row["LEA Number"]
        domain = row["Domain"]

        filename = f"{lea_number} - {domain} DNS Analysis"

        logger.info(f"Processing {filename}...")

        dig_row = dig_df.iloc[n] if n in dig_df.index else None  # type: ignore

        # Get DNS information
        dns_info, dns_records = get_dns_info_for_domain(domain=domain)
        logger.info(f"Got DNS info for {domain}")

        try:
            # Analyze DNS records
            dns_analysis = analyze_dns_records(
                domain=domain,
                records=dns_records,
                prompt=prompt,
                assistant_id=assistant_id,
                client=openai_client,
            )
        except Exception as e:
            logger.error(f"Error analyzing DNS records: {e}")

            dns_analysis = {}

        logger.info("Analyzed DNS records with GPT")

        # Create report
        dns_report = create_dns_report(
            template_path=TEMPLATE_PATH,
            filename=filename,
            range_url=range_url,
            dns_records=dns_records,
            dns_info=dns_info,
            dns_analysis=dns_analysis,
        )
        logger.info("Created templated DNS report")

        # Upload report
        dns_report_file = upload_html_to_google_doc(
            html=dns_report,
            filename=filename,
            parent_folder=reports_folder,
            drive=drive,
        )

        if dns_report_file is None:
            logger.error(f"Failed to upload report for {filename}")
            continue

        dns_report_file = drive.get(dns_report_file["id"])
        logger.info(f"Uploaded report at: {dns_report_file['webViewLink']}")

        # Update spreadsheet
        row_dict = {
            **row,
            **dns_info,
            **dns_records,
            "Record Analysis URL": dns_report_file["webViewLink"],
        }
        row_dict = sanitize_row(row_dict)

        sheets.batch_update(
            spreadsheet_id=sheet_url,
            data={row_slice: [row_dict]},
        )
        logger.info(f"Updated sheet at: {range_url}")

    # Format header
    sheets.format_header(
        spreadsheet_id=sheet_url,
        sheet_name="DIG",
    )


if __name__ == "__main__":
    main()
