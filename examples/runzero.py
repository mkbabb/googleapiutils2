from __future__ import annotations

import os
import tempfile
from typing import *

import requests

from googleapiutils2 import Drive, GoogleMimeTypes, Sheets

drive = Drive()
sheets = Sheets()

base_folder = (
    "https://drive.google.com/drive/u/0/folders/1rIwqPViVFlblsAjKMGzrJTQ4GCtt85uz"
)

token = os.getenv("RUNZERO_TOKEN")

base_url = "https://console.runzero.com/api/v1.0/"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

endpoints = [
    "export/org/assets.csv",
    "export/org/services.csv",
    "export/org/sites.csv",
    "export/org/wireless.csv",
    "export/org/software.csv",
    "export/org/vulnerabilities.csv",
    "export/org/users.csv",
    "export/org/groups.csv",
    "account/orgs/{org_id}",
    "org/agents",
    "org/tasks",
]

get_all_orgs_endpoint = "account/orgs"

orgs = requests.get(base_url + get_all_orgs_endpoint, headers=headers).json()

org_folders = {}

for o in orgs:
    name, oid = o["name"], o["id"]

    folder = drive.create(
        name=name,
        mime_type=GoogleMimeTypes.folder,
        parents=base_folder,
        get_extant=True,
    )

    org_folders[name] = folder


for name, folder in org_folders.items():
    print(f"Processing {name}")

    for endpoint in endpoints:
        url = (base_url + endpoint).format(org_id=oid)

        print(f"Downloading {url}")

        r = requests.get(url, headers=headers, params={"_oid": oid})
        r.raise_for_status()

        with tempfile.NamedTemporaryFile(mode="w") as f:
            f.write(r.text)

            name = endpoint.split("/")[-1]
            if name == "{org_id}":
                name = "org_info"

            drive.upload(
                filepath=f.name,
                name=name,
                to_mime_type=GoogleMimeTypes.csv,
                parents=folder["id"],
            )
