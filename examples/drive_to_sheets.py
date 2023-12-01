import tempfile

import numpy as np
import pandas as pd

from googleapiutils2 import Drive, GoogleMimeTypes


def generate_random_csv(rows: int, cols: int) -> pd.DataFrame:
    data = np.random.rand(rows, cols)
    return pd.DataFrame(data)


drive = Drive()

folder_id = (
    "https://drive.google.com/drive/u/0/folders/1lWgLNquLCwKjW4lenekduwDZ3J7aqCZJ"
)


name = "random.csv"


with tempfile.NamedTemporaryFile(
    delete=False, suffix=".csv", mode="w", newline=""
) as tmpfile:
    rows, cols = 100, 100
    df = generate_random_csv(rows, cols)
    df.to_csv(tmpfile.name, index=False)

    drive.upload(
        filepath=tmpfile.name,
        name=name,
        parents=folder_id,
        mime_type=GoogleMimeTypes.sheets,
        recursive=True,
        update=True,
    )
