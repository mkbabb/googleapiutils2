from __future__ import annotations

import json
import re
import subprocess
import tempfile
from functools import cache
from typing import Any

from loguru import logger
from openai.types.chat import ChatCompletion

from googleapiutils2 import Drive, GoogleMimeTypes


def sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize a row dictionary for spreadsheet operations by converting complex types to JSON strings.

    Args:
        row: Dictionary containing row data

    Returns:
        Sanitized row dictionary
    """
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
    """
    Upload HTML content to Google Docs.

    Args:
        html: HTML content to upload
        filename: Name for the document
        parent_folder: Google Drive folder ID or URL
        drive: Google Drive client instance

    Returns:
        Uploaded file metadata or None on failure
    """
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
    """
    Strip unnecessary characters from an OpenAI response.

    Args:
        response: Raw response string

    Returns:
        Cleaned response string
    """
    quote_chars = ['"', "'", """, """]

    for char in quote_chars:
        response = response.strip().strip("\n")
        response = response.strip().strip(char)

    quote_chars = ["```", "json", "`"]

    for char in quote_chars:
        response = response.strip().strip("\n")
        response = response.strip().strip(char)

    return response


def handle_response(response: ChatCompletion) -> dict[str, Any] | str | None:
    """
    Handle and parse OpenAI API response.

    Args:
        response: OpenAI API response object

    Returns:
        Parsed response as dict, string or None
    """
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


def run_command(command: str) -> str:
    """
    Execute a system command and return its output.

    Args:
        command: Command to execute

    Returns:
        Command output as string
    """
    try:
        result = subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return e.output.strip()


@cache
def find_ns(domain: str, default_ns: str = "152.45.127.1"):
    """
    Find the nameserver for a given domain.

    Args:
        domain: Domain to find nameserver for
        default_ns: Default nameserver to use if none found

    Returns:
        Nameserver address
    """
    ns = run_command(f"dig +short NS {domain}")

    # Trim the "." at the end of the nameserver
    nss = [ns.strip(".") for ns in ns.split("\n")]

    for ns in nss:
        digged = run_command(f"dig @{ns} {domain} +short")
        if len(digged):
            return ns

    return default_ns


def extract_ip_details_from_spf(record: str, ns: str = "152.45.127.1"):
    """
    Extract IP addresses from SPF record and perform reverse DNS lookups.

    Args:
        record: SPF record string
        ns: Nameserver to use for DNS lookups

    Returns:
        List of unique hostnames
    """
    RE_IPS = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?:/\d{1,2})?\b")
    RE_HOSTNAMES = re.compile(r"include:(\S+)")

    ips = re.findall(RE_IPS, record)
    hostnames = re.findall(RE_HOSTNAMES, record)

    for ip in ips:
        hostnames.append(run_command(f"dig +short -x {ip} @{ns} +short"))

    # Trim the "." at the end of the hostnames
    hostnames = [str(hostname).strip().strip(".").strip() for hostname in hostnames]

    return list(set(hostnames))


def get_dns_record(domain: str, record_type: str, ns: str = "152.45.127.1"):
    """
    Fetch DNS record of the specified type using dig.

    Args:
        domain: Domain to query
        record_type: DNS record type (A, MX, TXT, etc.)
        ns: Nameserver to use

    Returns:
        DNS record string
    """
    result = run_command(f"dig @{ns} {record_type} {domain} +short")
    return result


def get_dkim_record(domain: str, ns: str = "152.45.127.1"):
    """
    Fetch DKIM record by trying various selector prefixes.

    Args:
        domain: Domain to query
        ns: Nameserver to use

    Returns:
        DKIM record if found, otherwise None
    """
    SELECTORS = [
        "default",
        "mail",
        "email",
        "dkim",
        "google",
        "selector1",
        "selector2",
        "smtp",
        "k1",
        "m1",
        "mimecast",
        "tm1",
        "tm2",
        "k2",
        "k3",
        "mandrill",
        "fd",
        "fd2",
        "s2",
        "mxvault",
        "amazon",
        "api",
        "s1",
        "fdm",
        "protonmail13",
        "zmail",
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
    """
    Get DNS information for a specified domain.

    Args:
        domain: Domain name to analyze

    Returns:
        Tuple of (dns_info, dns_records)
    """
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
            spf_ips = extract_ip_details_from_spf(record, ns=ns)
            dns_info["SPF IPs"] = spf_ips
            dns_info["Has SPF"] = True

    if dmarc_record := get_dns_record(f"_dmarc.{domain}", "TXT", ns=ns):
        dns_records["DMARC Record"] = dmarc_record
        dns_info["Has DMARC"] = True
        logger.info(f"Found DMARC record for {domain}: {dmarc_record}")

    if dkim_record := get_dkim_record(domain=domain, ns=ns):
        dns_records["DKIM Record"] = dkim_record
        dns_info["Has DKIM"] = True
        logger.info(f"Found DKIM record for {domain}: {dkim_record}")

    if mta_sts_record := get_dns_record(f"_mta-sts.{domain}", "TXT", ns=ns):
        dns_records["MTA-STS Record"] = mta_sts_record
        dns_info["Has MTA-STS"] = True
        logger.info(f"Found MTA-STS record for {domain}: {mta_sts_record}")

    if bimi_record := get_dns_record(f"_bimi.{domain}", "TXT", ns=ns):
        dns_records["BIMI Record"] = bimi_record
        dns_info["Has BIMI"] = True
        logger.info(f"Found BIMI record for {domain}: {bimi_record}")

    return dns_info, dns_records




