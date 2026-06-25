from __future__ import annotations

from typing import Literal
from bitformat._common import DtypeKind
from ._dtypes import DtypeDefinition, AllowedSizes
from ._tibs import Tibs, TibsLike, tibs_from_any, tibs_to_padded_bytes


# The definitions for each of the data types.
# Some of these definitions use a method to convert a bit length to the number of characters needed to print it.

# ----- Integer types -----

def to_u(bs: Tibs, start: int, length: int) -> int:
    """Return data as an unsigned int from a slice of the bits."""
    if length == 0:
        raise ValueError("Cannot interpret empty Tibs as an integer.")
    bits = tibs_from_any(bs)[start:start + length]
    if length <= 128:
        return bits.to_u()
    padding = -length % 8
    return int.from_bytes(tibs_to_padded_bytes(bits), "big") >> padding

def from_u(u: int, length: int) -> Tibs:
    if length == 0:
        raise ValueError("A non-zero length must be specified with a 'u' initialiser.")
    u = int(u)
    if u < 0:
        raise ValueError(f"Unsigned integers cannot be initialised with the negative number {u}.")
    if u >= (1 << length):
        raise ValueError(f"{u} is too large an unsigned integer for a bit length of {length}. "
                         f"The allowed range is[0, {(1 << length) - 1}].")
    if length <= 128:
        return Tibs.from_u(u, length=length)
    byte_length = (length + 7) // 8
    offset = byte_length * 8 - length
    return Tibs.from_bytes(u.to_bytes(byte_length, "big"), offset=offset, length=length)

def u_bits2chars(bit_length: int) -> int:
    # How many characters is largest possible int of this length?
    return len(str((1 << bit_length) - 1))


u_defn = DtypeDefinition(DtypeKind.UINT,
                         "a two's complement unsigned int",
                         "unsigned int",
                         AllowedSizes(1, None),
                         from_u,
                         to_u,
                         int,
                         False,
                         u_bits2chars,
                         endianness_variants=True)


def to_i(bs: Tibs, start: int, length: int) -> int:
    """Return data as a signed int from a slice of the bits."""
    if length == 0:
        raise ValueError("Cannot interpret empty Tibs as an integer.")
    bits = tibs_from_any(bs)[start:start + length]
    if length <= 128:
        return bits.to_i()
    u = to_u(bits, 0, length)
    return u - (1 << length) if bits[0] else u

def from_i(i: int, length: int) -> Tibs:
    if length == 0:
        raise ValueError("A non-zero length must be specified with an 'i' initialiser.")
    i = int(i)
    if i >= (1 << (length - 1)) or i < -(1 << (length - 1)):
        raise ValueError(f"{i} is too large a signed integer for a bit length of {length}. "
                         f"The allowed range is[{-(1 << (length - 1))}, {(1 << (length - 1)) - 1}")
    if length <= 128:
        return Tibs.from_i(i, length=length)
    u = (1 << length) + i if i < 0 else i
    return from_u(u, length)

def i_bits2chars(bit_length: int) -> int:
    # How many characters is largest negative int of this length? (To include minus sign).
    return len(str((-1 << (bit_length - 1))))


i_defn = DtypeDefinition(DtypeKind.INT,
                         "a two's complement signed int",
                         "signed int",
                         AllowedSizes(1, None),
                         from_i,
                         to_i,
                         int,
                         True,
                         i_bits2chars,
                         endianness_variants=True)


# ----- Literal types -----

def to_bin(bs: Tibs, start: int, length: int) -> str:
    """Return interpretation as a binary string."""
    return tibs_from_any(bs)[start:start + length].to_bin()

def from_bin(binstring: str, length: None = None) -> Tibs:
    """Create from the value given in binstring."""
    return Tibs.from_bin(binstring)

def to_oct(bs: Tibs, start: int, length: int) -> str:
    """Return interpretation as an octal string."""
    return tibs_from_any(bs)[start:start + length].to_oct()

def from_oct(octstring: str, length: None = None) -> Tibs:
    """Create from the value given in octstring."""
    return Tibs.from_oct(octstring)

def to_hex(bs: Tibs, start: int, length: int) -> str:
    """Return interpretation as a hexadecimal string."""
    return tibs_from_any(bs)[start:start + length].to_hex()

def from_hex(hexstring: str, length: None = None) -> Tibs:
    """Create from the value given in hexstring."""
    return Tibs.from_hex(hexstring)

def to_bytes(bs: Tibs, start: int, length: int) -> bytes:
    """Return interpretation as bytes."""
    return tibs_from_any(bs)[start:start + length].to_bytes()

def from_bytes(data: bytearray | bytes | list, length: None = None) -> Tibs:
    """Create from a bytes or bytearray object."""
    return Tibs.from_bytes(bytes(data))


def bin_bits2chars(bit_length: int) -> int:
    return bit_length

def oct_bits2chars(bit_length: int) -> int:
    return (bit_length + 2) // 3

def hex_bits2chars(bit_length: int) -> int:
    return (bit_length + 3) // 4

def bytes_bits2chars(bit_length: int) -> int:
    return (bit_length + 7) // 8


bin_defn = DtypeDefinition(DtypeKind.BIN,
                           "a binary string",
                           "binary string",
                           AllowedSizes(0, None),
                           from_bin,
                           to_bin,
                           str,
                           False,
                           bin_bits2chars)
oct_defn = DtypeDefinition(DtypeKind.OCT,
                           "an octal string",
                           "octal string",
                           AllowedSizes(0, None),
                           from_oct,
                           to_oct,
                           str,
                           False,
                           oct_bits2chars)
hex_defn = DtypeDefinition(DtypeKind.HEX,
                           "a hexadecimal string",
                           "hex string",
                           AllowedSizes(0, None),
                           from_hex,
                           to_hex,
                           str,
                           False,
                           hex_bits2chars)
bytes_defn = DtypeDefinition(DtypeKind.BYTES,
                             "a bytes object",
                             "bytes",
                             AllowedSizes(0, None),
                             from_bytes,
                             to_bytes,
                             bytes,
                             False,
                             bytes_bits2chars)


# ----- Float types -----

def to_f(bs: Tibs, start: int, length: int) -> float:
    """Interpret as a big-endian float."""
    return tibs_from_any(bs)[start:start + length].to_f()

def from_f(f: float | str, length: int | None) -> Tibs:
    if length is None:
        raise ValueError("No length can be inferred for the float initialiser.")
    return Tibs.from_f(float(f), length=length)

def f_bits2chars(bit_length: Literal[16, 32, 64]) -> int:
    # These bit lengths were found by looking at lots of possible values
    if bit_length in [16, 32]:
        return 23  # Empirical value
    else:
        return 24  # Empirical value


f_defn = DtypeDefinition(DtypeKind.FLOAT,
                         "an IEEE floating point number",
                         "float",
                         AllowedSizes(sizes=(16, 32, 64)),
                         from_f,
                         to_f,
                         float,
                         True,
                         f_bits2chars,
                         endianness_variants=True)


# ----- Other known length types -----

def to_tibs(bs: Tibs, start: int, length: int) -> Tibs:
    """Just return as a Tibs."""
    return tibs_from_any(bs)[start:start + length]

def from_tibs(bs: TibsLike, length: None = None) -> Tibs:
    return tibs_from_any(bs)

def bits_bits2chars(bit_length: int) -> int:
    # For bits type we can see how long it needs to be printed by trying any value
    temp = Tibs.from_zeros(bit_length)
    return len(str(temp))


bits_defn = DtypeDefinition(DtypeKind.BITS,
                            "a Tibs object",
                            "Tibs",
                            AllowedSizes(0, None),
                            from_tibs,
                            to_tibs,
                            Tibs,
                            False,
                            bits_bits2chars)


def to_bool(bs: Tibs, start: int, _length: int) -> bool:
    """Interpret as a bool"""
    assert _length == 1
    return bs[start]

def from_bool(value: bool, length: None = None) -> Tibs:
    return Tibs.from_bools([value])

def bool_bits2chars(_: Literal[1]) -> int:
    # Bools are printed as 1 or 0, not True or False, so are one character each
    return 1


bool_defn = DtypeDefinition(DtypeKind.BOOL,
                            "a bool (True or False)",
                            "bool",
                            AllowedSizes(sizes=(1,)),
                            from_bool,
                            to_bool,
                            bool,
                            False,
                            bool_bits2chars)


# ----- Special case pad type -----

def to_pad(_bs: Tibs, _start: int, _length: int) -> None:
    return None

def from_pad(value: None, length: int) -> None:
    raise ValueError("It's not possible to set a 'pad' value.")

pad_defn = DtypeDefinition(DtypeKind.PAD,
                           "a skipped section of padding",
                           "padding",
                           AllowedSizes(0, None),
                           from_pad,
                           to_pad,
                           None,
                           False,
                           None)

# ----------


dtype_definitions = [
    u_defn,
    i_defn,

    bin_defn,
    oct_defn,
    hex_defn,
    bytes_defn,

    f_defn,

    bits_defn,
    bool_defn,

    pad_defn,
]
