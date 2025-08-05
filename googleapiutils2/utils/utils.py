from __future__ import annotations

import json
import time
import urllib.parse
from collections import defaultdict
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
)

import googleapiclient.http
import requests

from googleapiutils2.utils.misc import THROTTLE_TIME, FilePath

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import Color


class Throttler:
    """Manages throttling for function calls."""

    def __init__(self, throttle_time: float = THROTTLE_TIME):
        self._throttle_time = throttle_time
        self._prev_time: float | None = None

    def dt(self) -> float:
        if self._throttle_time == 0:
            return 0

        if self._prev_time is not None:
            dt = time.perf_counter() - self._prev_time

            return max(0, self._throttle_time - dt)

        return 0

    def reset(self):
        self._prev_time = time.perf_counter()

    def throttle(self) -> float:
        dt = self.dt()

        if dt > 0:
            # logger.debug(f"Throttling for {dt:.2f} seconds")
            time.sleep(dt)

        self.reset()

        return dt


def named_methodkey(name: str):
    """Hash key that ignores the first argument of a method, but is named for the method."""

    def _key(self, *args, **kwargs):
        return (name, *list(args), *list(kwargs.values()))

    return _key


def hex_to_rgb(hex_code: str) -> Color:
    """Converts a hex color code to RGB(A), where each value is between 0 and 1.

    Args:
        hex_code (str): Hex color code to convert. Can be 3, 4, 6, or 8 characters long (optional alpha is supported).
    """
    hex_code = hex_code.lstrip("#")

    if len(hex_code) == 3 or len(hex_code) == 4:
        hex_code = "".join([2 * c for c in hex_code])

    rgb: Color = {
        "red": int(hex_code[:2], 16),
        "green": int(hex_code[2:4], 16),
        "blue": int(hex_code[4:6], 16),
    }

    if len(hex_code) == 8:
        rgb["alpha"] = int(hex_code[6:8], 16)
    elif len(hex_code) != 6:
        raise ValueError("Invalid hex code")

    return {k: v / 255.0 for k, v in rgb.items()}  # type: ignore


def get_url_params(url: str) -> dict[str, list[str]]:
    """Get the components of the given URL."""
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)


def update_url_params(url: str, params: dict) -> str:
    """Update the query parameters of the given URL with the given params."""
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


def path_or_str_to_json(path_or_str: FilePath | str) -> dict:
    if isinstance(path_or_str, str):
        try:
            return json.loads(path_or_str)
        except json.JSONDecodeError:
            pass

        path = Path(path_or_str)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        else:
            path_or_str = path

    return json.loads(path_or_str.read_bytes())


def download_large_file(
    url: str,
    filepath: FilePath,
    chunk_size: int = googleapiclient.http.DEFAULT_CHUNK_SIZE,
) -> Path:
    """Download a large file from the given URL to the given filepath."""

    filepath = Path(filepath)

    with requests.get(url, stream=True) as r:
        r.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                f.write(chunk)

    return filepath


def to_base(x: str | int, base: int, from_base: int = 10) -> list[int]:
    if isinstance(x, str):
        x = int(x, base=from_base)

    y = []
    while True:
        y.append(x % base)
        if (x := (x // base) - 1) < 0:
            break

    return y[::-1]


def nested_defaultdict(existing: dict | Any | None = None, **kwargs: Any) -> dict[Any, Any]:
    if existing is None:
        existing = {}
    elif not isinstance(existing, dict):
        return existing
    existing = {key: nested_defaultdict(val) for key, val in existing.items()}
    return defaultdict(nested_defaultdict, existing, **kwargs)


def deep_update(d: dict, u: dict) -> dict:
    for k, v in u.items():
        if isinstance(v, dict):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d
