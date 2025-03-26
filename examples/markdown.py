from __future__ import annotations

from tempfile import NamedTemporaryFile

from googleapiutils2 import Drive, GoogleMimeTypes, get_oauth2_creds

creds = get_oauth2_creds()


drive = Drive(creds=creds)

md_url = "https://docs.google.com/document/d/1AaXNNNti-eDVjDvpL7LRgJ_4IN9p3HUg0H_QuG-7JAk/edit?pli=1&tab=t.0#heading=h.w1ky4f1afbr2"


with NamedTemporaryFile(suffix=".md") as temp_file:
    downloaded_path = drive.download(
        filepath=temp_file.name,
        file_id=md_url,
        mime_type=GoogleMimeTypes.md,
    )

    content = downloaded_path.read_text()

    print(f"Downloaded file to {downloaded_path}")
