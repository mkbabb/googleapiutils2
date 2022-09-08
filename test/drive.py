from __future__ import annotations

import mimetypes
import os
from io import BytesIO
from pathlib import Path
from typing import *

import googleapiclient
import googleapiclient.http
from google.oauth2.credentials import Credentials
from googleapiclient import discovery

from googleapiutils.utils import (
    FilePath,
    GoogleMimeTypes,
    create_google_mime_type,
    get_oauth2_creds,
    parse_file_id,
)

from googleapiutils.drive import Drive

name = Path("friday-institute-reports")
dir = Path("auth")

token_path = dir.joinpath(name.with_suffix(".token.pickle"))
config_path = dir.joinpath(name.with_suffix(".credentials.json"))

creds = get_oauth2_creds(
    token_path=token_path, client_config=config_path, is_service_account=True
)

drive = Drive(creds=creds)


swain_url = (
    "https://drive.google.com/drive/u/0/folders/1N5kVZ5vJtaOcAZg0jsdYXvu5EUtFjlYc"
)

files = drive.list_children(parent_id=swain_url)
for file in files:
    print(file)

ECF_FOLDER_ID = parse_file_id(
    "https://drive.google.com/drive/u/0/folders/1fB2mj-hl7KIduiNidbWLlMAFXZ76GmN8"
)

filepath = "/Users/mkbabb/Programming/ecf-dedup/data/ECF Deduped.csv"

drive.upload_file(
    filepath=filepath,
    google_mime_type="file",
    kwargs={"body": {"parents": [ECF_FOLDER_ID]}},
)
