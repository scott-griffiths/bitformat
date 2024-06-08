from __future__ import annotations

import struct
import functools
from typing import Union, Optional, Dict, Callable
import bitarray
from bitformat.bitstore import BitStore
import bitformat
import bitarray.util

# The size of various caches used to improve performance
CACHE_SIZE = 256


def tidy_input_string(s: str) -> str:
    """Return string made lowercase and with all whitespace and underscores removed."""
    try:
        t = s.split()
    except (AttributeError, TypeError):
        raise ValueError(f"Expected str object but received a {type(s)} with value {s}.")
    return ''.join(t).lower().replace('_', '')


@functools.lru_cache(CACHE_SIZE)
def str_to_bitstore(s: str) -> BitStore:
    _, tokens = bitformat.utils.tokenparser(s)
    bs = BitStore()
    for token in tokens:
        bs += bitstore_from_token(*token)
    return bs


def bin2bitstore(binstring: str) -> BitStore:
    binstring = tidy_input_string(binstring)
    binstring = binstring.replace('0b', '')
    try:
        return BitStore.fromstr(binstring)
    except ValueError:
        raise bitformat.CreationError(f"Invalid character in bin initialiser {binstring}.")


def bin2bitstore_unsafe(binstring: str) -> BitStore:
    return BitStore.fromstr(binstring)


def hex2bitstore(hexstring: str) -> BitStore:
    hexstring = tidy_input_string(hexstring)
    hexstring = hexstring.replace('0x', '')
    try:
        ba = bitarray.util.hex2ba(hexstring)
    except ValueError:
        raise bitformat.CreationError("Invalid symbol in hex initialiser.")
    return BitStore.frombitarray(ba)


def oct2bitstore(octstring: str) -> BitStore:
    octstring = tidy_input_string(octstring)
    octstring = octstring.replace('0o', '')
    try:
        ba = bitarray.util.base2ba(8, octstring)
    except ValueError:
        raise bitformat.CreationError("Invalid symbol in oct initialiser.")
    return BitStore.frombitarray(ba)


def int2bitstore(i: int, length: int, signed: bool) -> BitStore:
    i = int(i)
    try:
        x = BitStore.frombitarray(bitarray.util.int2ba(i, length=length, endian='big', signed=signed))
    except OverflowError as e:
        if signed:
            if i >= (1 << (length - 1)) or i < -(1 << (length - 1)):
                raise bitformat.CreationError(f"{i} is too large a signed integer for a bitstring of length {length}. "
                                              f"The allowed range is [{-(1 << (length - 1))}, {(1 << (length - 1)) - 1}].")
        else:
            if i >= (1 << length):
                raise bitformat.CreationError(f"{i} is too large an unsigned integer for a bitstring of length {length}. "
                                              f"The allowed range is [0, {(1 << length) - 1}].")
            if i < 0:
                raise bitformat.CreationError("uint cannot be initialised with a negative number.")
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
    return BitStore.frombytes(b)


literal_bit_funcs: Dict[str, Callable[..., BitStore]] = {
    '0x': hex2bitstore,
    '0X': hex2bitstore,
    '0b': bin2bitstore,
    '0B': bin2bitstore,
    '0o': oct2bitstore,
    '0O': oct2bitstore,
}


def bitstore_from_token(name: str, token_length: Optional[int], value: Optional[str]) -> BitStore:
    if name in literal_bit_funcs:
        return literal_bit_funcs[name](value)
    try:
        d = bitformat.dtypes.Dtype(name, token_length)
    except ValueError as e:
        raise bitformat.CreationError(f"Can't parse token: {e}")
    if value is None and name != 'pad':
        raise ValueError(f"Token {name} requires a value.")
    bs = d.build(value)._bitstore
    if token_length is not None and len(bs) != d.bitlength:
        raise bitformat.CreationError(f"Token with length {token_length} packed with value of length {len(bs)} "
                                      f"({name}:{token_length}={value}).")
    return bs
