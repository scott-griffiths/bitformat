
from bit_rust import BitRust as BitStore
from typing import Iterator, Iterable

# These can all be converted to pure Rust later if we feel like it


def findall(self, bs: BitStore, bytealigned: bool) -> Iterator[int]:
    p_list = self.findall_list(bs, bytealigned)
    for p in p_list:
        yield p

def set_from_slice(self, value: bool, start: int, stop: int, step: int) -> BitStore:
    return self.set_from_sequence(value, list(range(start, stop, step)));

def __iter__(self) -> Iterator[bool]:
    for i in range(len(self)):
        yield self.getindex(i)

BitStore.findall = findall
BitStore.set_from_slice = set_from_slice
BitStore.__iter__ = __iter__