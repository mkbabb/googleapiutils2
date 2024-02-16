from __future__ import annotations

import json
import pathlib
import pprint
import re
import subprocess
import tempfile
import tomllib
from typing import *

import ipinfo  # type: ignore
import openai
import pandas as pd
from loguru import logger
from openai.types.chat import ChatCompletion

from googleapiutils2 import Drive, GoogleMimeTypes, Sheets, SheetSlice, get_oauth2_creds

RE_IPS = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b")
RE_HOSTNAMES = re.compile(r"include:(\S+)")


def upload_markdown(
    content: str,
    filename: str,
    parent_folder: str,
    drive: Drive,
):
    with tempfile.NamedTemporaryFile(mode="r+", suffix=".txt") as f:
        f.write(content)
        f.seek(0)

        return drive.upload(
            filepath=f.name,
            name=filename,
            mime_type=GoogleMimeTypes.txt,
            parents=parent_folder,
        )


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


def handle_response(response: ChatCompletion):
    if not len(response.choices):
        return None

    content = response.choices[0].message.content

    if content is None:
        return None

    content = strip_response(content)

    return content


def analyze_dns_records_for_cybersecurity(domain: str, records: dict[str, str]):
    records_str = json.dumps(records, indent=2)

    system_prompt = "As an expert in Cybersecurity, analyze the given DNS records for cybersecurity insights."

    prompt = f"""Analyze the following DNS records of the domain '{domain}' for any cybersecurity concerns, such as potential vulnerabilities or misconfigurations.
    Be extemely pithy in your reply and provide actionable insights.

DNS Records:
{records_str}"""

    response = openai.chat.completions.create(
        # model="gpt-4-turbo-preview",
        model="gpt-3.5-turbo-1106",
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {"role": "user", "content": prompt},
        ],
        # response_format={"type": "json_object"},
    )

    return handle_response(response=response)


def run_command(command: str) -> str:
    """Executes a system command and returns its output"""
    try:
        result = subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return e.output.strip()


def _reverse_dns_lookup(hostname: str) -> list[str] | None:
    """Performs a reverse DNS lookup to get the numeric IP address for a given hostname"""
    ip = run_command(f"dig +short {hostname}")

    return ip.split("\n") if ip else None


def get_dns_info_for_domain(domain: str, ipinfo_api: ipinfo.Handler) -> Dict[str, Any]:
    SUPPORTED_RECORD_TYPES = [
        "A",
        "MX",
        "TXT",
        "AAAA",
        "SRV",
        "CNAME",
        "NS",
        "SOA",
        "PTR",
        "ANY",
    ]

    def _get_dns_record(domain: str, record_type: str) -> str:
        """Fetches DNS record of the specified type using dig"""
        result = run_command(f"dig {record_type} {domain} +short")
        return result

    def extract_ip_details_from_spf(record: str) -> Dict[str, Any]:
        """Extracts IP addresses from SPF record, performs reverse DNS if necessary, and fetches IP details"""
        ips = re.findall(RE_IPS, record)
        hostnames = re.findall(RE_HOSTNAMES, record)

        for hostname in hostnames:
            ip = _reverse_dns_lookup(hostname)
            if ip is not None:
                ips.extend(ip)

        cleaned_ips = set([str(ip).strip() for ip in ips])

        return {ip: ipinfo_api.getDetails(ip).all for ip in cleaned_ips}

    dns_info: dict[str, Any] = {}

    for record_type in SUPPORTED_RECORD_TYPES:
        key = f"{record_type} Record"
        record = _get_dns_record(domain=domain, record_type=record_type)

        if not record:
            continue

        dns_info[key] = record

        if record_type == "TXT":
            if "v=spf1" in record:  # SPF Handling
                spf_ips = extract_ip_details_from_spf(record)
                dns_info["SPF IPs"] = spf_ips
            if "v=DMARC1" in record:  # DMARC Handling
                dns_info["DMARC Policy"] = record

    if dmarc_record := _get_dns_record(f"_dmarc.{domain}", "TXT"):
        dns_info["DMARC Record"] = dmarc_record

    return dns_info


creds = get_oauth2_creds()
drive = Drive(creds=creds)
sheets = Sheets(creds=creds)

config_path = pathlib.Path("./auth/config.toml")
config = tomllib.loads(
    config_path.read_text(),
)

ipinfo_api = ipinfo.getHandler(
    access_token=config["ipinfo"]["access_token"],
)

reports_folder = (
    "https://drive.google.com/drive/u/0/folders/10m37Y2BQ-L9m2QIj3ay_6s4mdzBhF9go"
)

file_id = "https://docs.google.com/spreadsheets/d/1yYHbUQpGhm2GF16jgYoG_90cYmWfZjyNHwXQf1LI8fc/edit#gid=1778461197"

addresses_df = sheets.to_frame(
    sheets.values(
        spreadsheet_id=file_id,
        range_name="Cleaned Domain List",
    )
)

dig_df = sheets.to_frame(
    sheets.values(
        spreadsheet_id=file_id,
        range_name="DIG",
    )
)


for n, row in addresses_df.iterrows():
    lea_number = row["LEA Number"]
    domain = row["Domain"]

    logger.info(f"Processing domain: {domain}")

    dig_row = dig_df.iloc[n] if n in dig_df.index else None  # type: ignore

    # skip any rows that have an analysis document:
    if dig_row is not None and (
        "Record Analysis URL" in dig_row
        and not (
            pd.isna(dig_row["Record Analysis URL"])
            or dig_row["Record Analysis URL"] == ""
        )
    ):
        continue

    dns_info = get_dns_info_for_domain(domain=domain, ipinfo_api=ipinfo_api)

    analysis = analyze_dns_records_for_cybersecurity(domain, dns_info)

    dns_info_str = json.dumps(dns_info, indent=4).replace("\\n", "\n")

    analysis = f"""
## DNS Records:
{dns_info_str}

## Analysis:
{analysis}"""

    if "SPF IPs" in dns_info:
        del dns_info["SPF IPs"]

    analysis_file = upload_markdown(
        content=analysis,
        filename=f"{lea_number} - {domain} DNS Analysis.txt",
        parent_folder=reports_folder,
        drive=drive,
    )
    analysis_file = drive.get(analysis_file["id"])

    row_dict = {**row, **dns_info, "Record Analysis URL": analysis_file["webViewLink"]}

    row_ix = int(n) + 2  # type: ignore
    row_slice = SheetSlice["DIG", row_ix, ...]

    sheets.batch_update(
        spreadsheet_id=file_id,
        data={row_slice: [row_dict]},
    )
