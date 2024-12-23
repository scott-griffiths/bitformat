
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
    return int(self.to_bin(), 2)

def to_int(self) -> int:
    bin_str = self.to_bin()
    i = int(bin_str, 2)
    if bin_str[0] == "1":
        i -= 1 << len(self)
    return i

def findall(self, bs: BitStore, bytealigned: bool) -> Iterator[int]:
    p_list = self.findall_list(bs, bytealigned)
    for p in p_list:
        yield p

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

def __iter__(self) -> Iterator[bool]:
    for i in range(len(self)):
        yield self.getindex(i)


BitStore.from_int = classmethod(from_int)
BitStore.to_uint = to_uint
BitStore.to_int = to_int
BitStore.findall = findall
BitStore.count = count
BitStore.set_from_iterable = set_from_iterable
BitStore.set_from_slice = set_from_slice
BitStore.__iter__ = __iter__