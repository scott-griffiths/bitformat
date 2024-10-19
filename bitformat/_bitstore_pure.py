from __future__ import annotations

import copy
import struct
from typing import Iterable, Iterator


class BitStore:
    """A pure Python implementation of a BitStore. Horribly inefficient but useful for testing."""

    @classmethod
    def _from_bytes_with_offsets(cls, b: bytes | bytearray | memoryview, offset: int = 0, padding: int = 0) -> BitStore:
        assert 0 <= offset <= 7
        assert 0 <= padding <= 7
        padding = None if padding == 0 else -padding
        x = super().__new__(cls)
        binstr = ''.join(format(byte, '08b') for byte in b)
        x.bytearray_ = bytearray(int(b) for b in binstr[offset:padding])
        x.data = bytearray(b)
        x.offset = offset
        x.padding = padding
        return x

    def __new__(cls, ) -> None:
        return cls._from_bytes_with_offsets(b'')

    @classmethod
    def from_zeros(cls, i: int) -> BitStore:
        if i == 0:
            return cls._from_bytes_with_offsets(b'')
        b = b'\x00' * ((i + 7) // 8)
        offset = 8 - (i % 8)
        if offset == 8:
            offset = 0
        return cls._from_bytes_with_offsets(b, offset)

    @classmethod
    def from_ones(cls, i: int) -> BitStore:
        x = super().__new__(cls)
        x.bytearray_ = bytearray([1] * i)
        return x

    @classmethod
    def from_bytes(cls, b: bytes | bytearray | memoryview, /) -> BitStore:
        return cls._from_bytes_with_offsets(b)

    @classmethod
    def from_hex(cls, hexstring: str, /) -> BitStore:
        hexstring = ''.join(hexstring.split())
        odd_length = len(hexstring) % 2
        if odd_length:
            hexstring += '0'
        b = bytes.fromhex(hexstring)
        return cls._from_bytes_with_offsets(b, offset=0, padding=odd_length * 4)

    @classmethod
    def from_oct(cls, octstring: str, /) -> BitStore:
        octstring = ''.join(octstring.split())
        if octstring == '':
            return cls()
        integer_value = int(octstring, 8)
        num_bytes = (len(octstring)*3 + 7) // 8
        b = integer_value.to_bytes(num_bytes, byteorder='big')
        offset = 8 - ((len(octstring) * 3) % 8)
        if offset == 8:
            offset = 0
        return cls._from_bytes_with_offsets(b, offset)

    @classmethod
    def from_bin(cls, binstring: str) -> BitStore:
        binstring = ''.join(binstring.split())
        if binstring == '':
            return cls()
        padding = 8 - (len(binstring) % 8)
        if padding == 8:
            padding = 0
        integer_value = int(binstring, 2) << padding
        num_bytes = (len(binstring) + 7) // 8
        b = integer_value.to_bytes(num_bytes, byteorder='big')
        return cls._from_bytes_with_offsets(b, 0, padding)

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
        b = i.to_bytes((length + 7) // 8, byteorder='big', signed=signed)
        offset = 8 - (length % 8)
        if offset == 8:
            offset = 0
        return cls._from_bytes_with_offsets(b, offset)

    @classmethod
    def from_float(cls, f: float, length: int) -> BitStore:
        fmt = {16: '>e', 32: '>f', 64: '>d'}[length]
        try:
            b = struct.pack(fmt, f)
        except OverflowError:
            # If float64 doesn't fit it automatically goes to 'inf'. This reproduces that behaviour for other types.
            b = struct.pack(fmt, float('inf') if f > 0 else float('-inf'))
        return BitStore._from_bytes_with_offsets(b, 0, 0)

    @classmethod
    def join(cls, iterable: Iterable[BitStore], /) -> BitStore:
        ba = bytearray()
        for i in iterable:
            ba.extend(i.bytearray_)
        bin = ''.join('0' if i == 0 else '1' for i in ba)
        return cls.from_bin(bin)

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

    def to_uint(self, start: int | None = None, end: int | None = None) -> int:
        bitstr = ''.join('0' if i == 0 else '1' for i in self.bytearray_[start:end])
        return int(bitstr, 2)

    def to_int(self, start: int | None = None, end: int | None = None) -> int:
        bitstr = ''.join('0' if i == 0 else '1' for i in self.bytearray_[start:end])
        start, end, _ = slice(start, end).indices(len(self))
        if self.bytearray_[start] == 0:
            return int(bitstr, 2)
        return int(bitstr, 2) - (1 << (end - start))

    def to_hex(self, start: int | None = None, end: int | None = None) -> str:
        bitstr = ''.join('0' if i == 0 else '1' for i in self.bytearray_[start:end])
        if bitstr == '':
            return ''
        start, end, _ = slice(start, end).indices(len(self))
        if len(bitstr) % 4 != 0:
            raise ValueError(f"Cannot convert {bitstr} to hex as it is not a multiple of 4 bits.")
        return hex(int(bitstr, 2))[2:].zfill((end - start + 3) // 4)

    def to_bin(self, start: int | None = None, end: int | None = None) -> str:
        return ''.join('0' if i == 0 else '1' for i in self.bytearray_[start:end])

    def to_oct(self, start: int | None = None, end: int | None = None) -> str:
        bitstr = ''.join('0' if i == 0 else '1' for i in self.bytearray_[start:end])
        if bitstr == '':
            return ''
        start, end, _ = slice(start, end).indices(len(self))
        if len(bitstr) % 3 != 0:
            raise ValueError(f"Cannot convert {bitstr} to oct as it is not a multiple of 3 bits.")
        return oct(int(bitstr, 2))[2:].zfill((end - start + 2) // 3)

    def __eq__(self, other: BitStore, /) -> bool:
        return self.bytearray_ == other.bytearray_

    def __and__(self, other: BitStore, /) -> BitStore:
        x = super().__new__(self.__class__)
        if len(self.bytearray_) != len(other.bytearray_):
            raise ValueError
        x.bytearray_ = bytearray(int(a) & int(b) for a, b in zip(self.bytearray_, other.bytearray_))
        return x

    def __or__(self, other: BitStore, /) -> BitStore:
        x = super().__new__(self.__class__)
        if len(self.bytearray_) != len(other.bytearray_):
            raise ValueError
        x.bytearray_ = bytearray(int(a) | int(b) for a, b in zip(self.bytearray_, other.bytearray_))
        return x

    def __xor__(self, other: BitStore, /) -> BitStore:
        x = super().__new__(self.__class__)
        if len(self.bytearray_) != len(other.bytearray_):
            raise ValueError
        x.bytearray_ = bytearray(int(a) ^ int(b) for a, b in zip(self.bytearray_, other.bytearray_))
        return x

    def find(self, bs: BitStore, bytealigned: bool = False, bytealign_offset: int = 0) -> int:
        to_find = bs.to_bin()
        bitstr = ''.join('0' if i == 0 else '1' for i in self.bytearray_)
        if not bytealigned:
            return bitstr.find(to_find)
        start = 0
        f = bitstr.find(to_find, start)
        while (f + bytealign_offset) % 8 != 0 and f != -1:
            start = f + 1
            f = bitstr.find(to_find, start)
        return f

    def rfind(self, bs: BitStore, bytealigned: bool = False) -> int:
        all_pos = list(self.findall(bs, bytealigned))
        if not all_pos:
            return -1
        return all_pos[-1]

    def findall(self, bs: BitStore, bytealigned: bool = False) -> Iterator[int]:
        # Use self.find() to find all the positions of a BitStore in another BitStore
        f = self.find(bs, bytealigned)
        start = 0
        while f != -1:
            yield f + start
            start += f + 1
            slice_ = self.getslice(start, None)
            bytealign_offset = start % 8
            f = slice_.find(bs, bytealigned, bytealign_offset)

    def count(self, value, /) -> int:
        return self.bytearray_.count(value)

    def reverse(self) -> BitStore:
        x = self.__class__()
        x.bytearray_ = self.bytearray_[::-1]
        return x

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
        x = super().__new__(self.__class__)
        x.bytearray_ = self.bytearray_.__getitem__(key)
        return x

    def getslice(self, start: int | None, stop: int | None, /) -> BitStore:
        x = super().__new__(self.__class__)
        x.bytearray_ = self.bytearray_[start:stop]
        return x

    def invert(self, index: int | None = None, /) -> BitStore:
        x = self.__class__()
        x.bytearray_ = self.bytearray_[:]
        if index is not None:
            x.bytearray_[index] = 1 - x.bytearray_[index]
        else:
            x.bytearray_ = bytearray(1 - b for b in x.bytearray_)
        return x

    def any_set(self) -> bool:
        return 1 in self.bytearray_

    def all_set(self) -> bool:
        return all(self.bytearray_)

    def __len__(self) -> int:
        return len(self.bytearray_)

    def set(self, value: int, pos: int | slice) -> BitStore:
        x = self.copy()
        if isinstance(pos, slice):
            for i in range(*pos.indices(len(self))):
                x.bytearray_[i] = value
        else:
            x.bytearray_[pos] = value
        return x

    def set_from_iterable(self, value: int, pos: Iterable[int]) -> BitStore:
        x = self.copy()
        for p in pos:
            x.bytearray_[p] = value
        return x


class MutableBitStore(BitStore):
    """A mutable version of BitStore with an additional setitem method."""
    def __new__(cls, bs: BitStore | None = None):
        x = super().__new__(cls)
        if bs is not None:
            x.bytearray_ = bs.bytearray_
        return x

    def setitem(self, key: int | slice, value: int | BitStore):
        if isinstance(value, BitStore):
            self.bytearray_.__setitem__(key, value.bytearray_)
        else:
            if isinstance(key, slice):
                for i in range(*key.indices(len(self))):
                    self.bytearray_[i] = value
            else:
                self.bytearray_[key] = value