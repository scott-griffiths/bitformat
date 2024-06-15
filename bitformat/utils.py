from __future__ import annotations

import re
from typing import Pattern


# A token name followed by an integer number
NAME_INT_RE: Pattern[str] = re.compile(r'^([a-zA-Z][a-zA-Z0-9_]*?)(\d*)$')


def parse_name_length_token(fmt: str) -> tuple[str, int | None]:
    # Any single token with just a name and length
    if m2 := NAME_INT_RE.match(fmt):
        name = m2.group(1)
        length_str = m2.group(2)
        length = None if length_str == '' else int(length_str)
        return name, length
    raise ValueError(f"Can't parse 'name[length]' token '{fmt}'.")

