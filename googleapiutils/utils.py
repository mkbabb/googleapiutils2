from __future__ import annotations

import json
import pickle
import urllib.parse
from functools import cache
from pathlib import Path
from typing import *

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


def url_components(url: str) -> dict[str, List[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)


def update_url_params(url: str, params: dict) -> str:
    url_obj = urllib.parse.urlparse(url)
    params.update(urllib.parse.parse_qsl(url_obj.query))

    query = urllib.parse.urlencode(params)

    url_obj = urllib.parse.ParseResult(
        url_obj.scheme,
        url_obj.netloc,
        url_obj.path,
        url_obj.params,
        query,
        url_obj.fragment,
    )

    return url_obj.geturl()


GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]


TOKEN_PATH = "auth/token.pickle"
CONFIG_PATH = "auth/credentials.json"

FilePath = str | Path


def get_oauth2_creds(
    client_config: FilePath | dict = CONFIG_PATH,
    token_path: FilePath = TOKEN_PATH,
    scopes: List[str] = SCOPES,
) -> Optional[Credentials]:
    token_path = Path(token_path)

    if not isinstance(client_config, dict):
        path = Path(client_config)
        client_config = json.loads(path.read_bytes())

    is_service_account = client_config.get("type", "") == "service_account"

    if not is_service_account:
        creds: Credentials = None

        if token_path.exists():
            creds = pickle.loads(token_path.read_bytes())

        if creds is not None and not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())

        elif creds is None:
            flow = InstalledAppFlow.from_client_config(client_config, scopes)
            creds = flow.run_local_server(port=0)
            token_path.write_bytes(pickle.dumps(creds))

        return creds
    else:
        return service_account.Credentials.from_service_account_info(
            client_config, scopes=scopes
        )


def get_id_from_url(url: str) -> str:
    url_obj = urllib.parse.urlparse(url)
    path = url_obj.path
    paths = path.split("/")

    get_adjacent = (
        lambda x: paths[t_ix]
        if x in paths and (t_ix := paths.index(x) + 1) < len(paths)
        else None
    )

    id = get_adjacent("folders") or get_adjacent("d")

    if id is not None:
        return id
    else:
        comps = url_components(url)
        if (ids := comps.get("id")) is not None:
            return ids[0]
        else:
            raise ValueError(f"Could not parse file URL of {url}")


def parse_file_id(file_id: str | Iterable[str] | None):
    @cache
    def inner(file_id: str) -> str:
        if file_id.find("http") != -1:
            return get_id_from_url(file_id)
        else:
            return file_id

    if isinstance(file_id, str):
        return inner(file_id)
    elif isinstance(file_id, Iterable):
        return list(map(inner, file_id))
    else:
        return None


def to_base(x: str | int, base: int, from_base: int = 10) -> list[int]:
    if isinstance(x, str):
        x = int(x, base=from_base)

    y = []
    while x != 0:
        y.append(x % base)
        x //= base

    return y[::-1]


T = TypeVar("T")
P = ParamSpec("P")


def take_annotation_from(
    this: Callable[P, Optional[T]]
) -> Callable[[Callable], Callable[P, Optional[T]]]:
    def decorator(real_function: Callable) -> Callable[P, Optional[T]]:
        def new_function(*args: P.args, **kwargs: P.kwargs) -> Optional[T]:
            return real_function(*args, **kwargs)

        return new_function

    return decorator
