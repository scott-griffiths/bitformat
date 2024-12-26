
from bit_rust import BitRust
from typing import Iterator

# These can all be converted to pure Rust later if we feel like it

def findall(self, bs: BitRust, bytealigned: bool) -> Iterator[int]:
    p_list = self.findall_list(bs, bytealigned)
    for p in p_list:
        yield p

def __iter__(self) -> Iterator[bool]:
    for i in range(len(self)):
        yield self.getindex(i)

BitRust.findall = findall
BitRust.__iter__ = __iter__