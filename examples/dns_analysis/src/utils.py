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


def extract_ip_details_from_spf(
    record: str, domain: str, ns: str = "152.45.127.1", max_recursion: int = 3
):
    """
    Extract and categorize components from SPF record with comprehensive mechanism support.

    Args:
        record: SPF record string
        domain: Domain the SPF record belongs to (needed for resolving relative mechanisms)
        ns: Nameserver to use for DNS lookups
        max_recursion: Maximum recursion depth for processing included SPF records

    Returns:
        Dictionary of categorized SPF components with lookups
    """
    # Remove quotes if present
    record = record.strip('"\'')

    # Clean up record for parsing
    record = " " + record + " "  # Add spaces for boundary matching

    # Regex patterns for different SPF mechanisms with modifiers
    RE_IPV4 = re.compile(
        r"(?<!\S)([-~+?]?)ip4:(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?)(?!\S)"
    )
    RE_IPV6 = re.compile(r"(?<!\S)([-~+?]?)ip6:([0-9a-fA-F:]+(?:/\d{1,3})?)(?!\S)")
    RE_INCLUDE = re.compile(r"(?<!\S)([-~+?]?)include:(\S+)(?!\S)")
    RE_A_DOMAIN = re.compile(r"(?<!\S)([-~+?]?)a:(\S+?)(?:/\d{1,2})?(?!\S)")
    RE_A_SIMPLE = re.compile(r"(?<!\S)([-~+?]?)a(?!/\d)(?!\S|:)")  # Just 'a' mechanism
    RE_MX_DOMAIN = re.compile(r"(?<!\S)([-~+?]?)mx:(\S+?)(?:/\d{1,2})?(?!\S)")
    RE_MX_SIMPLE = re.compile(
        r"(?<!\S)([-~+?]?)mx(?!/\d)(?!\S|:)"
    )  # Just 'mx' mechanism
    RE_PTR = re.compile(r"(?<!\S)([-~+?]?)ptr(?::(\S+))?(?!\S)")
    RE_EXISTS = re.compile(r"(?<!\S)([-~+?]?)exists:(\S+)(?!\S)")
    RE_REDIRECT = re.compile(r"(?<!\S)redirect=(\S+)(?!\S)")
    RE_EXP = re.compile(r"(?<!\S)exp=(\S+)(?!\S)")
    RE_ALL = re.compile(r"(?<!\S)([-~+?]?)all(?!\S)")

    # Initialize results dictionary
    results: dict = {
        "mechanisms": {
            "ip4": [],
            "ip6": [],
            "include": [],
            "a": [],
            "mx": [],
            "ptr": [],
            "exists": [],
            "all": None,
        },
        "modifiers": {"redirect": None, "exp": None},
        "hostnames": [],
        "ips": [],
        "raw": record.strip(),
    }

    # Find the 'all' mechanism and its modifier
    all_match = re.search(RE_ALL, record)
    if all_match:
        modifier = all_match.group(1) or "+"  # Default to '+' if no modifier
        results["mechanisms"]["all"] = f"{modifier}all"

    # Extract IPv4 addresses with modifiers
    for modifier, ip in re.findall(RE_IPV4, record):
        modifier = modifier or "+"  # Default to '+' if no modifier
        results["mechanisms"]["ip4"].append((modifier, ip))

    # Extract IPv6 addresses with modifiers
    for modifier, ip in re.findall(RE_IPV6, record):
        modifier = modifier or "+"  # Default to '+' if no modifier
        results["mechanisms"]["ip6"].append((modifier, ip))

    # Extract include directives with modifiers
    for modifier, included_domain in re.findall(RE_INCLUDE, record):
        modifier = modifier or "+"  # Default to '+' if no modifier
        results["mechanisms"]["include"].append((modifier, included_domain))

    # Extract 'a' mechanisms with domains
    for modifier, a_domain in re.findall(RE_A_DOMAIN, record):
        modifier = modifier or "+"  # Default to '+' if no modifier
        results["mechanisms"]["a"].append((modifier, a_domain))

    # Handle simple 'a' mechanism (refers to current domain)
    a_simple_matches = re.findall(RE_A_SIMPLE, record)
    if a_simple_matches and domain:
        for modifier in a_simple_matches:
            modifier = modifier or "+"  # Default to '+' if no modifier
            results["mechanisms"]["a"].append((modifier, domain))

    # Extract 'mx' mechanisms with domains
    for modifier, mx_domain in re.findall(RE_MX_DOMAIN, record):
        modifier = modifier or "+"  # Default to '+' if no modifier
        results["mechanisms"]["mx"].append((modifier, mx_domain))

    # Handle simple 'mx' mechanism (refers to current domain)
    mx_simple_matches = re.findall(RE_MX_SIMPLE, record)
    if mx_simple_matches and domain:
        for modifier in mx_simple_matches:
            modifier = modifier or "+"  # Default to '+' if no modifier
            results["mechanisms"]["mx"].append((modifier, domain))

    # Extract 'ptr' mechanisms
    for modifier, ptr_domain in re.findall(RE_PTR, record):
        modifier = modifier or "+"  # Default to '+' if no modifier
        ptr_domain = ptr_domain or (domain if domain else "SENDER")
        results["mechanisms"]["ptr"].append((modifier, ptr_domain))

    # Extract 'exists' mechanisms
    for modifier, exists_domain in re.findall(RE_EXISTS, record):
        modifier = modifier or "+"  # Default to '+' if no modifier
        results["mechanisms"]["exists"].append((modifier, exists_domain))

    # Extract 'redirect' modifier (only one allowed)
    redirect_matches = re.findall(RE_REDIRECT, record)
    if redirect_matches:
        results["modifiers"]["redirect"] = redirect_matches[0]

    # Extract 'exp' modifier (only one allowed)
    exp_matches = re.findall(RE_EXP, record)
    if exp_matches:
        results["modifiers"]["exp"] = exp_matches[0]

    # Function to safely perform reverse DNS lookup
    def safe_reverse_lookup(ip: str):
        # add to the list of ips:
        results["ips"].append(ip)

        try:
            # Handle CIDR notation by extracting base IP
            base_ip = ip.split("/")[0].strip()
            hostname = run_command(f"dig +short -x {base_ip} @{ns}")
            if hostname:
                return hostname.strip().strip(".").strip()
            return None
        except Exception as e:
            logger.warning(f"Error in reverse lookup for {ip}: {str(e)}")
            return None

    # Resolve hostnames from IP addresses
    for modifier, ip in results["mechanisms"]["ip4"]:
        hostname = safe_reverse_lookup(ip)

        if hostname:
            results["hostnames"].append(hostname)

    # For IPv6 addresses
    for modifier, ip in results["mechanisms"]["ip6"]:
        hostname = safe_reverse_lookup(ip)

        if hostname:
            results["hostnames"].append(hostname)

    # Process 'include' mechanisms recursively
    if max_recursion > 0:
        for modifier, include_domain in results["mechanisms"]["include"]:
            try:
                included_spf = get_dns_record(include_domain, "TXT", ns)
                if included_spf and "v=spf1" in included_spf.lower():
                    # Recursively process included SPF record
                    included_results = extract_ip_details_from_spf(
                        included_spf, include_domain, ns, max_recursion - 1
                    )
                    # Merge hostnames results
                    results["hostnames"].extend(included_results["hostnames"])
                    # Add the include domain itself
                    results["hostnames"].append(f"SPF_INCLUDE:{include_domain}")
                    # Merge IPs results
                    results["ips"].extend(included_results["ips"])
            except Exception as e:
                logger.warning(f"Error processing include:{include_domain}: {str(e)}")

    # Function to safely get A records and perform reverse lookups
    def get_a_records_with_hostnames(domain):
        try:
            a_records = get_dns_record(domain, "A", ns)
            hostnames = []
            if a_records:
                for ip in a_records.split("\n"):
                    if ip.strip():
                        hostname = safe_reverse_lookup(ip)
                        if hostname:
                            hostnames.append(hostname)
            return hostnames
        except Exception as e:
            logger.warning(f"Error getting A records for {domain}: {str(e)}")
            return []

    # Resolve A records
    for modifier, a_domain in results["mechanisms"]["a"]:
        hostnames = get_a_records_with_hostnames(a_domain)
        results["hostnames"].extend(hostnames)

    # Resolve MX records
    for modifier, mx_domain in results["mechanisms"]["mx"]:
        try:
            mx_records = get_dns_record(mx_domain, "MX", ns)
            if mx_records:
                for mx in mx_records.split("\n"):
                    if mx.strip():
                        # Extract the MX server name (after priority number)
                        mx_parts = mx.strip().split()
                        if len(mx_parts) > 1:
                            mx_server = mx_parts[1].strip().strip(".")
                            # Add hostnames from the MX server's A records
                            mx_hostnames = get_a_records_with_hostnames(mx_server)
                            results["hostnames"].extend(mx_hostnames)
        except Exception as e:
            logger.warning(f"Error processing MX for {mx_domain}: {str(e)}")

    # Process 'ptr' mechanisms - just add domain info for now
    # Full PTR validation would require the sender's IP, which we don't have
    for modifier, ptr_domain in results["mechanisms"]["ptr"]:
        if ptr_domain != "SENDER":
            results["hostnames"].append(f"PTR:{ptr_domain}")

    # Process 'exists' mechanisms - just add domain info
    for modifier, exists_domain in results["mechanisms"]["exists"]:
        results["hostnames"].append(f"EXISTS:{exists_domain}")

    # Process 'redirect' modifier if present
    if results["modifiers"]["redirect"]:
        redirect_domain = None  # type: ignore

        try:
            redirect_domain = results["modifiers"]["redirect"]

            redirect_spf = get_dns_record(redirect_domain, "TXT", ns)

            if redirect_spf and "v=spf1" in redirect_spf.lower() and max_recursion > 0:
                # Recursively process redirected SPF record
                redirect_results = extract_ip_details_from_spf(
                    redirect_spf, redirect_domain, ns, max_recursion - 1
                )
                # Merge hostnames results
                results["hostnames"].extend(redirect_results["hostnames"])
                # Add the redirect domain itself
                results["hostnames"].append(f"SPF_REDIRECT:{redirect_domain}")
                # Merge IPs results
                results["ips"].extend(redirect_results["ips"])
        except Exception as e:
            logger.warning(f"Error processing redirect={redirect_domain}: {str(e)}")

    # Make hostnames list unique
    results["hostnames"] = list(set(filter(None, results["hostnames"])))
    # Make IPs list unique
    results["ips"] = list(set(filter(None, results["ips"])))

    # sort the hostnames
    results["hostnames"] = sorted(results["hostnames"])
    # sort the ips
    results["ips"] = sorted(results["ips"])

    return results


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
            spf_info = extract_ip_details_from_spf(
                record=record, domain=domain, ns=ns, max_recursion=3
            )

            dns_info["SPF Hostnames"] = spf_info["hostnames"]

            dns_info["SPF IPs"] = spf_info["ips"]

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
