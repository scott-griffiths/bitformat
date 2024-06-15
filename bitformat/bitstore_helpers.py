from __future__ import annotations

import struct
import functools
from typing import Union, Dict, Callable
import bitarray
from bitformat.bitstore import BitStore
from .dtypes import Dtype
import bitarray.util
import re
from typing import Pattern

# The size of various caches used to improve performance
CACHE_SIZE = 256

# A token name followed by an integer number
NAME_INT_RE: Pattern[str] = re.compile(r'^([a-zA-Z][a-zA-Z0-9_]*?)(\d*)$')

# Hex, oct or binary literals
LITERAL_RE: Pattern[str] = re.compile(r'^(?P<name>0([xob]))(?P<value>.+)', re.IGNORECASE)

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
    if name in literal_bit_funcs:
        return literal_bit_funcs[name](value)
    try:
        d = Dtype(name, token_length)
    except ValueError as e:
        raise ValueError(f"Can't parse token: '{e}'")
    if value is None and name != 'pad':
        raise ValueError(f"Token '{name}' requires a value.")
    bs = d.build(value)._bitstore
    if token_length is not None and len(bs) != d.bitlength:
        raise ValueError(f"Token with length {token_length} packed with value of length {len(bs)} "
                         f"({name}:{token_length}={value}).")
    return bs
