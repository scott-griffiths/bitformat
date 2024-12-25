
from bit_rust import BitRust as BitStore
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

def to_uint(self) -> int:
    return int.from_bytes(self.to_int_byte_data(False), byteorder="big", signed=False)

def to_int(self) -> int:
    return int.from_bytes(self.to_int_byte_data(True), byteorder="big", signed=True)

def findall(self, bs: BitStore, bytealigned: bool) -> Iterator[int]:
    p_list = self.findall_list(bs, bytealigned)
    for p in p_list:
        yield p

def set_from_slice(self, value: bool, start: int, stop: int, step: int) -> BitStore:
    return self.set_from_sequence(value, list(range(start, stop, step)));

def __iter__(self) -> Iterator[bool]:
    for i in range(len(self)):
        yield self.getindex(i)


BitStore.from_int = classmethod(from_int)
BitStore.to_uint = to_uint
BitStore.to_int = to_int
BitStore.findall = findall
BitStore.set_from_slice = set_from_slice
BitStore.__iter__ = __iter__