from __future__ import annotations

import os
from typing import *

import pytest

from googleapiutils2.geocode import Geocode


@pytest.fixture(scope="session", autouse=True)
def geocoder() -> Geocode:
    api_key = os.environ.get("GEOCODING_API_KEY", "")
    return Geocode(api_key=api_key)
