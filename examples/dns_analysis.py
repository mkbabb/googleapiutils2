from __future__ import annotations

import json
import pathlib
import re
import subprocess
import tempfile
import tomllib  # type: ignore
from functools import cache
from typing import *
from datetime import timedelta

import ipinfo  # type: ignore
import jinja2
import openai
from jinja_markdown2 import MarkdownExtension  # type: ignore
from loguru import logger
from openai.types.chat import ChatCompletion

from googleapiutils2 import (
    Drive,
    GoogleMimeTypes,
    Sheets,
    SheetSlice,
    get_oauth2_creds,
    cache_with_stale_interval,
)

jinja_env = jinja2.Environment(loader=jinja2.loaders.FileSystemLoader("."))
jinja_env.add_extension(MarkdownExtension)

TEMPLATE_PATH = pathlib.Path("./examples/dns-report-template.md")

DEFAULT_NS = "152.45.127.1"


def sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        k: json.dumps(v, default=str) if isinstance(v, (list, dict, tuple)) else v
        for k, v in row.items()
    }


def upload_html_to_google_doc(
    html: str,
    filename: str,
    parent_folder: str,
    drive: Drive,
):

    with tempfile.NamedTemporaryFile(mode="r+", suffix=".html") as f:
        f.write(html)
        f.seek(0)

        return drive.upload(
            filepath=f.name,
            name=filename,
            to_mime_type=GoogleMimeTypes.docs,
            from_mime_type=GoogleMimeTypes.html,
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


def handle_response(response: ChatCompletion) -> dict[str, Any] | str | None:
    if not len(response.choices):
        return None

    content = response.choices[0].message.content

    if content is None:
        return None

    content = strip_response(content)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return content


@cache_with_stale_interval(stale_interval=timedelta(days=1))
def analyze_dns_records(
    domain: str, records: dict[str, str], system_prompt: str, prompt: str
):
    records_str = json.dumps(records, indent=2)

    prompt = prompt.format(domain=domain, records_str=records_str)

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    parsed_response = handle_response(response=response)  # type: ignore

    if parsed_response is None:
        return "No response from OpenAI"

    return parsed_response


def run_command(command: str) -> str:
    """Executes a system command and returns its output"""
    try:
        result = subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return e.output.strip()


@cache
def find_ns(domain: str, default_ns: str = DEFAULT_NS):
    """Finds the nameserver for a given domain"""
    ns = run_command(f"dig +short NS {domain}")

    # trim the "." at the end of the nameserver
    nss = [ns.strip(".") for ns in ns.split("\n")]

    for ns in nss:
        digged = run_command(f"dig @{ns} {domain} +short")
        if len(digged):
            return ns

    return default_ns


def extract_ip_details_from_spf(record: str, ns: str = DEFAULT_NS):
    """Extracts IP addresses from SPF record, performs reverse DNS if necessary, and fetches IP details"""
    RE_IPS = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?:/\d{1,2})?\b")
    RE_HOSTNAMES = re.compile(r"include:(\S+)")

    ips = re.findall(RE_IPS, record)
    hostnames = re.findall(RE_HOSTNAMES, record)

    for ip in ips:
        hostnames.append(run_command(f"dig +short -x {ip} @{ns} +short"))

    # trim the "." at the end of the hostnames
    hostnames = [str(hostname).strip().strip(".").strip() for hostname in hostnames]

    return list(set(hostnames))


def get_dns_record(domain: str, record_type: str, ns: str = DEFAULT_NS):
    """Fetches DNS record of the specified type using dig"""
    result = run_command(f"dig @{ns} {record_type} {domain} +short")
    return result


def get_dkim_record(domain: str, ns: str = DEFAULT_NS):
    """Fetches DKIM record using dig"""
    SELECTORS = [
        "default",  # Generic default selector, could be used by various organizations
        "mail",  # Generic selector, commonly used across multiple organizations
        "email",  # Generic selector, commonly used across multiple organizations
        "dkim",  # Various (this is a generic selector name and could be used by multiple organizations)
        "google",  # Organization: Google
        "selector1",  # Organization: Microsoft
        "selector2",  # Organization: Microsoft
        "smtp",  # Generic selector, commonly used across multiple organizations
        "k1",  # Likely associated with organizations using third-party email services, but not a well-known standard.
        "m1",  # Placeholder for m1, as it wasn't explicitly mentioned
        "mimecast",  # Organization: Mimecast
        "tm1",  # Organization: Trend Micro
        "tm2",  # Organization: Trend Micro
        "k2",  # Likely associated with organizations using third-party email services, but not a well-known standard.
        "k3",  # Likely associated with organizations using third-party email services, but not a well-known standard.
        "mandrill",  # Organization: Mandrill (a transactional email API for Mailchimp users)
        "fd",  # Organization: FastDomain
        "fd2",  # Organization: FastDomain
        "s2",  # Organization: SparkPost
        "mxvault",  # Organization: MX Guarddog
        "amazon",  # Organization: Amazon SES (Simple Email Service)
        "api",  # Likely associated with various organizations using APIs for email services, not a specific standard.
        "s1",  # Organization: SparkPost
        "fdm",  # Organization: FastDomain
        "protonmail13",  # Organization: ProtonMail
        "zmail",  # Organization: Zoho Mail
    ]

    for selector in SELECTORS:
        if (
            dkim_record := get_dns_record(
                f"{selector}._domainkey.{domain}", "TXT", ns=ns
            )
        ) and "dkim" in dkim_record.lower():
            logger.info(f"Found DKIM record for {domain} with selector: {selector}")

            return dkim_record


def get_dns_info_for_domain(domain: str):
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

    ns = find_ns(domain)

    dns_info: dict[str, Any] = {
        "Has SPF": False,
        "Has DMARC": False,
        "Has DKIM": False,
        "Has MTA-STS": False,
        "Has BIMI": False,
        "Domain": domain,
        "NS": ns,
    }

    dns_records = {}

    for record_type in SUPPORTED_RECORD_TYPES:
        key = f"{record_type} Record" if record_type != "ANY" else "ANY Command Result"

        record = get_dns_record(domain=domain, record_type=record_type, ns=ns)
        if not record:
            continue

        logger.info(f"Found {record_type} record for {domain}: {record}")

        dns_records[key] = record

        record = record.strip().lower()

        if record_type == "TXT" and "v=spf" in record:
            spf_ips = extract_ip_details_from_spf(record)
            dns_info["SPF IPs"] = spf_ips
            dns_info["Has SPF"] = True

    if dmarc_record := get_dns_record(f"_dmarc.{domain}", "TXT"):
        dns_records["DMARC Record"] = dmarc_record
        dns_info["Has DMARC"] = True

        logger.info(f"Found DMARC record for {domain}: {dmarc_record}")

    if dkim_record := get_dkim_record(domain=domain, ns=ns):
        dns_records["DKIM Record"] = dkim_record
        dns_info["Has DKIM"] = True

        logger.info(f"Found DKIM record for {domain}: {dkim_record}")

    if mta_sts_record := get_dns_record(f"_mta-sts.{domain}", "TXT"):
        dns_records["MTA-STS Record"] = mta_sts_record
        dns_info["Has MTA-STS"] = True

        logger.info(f"Found MTA-STS record for {domain}: {mta_sts_record}")

    if bimi_record := get_dns_record(f"_bimi.{domain}", "TXT"):
        dns_records["BIMI Record"] = bimi_record
        dns_info["Has BIMI"] = True

        logger.info(f"Found BIMI record for {domain}: {bimi_record}")

    return dns_info, dns_records


def create_dns_report(
    template_path: pathlib.Path,
    **params: Any,
):
    YES_TAG = "<span style='color: #5cc75f;'>Yes</span>"
    NO_TAG = "<span style='color: #f72a2a;'>No</span>"

    # grab the template and render it with jinja2 and Markdown:
    template = jinja_env.get_template(str(template_path))

    return template.render(
        **params,
        YES_TAG=YES_TAG,
        NO_TAG=NO_TAG,
    )


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

openai.api_key = config["openai"]["api_key"]

reports_folder = (
    "https://drive.google.com/drive/u/0/folders/10m37Y2BQ-L9m2QIj3ay_6s4mdzBhF9go"
)

sheet_url = "https://docs.google.com/spreadsheets/d/1YMIIldmiclGQciVqkU_9PjqX4mS4bWQejvRIEUHjMlU/edit#gid=0"

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

    dns_info, dns_records = get_dns_info_for_domain(domain=domain)

    logger.info(f"Got DNS info for {domain}")

    dns_analysis = analyze_dns_records(
        domain=domain,
        records=dns_records,
        system_prompt=system_prompt,
        prompt=prompt,
    )

    logger.info(f"Analyzed DNS records with GPT")

    dns_report = create_dns_report(
        template_path=TEMPLATE_PATH,
        filename=filename,
        range_url=range_url,
        dns_records=dns_records,
        dns_info=dns_info,
        dns_analysis=dns_analysis,
    )

    logger.info(f"Created templated DNS report")

    dns_report_file = upload_html_to_google_doc(
        html=dns_report,
        filename=filename,
        parent_folder=reports_folder,
        drive=drive,
    )
    dns_report_file = drive.get(dns_report_file["id"])

    logger.info(f"Uploaded report at: {dns_report_file['webViewLink']}")

    row_dict = {
        **row,
        **dns_info,
        **dns_records,
        "Record Analysis URL": dns_report_file["webViewLink"],
    }

    row_dict = sanitize_row(row_dict)

    sheets.batch_update(
        spreadsheet_id=sheet_url,
        data={row_slice: [row_dict]},  # type: ignore
    )

    logger.info(f"Updated sheet at: {range_url}")
