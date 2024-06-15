from __future__ import annotations

import functools
import re

# TODO: This is defined twice.
# A token name followed by an integer number
NAME_INT_RE: Pattern[str] = re.compile(r'^([a-zA-Z][a-zA-Z0-9_]*?)(\d*)$')


CACHE_SIZE = 256


@functools.lru_cache(CACHE_SIZE)
def parse_name_length_token(fmt: str, **kwargs) -> tuple[str, int | None]:
    # Any single token with just a name and length
    if m2 := NAME_INT_RE.match(fmt):
        name = m2.group(1)
        length_str = m2.group(2)
        length = None if length_str == '' else int(length_str)
    else:
        raise ValueError(f"Can't parse 'name[length]' token '{fmt}'.")
    return name, length

