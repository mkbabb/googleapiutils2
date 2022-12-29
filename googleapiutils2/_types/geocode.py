from __future__ import annotations

import typing
from typing import *

LocationType = Literal[
    "ROOFTOP", "RANGE_INTERPOLATED", "GEOMETRIC_CENTER", "APPROXIMATE"
]

if TYPE_CHECKING:

    @typing.type_check_only
    class AddressComponents(TypedDict):
        long_name: str
        short_name: str
        types: list[str]

    @typing.type_check_only
    class Location(TypedDict):
        lat: float
        lng: float

    @typing.type_check_only
    class ViewPort(TypedDict):
        northeast: Location
        southwest: Location

    @typing.type_check_only
    class Geometry(TypedDict):
        location: Location
        location_type: LocationType
        viewport: ViewPort

    @typing.type_check_only
    class GeocodeResult(TypedDict):
        address_components: list[AddressComponents]
        formatted_address: str
        geometry: Geometry
        place_id: str
        types: list[str]
