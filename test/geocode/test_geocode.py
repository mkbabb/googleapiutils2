from __future__ import annotations

from typing import *

from googleapiutils2.geocode import Geocode


def test_geocode(geocoder: Geocode):
    address = "1600 Amphitheatre Parkway, Mountain View, CA"

    result = geocoder.geocode(address)

    assert result is not None

    assert len(result) == 1

    result = result[0]

    assert (
        result["formatted_address"]
        == "Google Building 40, 1600 Amphitheatre Pkwy, Mountain View, CA 94043, USA"
    )
    assert result["geometry"]["location_type"] == "ROOFTOP"
