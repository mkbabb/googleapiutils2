# googleapiutils2

Utilities for
[Google's v2 Python API](https://github.com/googleapis/google-api-python-client).
Currently supports sections of the following resources:

-   Drive: `FilesResource`, `...`
-   Sheets: `SpreadsheetsResource`, `...`
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

## Drive

...

## Sheets

Simple example:

```python
...
creds = get_oauth2_creds(client_config=config_path)
sheets = Sheets(creds=creds)

sheet_id = "id"
Sheet1 = SheetsValueRange(sheets, sheet_id, sheet_name="Sheet1")

rows = [
    {
        "Heyy": "99",
    }
]
Sheet1[2:3, ...].update(rows)
```

What the above does is: - Get the OAuth2 credentials from the `client_config.json`
file - create a `Sheets` object thereupon. - Create a `SheetsValueRange` object, which
is a wrapper around the `spreadsheets.values` API. - Update the range `Sheet1!A2:B3`
with the given rows.

Note the slicing syntax, which will feel quite familiar for any Python programmer.

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
