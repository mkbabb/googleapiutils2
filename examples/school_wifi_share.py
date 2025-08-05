"""
Used to share folders with school districts for the WiFi project.

- Retrieve responses from a Google Sheets document containing PSU IDs and email addresses.
- Extract the PSU IDs using a regular expression.
- Split the email addresses into a list.
- Retrieve all folders from specified locations.
- Iterate through the responses and grant permission for emails that match the PSU IDs in the folder names.
"""

from __future__ import annotations

import re
from itertools import chain

from googleapiutils2 import Drive, Permissions, Sheets

# Initialize the Google Drive, Sheets, and Permissions objects
drive = Drive()
sheets = Sheets()
permissions = Permissions(drive=drive)

# Columns of interest in the sheet
psu_col, email_col = (
    "What is your PSU name and ID?  Select the dropdown and then start typing the name to jump ahead in the list.",
    "What are the email addresses you'd like to grant access to the report? Please separate each email address by a comma.",
)

# URL to the responses sheet
responses_sheet_url = (
    "https://docs.google.com/spreadsheets/d/1hjeVzc_WsEVyth8lje9uZNBvSPldawFpj96lrclOahU/edit#gid=506522074"
)

# Retrieve responses as a DataFrame
responses_df = sheets.to_frame(sheets.values(responses_sheet_url, "Validated Responses"))
if responses_df is None:
    raise ValueError("No responses found")

# Regular expression to match PSU IDs
PSU_ID_RE = re.compile(r"\[(.*)\]")
responses_df["psu_id"] = responses_df[psu_col].map(lambda x: re.findall(PSU_ID_RE, x)[0])

# Splitting emails and converting to lowercase
responses_df["emails"] = responses_df[email_col].str.split(",")
responses_df["emails"] = responses_df["emails"].map(lambda emails: [i.strip().lower() for i in emails])

# Folder IDs
wifi_folders = ["1OCweN3_HDyXL4Gpowz4MaHb01LukSbpv"]
shodan_folders = [
    "1E2Tw6VavbOGQw-JwFRTZ-PhIymwT2aTg",
    "1kRbsNfUTUWACFcvl4ciG43y0RoqHXu60",
]

# Function to list files
list_func = lambda x: list(drive.list(x, fields="files(name,id)"))

# Gather all folders
all_folders = list(chain.from_iterable(list_func(x) for x in chain(shodan_folders, wifi_folders)))

# Iterate through responses and grant permissions
for _n, row in responses_df.iterrows():
    psu_id = row["psu_id"]
    emails = row["emails"]

    for folder in filter(lambda x: psu_id in x["name"], all_folders):
        for email in emails:
            permissions.create(file_id=folder["id"], email_address=email)
