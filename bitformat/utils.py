from __future__ import annotations

import functools
import re
from typing import Pattern

# A token name followed by an integer number
NAME_INT_RE: Pattern[str] = re.compile(r'^([a-zA-Z][a-zA-Z0-9_]*?)(\d*)$')

CACHE_SIZE = 256

# Hex, oct or binary literals
LITERAL_RE: Pattern[str] = re.compile(r'^(?P<name>0([xob]))(?P<value>.+)', re.IGNORECASE)


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


@functools.lru_cache(CACHE_SIZE)
def parse_single_token(token: str) -> tuple[str, int | None, str | None]:
    if (equals_pos := token.find('=')) == -1:
        value = None
    else:
        value = token[equals_pos + 1:]
        token = token[:equals_pos]
    if m2 := NAME_INT_RE.match(token):
        name = m2.group(1)
        length_str = m2.group(2)
        if length_str == '':
            return name, None, value
        return name, int(length_str), value
    else:
        raise ValueError(f"Can't parse token '{token}'. It should be in the form 'name[length][=value]'.")


@functools.lru_cache(CACHE_SIZE)
def tokenparser(fmt: str) -> \
        list[tuple[str, int | str | None, str | None]]:
    """Divide the format string into tokens and parse them.

    Return list of [initialiser, length, value]
    initialiser is one of: hex, oct, bin, uint, int, 0x, 0o, 0b etc.
    length is None if not known, as is value.

    tokens must be of the form: [initialiser][length][=value]

    """
    fmt = ''.join(fmt.split())  # Remove whitespace
    ret_vals: list[tuple[str, str | int | None, str | None]] = []
    for token in fmt.split(','):
        if not token:
            continue
        # Match literal tokens of the form 0x... 0o... and 0b...
        if m := LITERAL_RE.match(token):
            ret_vals.append((m.group('name'), None, m.group('value')))
            continue
        ret_vals.append(parse_single_token(token))
    return ret_vals
