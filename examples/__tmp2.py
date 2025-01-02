from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, TypeVar, Callable, List, Any
import re
import PyPDF2
from googleapiutils2 import Sheets


@dataclass
class Transaction:
    """Represents a single transaction from the statement."""

    date: datetime
    description: str
    account_fee: float | None
    amount: float
    balance: float
    transaction_id: str = ""


# Constants
DATE_FORMAT = "%m/%d/%Y"
SHEET_HEADERS = [
    'Date',
    'Month',
    'Description',
    'Account Fee',
    'Amount',
    'Balance',
    'Transaction ID',
]

# Regex patterns
MONEY_PATTERN = re.compile(r'[+-]?\$[\d,]+\.\d+')
TRANSACTION_ID_PATTERN = re.compile(r'\b[0-9a-f]{12}\b')
DATE_PATTERN = re.compile(r'\d{2}/\d{2}/\d{4}')

T = TypeVar('T')


def chunk_by(
    items: List[T], predicate: Callable[[T], bool], include_marker: bool = False
) -> Iterator[List[T]]:
    """
    Generic function to chunk a list based on a predicate.

    Args:
        items: List to chunk
        predicate: Function that returns True for chunk boundaries
        include_marker: Whether to include the boundary item in the chunk

    Yields:
        Chunks of the original list
    """
    current_chunk: List[T] = []

    for item in items:
        if predicate(item):
            if current_chunk:
                yield current_chunk
            current_chunk = [item] if include_marker else []
        else:
            current_chunk.append(item)

    if current_chunk:
        yield current_chunk


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text content from PDF file."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        return "\n".join(page.extract_text() for page in pdf_reader.pages)


def clean_amount(amount_str: str) -> float:
    """Convert amount string to float, handling negative values."""
    return float(amount_str.replace("$", "").replace(",", "").replace("+", ""))


def extract_transaction_id(text: str) -> str:
    """Extract transaction ID from text."""
    match = TRANSACTION_ID_PATTERN.search(text.lower())
    return match.group(0) if match else ""


def find_transaction_sections(content: str) -> Iterator[List[str]]:
    """Find transaction sections in content."""
    lines = [line.strip() for line in content.split('\n') if line.strip()]

    def is_section_start(line: str) -> bool:
        is_start = "Transactions" in line and "DATE" in "".join(
            lines[lines.index(line) : lines.index(line) + 4]
        )
        return is_start

    def is_section_end(line: str) -> bool:
        return "Ending Balance" in line or "No Transactions" in line

    first_section = True
    for section in chunk_by(lines, is_section_start, include_marker=True):
        if not len(section):
            continue

        if first_section:
            first_section = False
            continue

        transaction_lines = []
        for line in section[2:]:  # Skip header
            if is_section_end(line):
                break
            transaction_lines.append(line)

        if transaction_lines:
            yield transaction_lines


def parse_amounts(line: str) -> tuple[float, float, float | None]:
    """Parse balance, amount, and optional fee from a line."""
    amounts = list(reversed([m.group(0) for m in MONEY_PATTERN.finditer(line)]))
    if not amounts:
        raise ValueError(f"No amounts found in line: {line}")

    balance = clean_amount(amounts[0])
    amount = clean_amount(amounts[1]) if len(amounts) > 1 else 0.0
    account_fee = clean_amount(amounts[2]) if len(amounts) > 2 else None

    # If the account fee is not None and
    # "From Apple Cash" is in the line, set account_fee to None
    # And if the amounts array has exactly 3 elements:
    if len(amounts) == 3 and (account_fee is not None and "From Apple Cash" in line):
        account_fee = None

    return balance, amount, account_fee


def parse_transactions(content: str) -> List[Transaction]:
    """Parse all transactions from statement content."""
    transactions = []

    for section in find_transaction_sections(content):
        start_idx = (
            next(
                (i for i, line in enumerate(section) if "Starting Balance" in line), -1
            )
            + 1
        )
        section = section[start_idx:]

        def is_date_line(line: str) -> bool:
            return bool(DATE_PATTERN.match(line))

        for date_chunk in chunk_by(section, is_date_line, include_marker=True):
            if not date_chunk:
                continue

            date_str = DATE_PATTERN.search(date_chunk[0]).group(0)  # type: ignore
            date = datetime.strptime(date_str, DATE_FORMAT)
            line_text = " ".join(date_chunk)
            balance, amount, account_fee = parse_amounts(date_chunk[-1])
            transaction_id = extract_transaction_id(line_text)

            transactions.append(
                Transaction(
                    date=date,
                    description=line_text,
                    account_fee=account_fee,
                    amount=amount,
                    balance=balance,
                    transaction_id=transaction_id,
                )
            )

    return transactions


def transactions_to_sheet_data(transactions: List[Transaction]) -> List[List[Any]]:
    """Convert transactions to format suitable for Google Sheets."""
    data = [SHEET_HEADERS]  # Start with headers

    for t in transactions:
        data.append(
            [
                t.date.isoformat(),
                t.date.strftime("%B"),
                t.description,
                f"{t.account_fee:.2f}" if t.account_fee is not None else "",
                f"{t.amount:.2f}",
                f"{t.balance:.2f}",
                t.transaction_id,
            ]
        )

    return data


def process_statement(pdf_path: Path, sheet_url: str, sheet_name: str) -> int:
    """Process PDF statement and save to Google Sheets."""
    content = extract_pdf_text(pdf_path)
    transactions = parse_transactions(content)

    sheets = Sheets()

    # Clear existing sheet content
    sheets.clear(
        spreadsheet_id=sheet_url,
        range_name=sheet_name,
    )

    # Write new data
    sheet_data = transactions_to_sheet_data(transactions)
    sheets.update(spreadsheet_id=sheet_url, range_name=sheet_name, values=sheet_data)

    return len(transactions)


def main():
    """Main execution function."""
    pdf_path = Path('/Users/mkbabb/Downloads/Apple Cash Statement.pdf')
    sheet_url = "https://docs.google.com/spreadsheets/d/1CeH0as2XlSDxjhbr6R8slj7eQQWeZYlk3lJwqn_MW3U/edit?gid=1996446037#gid=1996446037"
    sheet_name = "Transactions"

    try:
        num_transactions = process_statement(pdf_path, sheet_url, sheet_name)
        print(f"Successfully processed {num_transactions} transactions")
        print(f"Data written to Google Sheet: {sheet_url}")
    except Exception as e:
        print(f"Error processing statement: {e}")


if __name__ == "__main__":
    main()
