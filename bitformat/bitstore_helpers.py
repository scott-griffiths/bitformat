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


def tidy_input_string(s: str) -> str:
    """Return string made lowercase and with all whitespace and underscores removed."""
    try:
        t = s.split()
    except (AttributeError, TypeError):
        raise ValueError(f"Expected str object but received a {type(s)} with value {s}.")
    return ''.join(t).lower().replace('_', '')


@functools.lru_cache(CACHE_SIZE)
def str_to_bitstore(s: str) -> BitStore:
    tokens = tokenparser(s)
    bs = BitStore()
    for token in tokens:
        bs += bitstore_from_token(*token)
    return bs


def bin2bitstore(binstring: str) -> BitStore:
    binstring = tidy_input_string(binstring)
    binstring = binstring.replace('0b', '')
    try:
        return BitStore.from_binstr(binstring)
    except ValueError:
        raise ValueError(f"Invalid character in bin initialiser {binstring}.")


def bin2bitstore_unsafe(binstring: str) -> BitStore:
    return BitStore.from_binstr(binstring)


def hex2bitstore(hexstring: str) -> BitStore:
    hexstring = tidy_input_string(hexstring)
    hexstring = hexstring.replace('0x', '')
    try:
        ba = bitarray.util.hex2ba(hexstring)
    except ValueError:
        raise ValueError("Invalid symbol in hex initialiser.")
    return BitStore.from_bitarray(ba)


def oct2bitstore(octstring: str) -> BitStore:
    octstring = tidy_input_string(octstring)
    octstring = octstring.replace('0o', '')
    try:
        ba = bitarray.util.base2ba(8, octstring)
    except ValueError:
        raise ValueError("Invalid symbol in oct initialiser.")
    return BitStore.from_bitarray(ba)


def int2bitstore(i: int, length: int, signed: bool) -> BitStore:
    i = int(i)
    try:
        x = BitStore.from_bitarray(bitarray.util.int2ba(i, length=length, endian='big', signed=signed))
    except OverflowError as e:
        if signed:
            if i >= (1 << (length - 1)) or i < -(1 << (length - 1)):
                raise ValueError(f"{i} is too large a signed integer for a Bits of length {length}. "
                                 f"The allowed range is [{-(1 << (length - 1))}, {(1 << (length - 1)) - 1}].")
        else:
            if i >= (1 << length):
                raise ValueError(f"{i} is too large an unsigned integer for a Bits of length {length}. "
                                 f"The allowed range is [0, {(1 << length) - 1}].")
            if i < 0:
                raise ValueError("uint cannot be initialised with a negative number.")
        raise e
    return x


def float2bitstore(f: Union[str, float], length: int) -> BitStore:
    f = float(f)
    fmt = {16: '>e', 32: '>f', 64: '>d'}[length]
    try:
        b = struct.pack(fmt, f)
    except OverflowError:
        # If float64 doesn't fit it automatically goes to 'inf'. This reproduces that behaviour for other types.
        b = struct.pack(fmt, float('inf') if f > 0 else float('-inf'))
    return BitStore.from_bytes(b)


literal_bit_funcs: Dict[str, Callable[..., BitStore]] = {
    '0x': hex2bitstore,
    '0X': hex2bitstore,
    '0b': bin2bitstore,
    '0B': bin2bitstore,
    '0o': oct2bitstore,
    '0O': oct2bitstore,
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
