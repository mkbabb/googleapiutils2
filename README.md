# googleapiutils2

Utilities for
[Google's v2 Python API](https://github.com/googleapis/google-api-python-client).
Currently supports sections of the following resources:

-   Drive: `DriveResource`, `FilesResource`, `PermissionsResource`, `RepliesResource`,
    `...`
-   Sheets: `SpreadsheetsResource`, `ValuesResource`, `...`
-   Geocoding

## Quickstart

This project requires Python `^3.10` to run.

Several dependencies are needed, namely the aforesaid Google Python API, but also
Google's oauth library, and `requests`. Pre-bundled for ease of use are the fairly
monolithic `google-api-stubs`, which greatly improves the usage experience.

### via [`poetry`](https://python-poetry.org/docs/)

Install poetry, then run

> poetry install

And you're done.

## Overview

The library was written to be both consistent in general, and consistent with Google's
own API, just a little nicer to use. A note on IDs: anytime a resource ID is needed, one
can be provide the actual resource ID, or the URL to the resource. If a URL is provided,
this mapping is cached for future use.

## Drive

Example: copy a file to a folder.

```python
creds = get_oauth2_creds(config_obj)
drive = Drive(creds)

filename = "Heyy"

file = drive.get_name(filename, parents=[FOLDER_URL])
if file is not None:
    drive.delete(file["id"])

file = drive.copy(file_id=FILE_ID, to_filename=filename, to_folder_id=FOLDER_URL)
```

What the above does is:

-   Get the OAuth2 credentials from the `config_obj` object (JSON object representing
    the requisite credentials, see
    [here](https://developers.google.com/identity/protocols/oauth2/native-app#step-2:-send-a-request-to-googles-oauth-2.0-server)
    for more information).
-   create a `Drive` object thereupon.
-   Get the file with the given name, and delete it if it exists.
-   Copy the file with the given ID to the given folder, and return the new file.

## Sheets

Example: update a range of cells in a sheet.

```python
creds = get_oauth2_creds(config_path)
sheets = Sheets(creds)

Sheet1 = SheetsValueRange(sheets, SHEET_ID, sheet_name="Sheet1")

rows = [
    {
        "Heyy": "99",
    }
]
Sheet1[2:3, ...].update(rows)
```

What the above does is:

-   Get the OAuth2 credentials from the `config_path` file (see
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

```py
ix = SheetSlice["Sheet1", 1:3, 2:4] #  "Sheet1!B2:D4"
ix = SheetSlice["Sheet1", "A1:B2"]  #  "Sheet1!A1:B2"
ix = SheetSlice[1:3, 2:4]           #  "Sheet1!B2:D4"
ix = SheetSlice["A1:B2"]            #  "Sheet1!A1:B2"
ix = SheetSlice[..., 1:3]           #  "Sheet1!A1:Z3"
```

`SheetSlice` object can also be used as a key into a `SheetsValueRange` object, or a
dictionary (to use in updating a sheet's range, for example). Further, a
`SheetsValueRange` object can be sliced in a similar manner to that of a `SheetSlice`
object, and also be used as a dictionary key.
