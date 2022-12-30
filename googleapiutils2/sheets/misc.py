from enum import Enum

VERSION = "v4"


class ValueInputOption(Enum):
    unspecified = "INPUT_VALUE_OPTION_UNSPECIFIED"
    raw = "RAW"
    user_entered = "USER_ENTERED"


class ValueRenderOption(Enum):
    formatted = "FORMATTED_VALUE"
    unformatted = "UNFORMATTED_VALUE"
    formula = "FORMULA"
