"""Shared identifier validation."""

import re

ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


def is_valid_id(value: object) -> bool:
    return isinstance(value, str) and ID_PATTERN.fullmatch(value) is not None
