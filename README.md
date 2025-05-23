# googleapiutils2

Utilities for
[Google's v2 Python API](https://github.com/googleapis/google-api-python-client).
Currently supports sections of the following resources:

-   [Drive](https://developers.google.com/drive/api/reference/rest/v3): `DriveResource`,
    `FilesResource`, `PermissionsResource`, `RepliesResource`, `...`
-   [Sheets](https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets):
    `SpreadsheetsResource`, `ValuesResource`, `...`
-   [Geocoding](https://developers.google.com/maps/documentation/geocoding/overview)

## Quickstart 🚀

This project requires Python `^3.12` to run.

Several dependencies are needed, namely the aforesaid Google Python API, but also
Google's oauth library, and `requests`. Pre-bundled for ease of use is the fairly
monolithic `google-api-stubs`, which greatly improves the usage experience.

### via [`poetry`](https://python-poetry.org/docs/)

Install poetry, then run

> poetry add googleapiutils2

And you're done.

## Overview 📖

The library was written to be consistent with Google's own Python API - just a little
easier to use. Most `Drive` and `Sheets` operations are supported using explicit
parameters. But many functions thereof take a `**kwargs` parameter (used for parameter
forwarding) to allow for the more granular usage of the underlying API.

**A note on IDs:** anytime a resource ID is needed, one can be provide the actual resource
ID, or the URL to the resource. If a URL is provided, this mapping is cached for future
use.

## Authentication 🔑

Before using a `Drive` or `Sheets` object, one must first authenticate. This is done via
the `google.oauth2` library, creating a `Credentials` object.

### Custom Credentials

The library supports two methods of authentication:

-   via a Google service account (recommended, see more
    [here](https://cloud.google.com/iam/docs/creating-managing-service-accounts))
-   via OAuth2 (see more
    [here](https://developers.google.com/identity/protocols/oauth2/native-app))

With a service account, one can programmatically access resources without user input.
This is by far the easiest route, but requires a bit of setup.

If one's not using a service account, the library will attempt to open a browser window
to authenticate using the provided credentials. This authentication is cached for future
usage (though it does expire on some interval) - so an valid token path is required.

See the [`get_oauth2_creds`](googleapiutils2/utils.py) function for more information.

### Default Credentials

To expedite development, all credentials-based objects will default to using a service
account by way of the following discovery scheme:

-   If `./auth/credentials.json` exists, use that credentials file.
-   If the `GOOGLE_API_CREDENTIALS` environment variable is set, use the credentials
    file pointed to by the variable. - This can either be a path to a file, or a JSON object.

## Drive 📁

### MIME Types

When you upload a file to Google Drive, you must specify the original file's MIME type and the desired uploaded MIME type: the `from_mime_type` and `to_mime_type` parameters, respectively. The `GoogleMimeTypes` class provides a list of common MIME types.

We attempt to infer both MIME types from the file extension, but this is not always possible. The inference scheme is as thus:

-   If either parameter is explicitly set, e.g. is not None, the value is used.
-   If the file's already been uploaded, the MIME type is inferred from the file's metadata.
-   If the file's not been uploaded, the MIME type is inferred from the file's extension.
-   If the file's extension is not recognized, the MIME type is set to `GoogleMimeTypes.file`.
-

#### Markdown Support

The library supports uploading Markdown files to Google Drive. The MIME type is set to `GoogleMimeTypes.markdown`, and the file is converted to Google Docs format upon upload.

Conversely when downloading a markdown file, set MIME type `GoogleMimeTypes.markdown`, and the file will be downloaded first as an HTML file, and then converted to markdown format, thereupon renamed to `.md`.

### Example: upload a file to a folder.

```python
from googleapiutils2 import Drive, get_oauth2_creds

creds = get_oauth2_creds() # explicitly get the credentials; you can share these with Sheets, etc.
drive = Drive(creds=creds)

# This will upload to your root Google Drive folder
drive.upload(
    filepath="examples/hey.txt",
    name="Asset 1",
    to_mime_type=GoogleMimeTypes.docs,
)
```

### Example: copy a file to a folder.

```python
from googleapiutils2 import Drive
FILE_ID = ...
FOLDER_URL = ...

drive = Drive() # implicitly get the credentials

filename = "Heyy"

file = drive.get(filename, parents=[FOLDER_URL])
if file is not None:
    drive.delete(file["id"])

file = drive.copy(file_id=FILE_ID, to_filename=filename, to_folder_id=FOLDER_URL)
```

What the above does is:

-   Get the OAuth2 credentials using the default discvoery scheme (JSON object
    representing the requisite credentials, see
    [here](https://developers.google.com/identity/protocols/oauth2/native-app#step-2:-send-a-request-to-googles-oauth-2.0-server)
    for more information).
-   create a `Drive` object thereupon.
-   Get the file with the given name, and delete it if it exists.
-   Copy the file with the given ID to the given folder, and return the new file.

## Sheets 📊

### Example: update a range of cells in a sheet.

```python
SHEET_ID = ...

sheets = Sheets() # implicitly get the credentials

Sheet1 = SheetsValueRange(sheets, SHEET_ID, sheet_name="Sheet1")

rows = [
    {
        "Heyy": "99",
    }
]
Sheet1[2:3, ...].update(rows)
```

What the above does is:

-   Get the OAuth2 credentials using the default discovery scheme (JSON object
    representing the requisite credentials, see
    [here](https://developers.google.com/identity/protocols/oauth2/native-app#step-2:-send-a-request-to-googles-oauth-2.0-server)
    for more information).
-   create a `Sheets` object thereupon.
-   Create a `SheetsValueRange` object, which is a wrapper around the
    `spreadsheets.values` API.
-   Update the range `Sheet1!A2:B3` with the given rows.

Note the slicing syntax, which will feel quite familiar for any user of Numpy or Pandas.

### SheetSlice

A `SheetsValueRange` object can be sliced in a similar manner to that of a Numpy array.
The syntax is as follows:

    slc = Sheet[rows, cols]

Wherein `rows` and `cols` are either integers, slices of integers (stride is not
supported), strings (in A1 notation), or ellipses (`...`).

Note that Google's implementation of A1 notation is 1-indexed; 0 is invalid (e.g., 1
maps to `A`, 2 to `B`, etc.)

```py
ix = SheetSlice["Sheet1", 1:3, 2:4] #  "Sheet1!B2:D4"
ix = SheetSlice["Sheet1", "A1:B2"]  #  "Sheet1!A1:B2"
ix = SheetSlice[1:3, 2:4]           #  "Sheet1!B2:D4"
ix = SheetSlice["A1:B2"]            #  "Sheet1!A1:B2"
ix = SheetSlice[..., 1:3]           #  "Sheet1!A1:Z3"

values = {
    SheetSlice["A1:B2"]: [
        ["Heyy", "99"],
        ["Heyy", "99"],
    ],
} # "Sheet1!A1:B2" = [["Heyy", "99"], ["Heyy", "99"]]
```

A `SheetSlice` can also be used as a key into a `SheetsValueRange`, or a dictionary (to
use in updating a sheet's range via `.update()`, for example). Further, a
`SheetsValueRange` can be sliced in a similar manner to that of a `SheetSlice`.

```py
Sheet1[2:3, ...].update(rows)
...
```
