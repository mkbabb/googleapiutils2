import re
import time
from itertools import chain
from pathlib import Path
from typing import *

import pandas as pd

from googleapiutils2.drive.drive import Drive
from googleapiutils2.sheets.sheets import Sheets
from googleapiutils2.utils import get_oauth2_creds

PSU_ID_RE = re.compile("\[(.*)\]")


dir = Path("auth")

config_path = dir.joinpath("friday-institute-reports.credentials.json")

creds = get_oauth2_creds(client_config=config_path)

drive = Drive(creds=creds)
sheets = Sheets(creds=creds)


psu_col, email_col = (
    "What is your PSU name and ID?  Select the dropdown and then start typing the name to jump ahead in the list.",
    "What are the email addresses you'd like to grant access to the report? Please separate each email address by a comma.",
)

responses_sheet = "https://docs.google.com/spreadsheets/d/1hjeVzc_WsEVyth8lje9uZNBvSPldawFpj96lrclOahU/edit#gid=506522074"

t = sheets.get(responses_sheet, "Validated Responses")
responses_df = pd.DataFrame(t["values"])
responses_df: pd.DataFrame = responses_df.rename(columns=responses_df.iloc[0]).drop(
    responses_df.index[0]
)

responses_df["psu_id"] = responses_df[psu_col].map(
    lambda x: re.findall(PSU_ID_RE, x)[0]
)
responses_df["emails"] = responses_df[email_col].str.split(",")
responses_df["emails"] = responses_df["emails"].map(
    lambda emails: [i.strip().lower() for i in emails]
)


wifi_folders = ["1OCweN3_HDyXL4Gpowz4MaHb01LukSbpv"]

shodan_folders = [
    "1E2Tw6VavbOGQw-JwFRTZ-PhIymwT2aTg",
    "1kRbsNfUTUWACFcvl4ciG43y0RoqHXu60",
]

list_func = lambda x: list(drive.list_children(x, fields="files(name,id)"))

all_folders = chain(shodan_folders)
all_folders = list(chain.from_iterable((list_func(x) for x in all_folders)))


for n, row in responses_df.iterrows():
    psu_id = row["psu_id"]
    emails = row["emails"]

    for folder in filter(lambda x: psu_id in x["name"], all_folders):
        folder_id = folder["id"]

        for email in emails:
            drive.permissions_create(file_id=folder["id"], email_address=email)
