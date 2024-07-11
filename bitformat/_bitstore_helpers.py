from __future__ import annotations

import functools
from typing import Dict, Callable
from bitformat._bitstore import BitStore
from ._dtypes import Dtype
import re
from typing import Pattern

# The size of various caches used to improve performance
CACHE_SIZE = 256

# Hex, oct or binary literals
LITERAL_RE: Pattern[str] = re.compile(r'^(?P<name>0([xob]))(?P<value>.+)', re.IGNORECASE)

# name[length][=value]
NAME_INT_VALUE_RE: Pattern[str] = re.compile(r'^([a-zA-Z][a-zA-Z0-9_]*?)(\d*)(?:=(.*))?$')


@functools.lru_cache(CACHE_SIZE)
def parse_single_token(token: str) -> tuple[str, int | None, str | None]:
    if m := NAME_INT_VALUE_RE.match(token):
        name = m.group(1)
        length_str = m.group(2)
        value = m.group(3)
        if value == '':
            value = None
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


@functools.lru_cache(CACHE_SIZE)
def str_to_bitstore(s: str) -> BitStore:
    tokens = tokenparser(s)
    bs = BitStore()
    for token in tokens:
        bs += bitstore_from_token(*token)
    return bs


literal_bit_funcs: Dict[str, Callable[..., BitStore]] = {
    '0x': BitStore.from_hex,
    '0X': BitStore.from_hex,
    '0b': BitStore.from_bin,
    '0B': BitStore.from_bin,
    '0o': BitStore.from_oct,
    '0O': BitStore.from_oct,
}


def bitstore_from_token(name: str, token_length: int | None, value: str | None) -> BitStore:
    try:
        f = literal_bit_funcs[name]
    except KeyError:
        pass
    else:
        return f(value)
    d = Dtype(name, token_length)
    bs = d.pack(value)._bitstore
    return bs
