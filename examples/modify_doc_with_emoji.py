from tempfile import NamedTemporaryFile

from googleapiutils2 import Drive, GoogleMimeTypes

doc_url = "https://docs.google.com/document/d/1hZ0gBz5NJ_Y4MtmurTKPoBNoFQykmwy4ZHyTSRjBUqY/edit?tab=t.0"

drive = Drive()

file = drive.get(doc_url)

print("Downloading document as markdown...")
with NamedTemporaryFile(suffix=".md") as temp_file:
    downloaded_path = drive.download(
        filepath=temp_file.name,
        file_id=doc_url,
        mime_type=GoogleMimeTypes.md,
    )

    content = downloaded_path.read_text()

print("Adding emoji to content...")
modified_content = content

print("Uploading modified content back to document...")
with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as temp_file:
    temp_file.write(modified_content)
    temp_file.flush()

    drive.upload(filepath=temp_file.name, name=file["name"], update=True)

print("Done! Document has been updated with emojis.")
