
from bit_rust import BitRust as BitStore
import struct

# These can all be converted to pure Rust later if we feel like it

def from_int(cls, i: int, length: int, signed: bool, /) -> BitStore:
    if signed:
        if i >= (1 << (length - 1)) or i < -(1 << (length - 1)):
            raise ValueError(
                f"{i} is too large a signed integer for a Bits of length {length}. "
                f"The allowed range is [{-(1 << (length - 1))}, {(1 << (length - 1)) - 1}]."
            )
    else:
        if i >= (1 << length):
            raise ValueError(
                f"{i} is too large an unsigned integer for a Bits of length {length}. "
                f"The allowed range is [0, {(1 << length) - 1}]."
            )
        if i < 0:
            raise ValueError(
                f"Unsigned integers cannot be initialised with the negative number {i}."
            )
    b = i.to_bytes((length + 7) // 8, byteorder="big", signed=signed)
    offset = 8 - (length % 8)
    if offset == 8:
        offset = 0
    return cls.from_bytes_with_offset(b, offset=offset)

def from_float(cls, f: float, length: int) -> BitStore:
    fmt = {16: ">e", 32: ">f", 64: ">d"}[length]
    try:
        b = struct.pack(fmt, f)
    except OverflowError:
        # If float64 doesn't fit it automatically goes to 'inf'. This reproduces that behaviour for other types.
        b = struct.pack(fmt, float("inf") if f > 0 else float("-inf"))
    return BitStore.from_bytes(b)

def to_uint(self) -> int:
    b, offset = self.to_byte_data_with_offset()
    x = int.from_bytes(b, byteorder="big")
    padding = 8 - ((offset + len(self)) % 8)
    if padding != 8:
        x >>= padding
    return x

def to_int(self) -> int:
    b, offset = self.to_byte_data_with_offset()
    x = int.from_bytes(b, byteorder="big", signed=True)
    padding = 8 - ((offset + len(self)) % 8)
    if padding != 8:
        x >>= padding
    return x


BitStore.from_int = classmethod(from_int)
BitStore.from_float = classmethod(from_float)
BitStore.to_uint = to_uint
BitStore.to_int = to_int