
from bit_rust import BitRust as BitStore
import struct
from typing import Iterator, Iterable

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

def findall(self, bs: BitStore, bytealigned: bool) -> Iterator[int]:
    # TODO: bytealign_offset - see _bitstore_pure.py
    f = self.find(bs, bytealigned)
    start = 0
    while f is not None:
        yield f + start
        start += f + 1
        slice_ = self.getslice(start, None)
        f = slice_.find(bs, bytealigned)

def count(self, value: bool) -> int:
    if value:
        return self.count_ones()
    return self.count_zeros()

def set_from_iterable(self, value: bool, pos: Iterable[int]) -> BitStore:
    new_bitstore = self
    for p in pos:
        new_bitstore = new_bitstore.set_index(value, p)
    return new_bitstore

def set_from_slice(self, value: bool, s: slice) -> BitStore:
    return self.set_from_iterable(value, list(range(s.start or 0, s.stop, s.step or 1)));

def set_mutable_slice(self, start: int, end: int, value: BitStore) -> None:
    start = self.getslice(0, start)
    middle = value
    end = self.getslice(end, None)
    self = BitStore.join([start, middle, end])

BitStore.from_int = classmethod(from_int)
BitStore.from_float = classmethod(from_float)
BitStore.to_uint = to_uint
BitStore.to_int = to_int
BitStore.findall = findall
BitStore.count = count
BitStore.set_from_iterable = set_from_iterable
BitStore.set_from_slice = set_from_slice
BitStore.set_mutable_slice = set_mutable_slice