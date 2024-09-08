from __future__ import annotations

import copy
import struct
from typing import Iterable, Iterator


class BitStore:
    """A pure Python implementation of a BitStore. Horribly inefficient but useful for testing."""

    def __init__(self) -> None:
        self.bytearray_ = bytearray()

    @classmethod
    def from_zeros(cls, i: int) -> BitStore:
        x = super().__new__(cls)
        x.bytearray_ = bytearray(i)
        return x

    @classmethod
    def from_ones(cls, i: int) -> BitStore:
        x = super().__new__(cls)
        x.bytearray_ = bytearray([1] * i)
        return x

    @classmethod
    def from_bytes(cls, b: bytes | bytearray | memoryview, /) -> BitStore:
        x = super().__new__(cls)
        binstr = ''.join(format(byte, '08b') for byte in b)
        x.bytearray_ = bytearray(int(b) for b in binstr)
        return x

    @classmethod
    def from_hex(cls, hexstring: str, /) -> BitStore:
        x = super().__new__(cls)
        if hexstring == '':
            x.bytearray_ = bytearray()
        else:
            x.bytearray_ = bytearray(int(b) for b in bin(int(hexstring, 16))[2:].zfill(len(hexstring) * 4))
        return x

    @classmethod
    def from_oct(cls, octstring: str, /) -> BitStore:
        x = super().__new__(cls)
        if octstring == '':
            x.bytearray_ = bytearray()
        else:
            x.bytearray_ = bytearray(int(b) for b in bin(int(octstring, 8))[2:].zfill(len(octstring) * 3))
        return x

    @classmethod
    def from_bin(cls, binstring: str) -> BitStore:
        x = super().__new__(cls)
        if binstring == '':
            x.bytearray_ = bytearray()
        else:
            x.bytearray_ = bytearray(int(b) for b in binstring)
        return x

    @classmethod
    def from_int(cls, i: int, length: int, signed: bool, /) -> BitStore:
        if signed:
            if i >= (1 << (length - 1)) or i < -(1 << (length - 1)):
                raise ValueError(f"{i} is too large a signed integer for a Bits of length {length}. "
                                 f"The allowed range is [{-(1 << (length - 1))}, {(1 << (length - 1)) - 1}].")
        else:
            if i >= (1 << length):
                raise ValueError(f"{i} is too large an unsigned integer for a Bits of length {length}. "
                                 f"The allowed range is [0, {(1 << length) - 1}].")
            if i < 0:
                raise ValueError(f"Unsigned integers cannot be initialised with the negative number {i}.")
        x = super().__new__(cls)
        binstr = bin(i & ((1 << length) - 1))[2:].zfill(length)
        x.bytearray_ = bytearray(int(b) for b in binstr)
        return x

    @classmethod
    def from_float(cls, f: float, length: int) -> BitStore:
        fmt = {16: '>e', 32: '>f', 64: '>d'}[length]
        try:
            b = struct.pack(fmt, f)
        except OverflowError:
            # If float64 doesn't fit it automatically goes to 'inf'. This reproduces that behaviour for other types.
            b = struct.pack(fmt, float('inf') if f > 0 else float('-inf'))
        return BitStore.from_bytes(b)

    @classmethod
    def join(cls, iterable: Iterable[BitStore], /) -> BitStore:
        x = super().__new__(cls)
        x.bytearray_ = bytearray()
        for i in iterable:
            x.bytearray_.extend(i.bytearray_)
        return x

    def to_bytes(self) -> bytes:
        # Ensure the length of the bytearray is a multiple of 8
        ba = self.bytearray_[:]
        if len(ba) % 8 != 0:
            ba.extend([0] * (8 - len(ba) % 8))

        # Convert each group of 8 bits to a byte
        byte_list = [
            sum(bit << (7 - i) for i, bit in enumerate(ba[j:j + 8]))
            for j in range(0, len(ba), 8)
        ]
        return bytes(byte_list)

    def slice_to_uint(self, start: int | None = None, end: int | None = None) -> int:
        bitstr = ''.join('0' if i == 0 else '1' for i in self.bytearray_[start:end])
        return int(bitstr, 2)

    def slice_to_int(self, start: int | None = None, end: int | None = None) -> int:
        bitstr = ''.join('0' if i == 0 else '1' for i in self.bytearray_[start:end])
        start, end, _ = slice(start, end).indices(len(self))
        if self.bytearray_[start] == 0:
            return int(bitstr, 2)
        return int(bitstr, 2) - (1 << (end - start))

    def slice_to_hex(self, start: int | None = None, end: int | None = None) -> str:
        bitstr = ''.join('0' if i == 0 else '1' for i in self.bytearray_[start:end])
        if bitstr == '':
            return ''
        start, end, _ = slice(start, end).indices(len(self))
        return hex(int(bitstr, 2))[2:].zfill((end - start + 3) // 4)

    def slice_to_bin(self, start: int | None = None, end: int | None = None) -> str:
        return ''.join('0' if i == 0 else '1' for i in self.bytearray_[start:end])

    def slice_to_oct(self, start: int | None = None, end: int | None = None) -> str:
        bitstr = ''.join('0' if i == 0 else '1' for i in self.bytearray_[start:end])
        if bitstr == '':
            return ''
        start, end, _ = slice(start, end).indices(len(self))
        return oct(int(bitstr, 2))[2:].zfill((end - start + 2) // 3)

    def __iadd__(self, other: BitStore, /) -> BitStore:
        self.bytearray_.extend(other.bytearray_)
        return self

    def __add__(self, other: BitStore, /) -> BitStore:
        x = BitStore()
        x.bytearray_ = self.bytearray_[:]
        x.bytearray_.extend(other.bytearray_)
        return x

    def __eq__(self, other: BitStore, /) -> bool:
        return self.bytearray_ == other.bytearray_

    def __and__(self, other: BitStore, /) -> BitStore:
        x = BitStore()
        if len(self.bytearray_) != len(other.bytearray_):
            raise ValueError
        x.bytearray_ = bytearray(int(a) & int(b) for a, b in zip(self.bytearray_, other.bytearray_))
        return x

    def __or__(self, other: BitStore, /) -> BitStore:
        x = BitStore()
        if len(self.bytearray_) != len(other.bytearray_):
            raise ValueError
        x.bytearray_ = bytearray(int(a) | int(b) for a, b in zip(self.bytearray_, other.bytearray_))
        return x

    def __xor__(self, other: BitStore, /) -> BitStore:
        x = BitStore()
        if len(self.bytearray_) != len(other.bytearray_):
            raise ValueError
        x.bytearray_ = bytearray(int(a) ^ int(b) for a, b in zip(self.bytearray_, other.bytearray_))
        return x

    def __iand__(self, other: BitStore, /) -> BitStore:
        if len(self.bytearray_) != len(other.bytearray_):
            raise ValueError
        self.bytearray_ = bytearray(int(a) & int(b) for a, b in zip(self.bytearray_, other.bytearray_))
        return self

    def __ior__(self, other: BitStore, /) -> BitStore:
        if len(self.bytearray_) != len(other.bytearray_):
            raise ValueError
        self.bytearray_ = bytearray(int(a) | int(b) for a, b in zip(self.bytearray_, other.bytearray_))
        return self

    def __ixor__(self, other: BitStore, /) -> BitStore:
        if len(self.bytearray_) != len(other.bytearray_):
            raise ValueError
        self.bytearray_ = bytearray(int(a) ^ int(b) for a, b in zip(self.bytearray_, other.bytearray_))
        return self

    def find(self, bs: BitStore, start: int, end: int, bytealigned: bool = False) -> int:
        to_find = bs.slice_to_bin()
        while True:
            bitstr = ''.join('0' if i == 0 else '1' for i in self.bytearray_[start:end])
            f = bitstr.find(to_find)
            if f == -1:
                return -1
            if not bytealigned:
                return f + start
            if ((f + start) % 8) == 0:
                return f + start
            start = f + start + 1

    def rfind(self, bs: BitStore, start: int, end: int, bytealigned: bool = False):
        all_pos = list(self.findall(bs, start, end, bytealigned))
        if not all_pos:
            return -1
        return all_pos[-1]

    def findall(self, bs: BitStore, start: int, end: int, bytealigned: bool = False) -> Iterator[int]:
        # Use self.find() to find all the positions of a BitStore in another BitStore
        f = self.find(bs, start, end, bytealigned)
        while f != -1:
            yield f
            start = f + 1
            f = self.find(bs, start, end, bytealigned)

    def count(self, value, /) -> int:
        return self.bytearray_.count(value)

    def clear(self) -> None:
        self.bytearray_ = bytearray()

    def reverse(self) -> None:
        self.bytearray_ = self.bytearray_[::-1]

    def __iter__(self) -> Iterable[bool]:
        for i in range(len(self)):
            yield self.getindex(i)

    def copy(self) -> BitStore:
        """Always creates a copy, even if instance is immutable."""
        s_copy = self.__class__()
        s_copy.bytearray_ = copy.copy(self.bytearray_)
        return s_copy

    def __getitem__(self, item: int | slice, /) -> int | BitStore:
        # Use getindex or getslice instead
        raise NotImplementedError

    def getindex(self, index: int, /) -> bool:
        return bool(self.bytearray_[index])

    def getslice_withstep(self, key: slice, /) -> BitStore:
        x = BitStore()
        x.bytearray_ = self.bytearray_.__getitem__(key)
        return x

    def getslice(self, start: int | None, stop: int | None, /) -> BitStore:
        x = BitStore()
        x.bytearray_ = self.bytearray_[start:stop]
        return x

    def invert(self, index: int | None = None, /) -> None:
        if index is not None:
            self.bytearray_[index] = 1 - self.bytearray_[index]
        else:
            self.bytearray_ = bytearray(1 - b for b in self.bytearray_)

    def any_set(self) -> bool:
        return 1 in self.bytearray_

    def all_set(self) -> bool:
        return all(self.bytearray_)

    def __len__(self) -> int:
        return len(self.bytearray_)

    def setitem(self, key, value, /):
        if isinstance(value, BitStore):
            self.bytearray_.__setitem__(key, value.bytearray_)
        else:
            if isinstance(key, slice):
                for i in range(*key.indices(len(self))):
                    self.bytearray_[i] = value
            else:
                self.bytearray_[key] = value
