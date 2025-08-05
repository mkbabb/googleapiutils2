from __future__ import annotations

from typing import Any

from loguru import logger

from googleapiutils2 import Drive, Sheets, SheetsMonitor, get_oauth2_creds


def handle_sheet_changes(data: Any, monitor: SheetsMonitor) -> None:
    """Process changes to the monitored sheet range.

    Args:
        data: The sheet data returned from sheets.values()
    """
    try:
        # Convert to dataframe for easier processing
        df = Sheets.to_frame(data)

        if len(df) == 0:
            logger.warning("Received empty data update")
            return

        # Process the changes
        logger.info(f"Received update with {len(df)} rows")

        monitor.stop()

        logger.info("STOPPING...")

    except Exception as e:
        logger.exception(f"Error processing sheet changes: {e}")


def main():
    # Initialize API clients

    creds = get_oauth2_creds()
    drive = Drive(creds=creds)
    sheets = Sheets(creds=creds)

    sheet_url = "https://docs.google.com/spreadsheets/d/1d07HFq7wSbYPsuwBoJcd1E1R4F14RkeN-3GUyzvWepw/edit?gid=285351317#gid=285351317"

    monitor = SheetsMonitor(
        sheets=sheets,
        drive=drive,
        spreadsheet_id=sheet_url,
        callback=handle_sheet_changes,
        range_name="Sheet1!A:Z",  # Monitor all columns in Sheet1
        interval=5,  # Check every 30 seconds
    )

    monitor.start()


if __name__ == "__main__":
    main()
