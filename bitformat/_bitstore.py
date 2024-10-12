from __future__ import annotations

import bitarray
import bitarray.util
import copy
from typing import Iterable, Iterator


class BitStore:
    """A light wrapper around bitarray"""

    __slots__ = ('_bitarray', 'bitoffset')

    def __new__(cls):
        x = super().__new__(cls)
        x.bitoffset = 0
        x._bitarray = bitarray.frozenbitarray()
        return x

    @classmethod
    def from_zeros(cls, i: int) -> BitStore:
        x = super().__new__(cls)
        x.bitoffset = 0
        x._bitarray = bitarray.frozenbitarray(i)
        return x

    @classmethod
    def from_ones(cls, i: int) -> BitStore:
        x = super().__new__(cls)
        x.bitoffset = 0
        ba = bitarray.bitarray(i)
        ba.setall(True)
        x._bitarray = bitarray.frozenbitarray(ba)
        return x

    @classmethod
    def from_bytes(cls, b: bytes | bytearray | memoryview, /) -> BitStore:
        x = super().__new__(cls)
        x.bitoffset = 0
        ba = bitarray.bitarray()
        ba.frombytes(b)
        x._bitarray = bitarray.frozenbitarray(ba)
        return x

    @classmethod
    def from_bin(cls, binstring: str, /) -> BitStore:
        x = super().__new__(cls)
        x.bitoffset = 0
        try:
            x._bitarray = bitarray.frozenbitarray(binstring)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid symbol in binary initialiser '{binstring}'")
        return x

    @classmethod
    def from_hex(cls, hexstring: str, /) -> BitStore:
        x = super().__new__(cls)
        x.bitoffset = 0
        try:
            x._bitarray = bitarray.frozenbitarray(bitarray.util.hex2ba(hexstring))
        except (TypeError, ValueError):
            raise ValueError(f"Invalid symbol in hex initialiser '{hexstring}'")
        return x

    @classmethod
    def from_oct(cls, octstring: str, /) -> BitStore:
        x = super().__new__(cls)
        x.bitoffset = 0
        try:
            x._bitarray = bitarray.frozenbitarray(bitarray.util.base2ba(8, octstring))
        except (TypeError, ValueError):
            raise ValueError(f"Invalid symbol in oct initialiser '{octstring}'.")
        return x

    @classmethod
    def from_int(cls, i: int, length: int, signed: bool, /) -> BitStore:
        x = super().__new__(cls)
        x.bitoffset = 0
        x._bitarray = bitarray.frozenbitarray(bitarray.util.int2ba(i, length=length, endian='big', signed=signed))
        return x

    @classmethod
    def join(cls, iterable: Iterable[BitStore], /) -> BitStore:
        x = super().__new__(cls)
        ba = bitarray.bitarray()
        x.bitoffset = 0
        for i in iterable:
            if i.bitoffset == 0:
                ba += i._bitarray
            else:
                ba += i._bitarray[i.bitoffset:]
        x._bitarray = bitarray.frozenbitarray(ba)
        return x

    def to_bytes(self) -> bytes:
        return self._bitarray.tobytes()

    def slice_to_uint(self, start: int | None = None, end: int | None = None) -> int:
        return bitarray.util.ba2int(self._bitarray[start:end], signed=False)

    def slice_to_int(self, start: int | None = None, end: int | None = None) -> int:
        return bitarray.util.ba2int(self._bitarray[start:end], signed=True)

    def slice_to_hex(self, start: int | None = None, end: int | None = None) -> str:
        return bitarray.util.ba2hex(self._bitarray[start:end])

    def slice_to_bin(self, start: int | None = None, end: int | None = None) -> str:
        return self._bitarray[start:end].to01()

    def slice_to_oct(self, start: int | None = None, end: int | None = None) -> str:
        return bitarray.util.ba2base(8, self._bitarray[start:end])

    def __eq__(self, other: BitStore, /) -> bool:
        return self._bitarray == other._bitarray

    def __and__(self, other: BitStore, /) -> BitStore:
        x = super().__new__(self.__class__)
        x._bitarray = self._bitarray & other._bitarray
        return x

    def __or__(self, other: BitStore, /) -> BitStore:
        x = super().__new__(self.__class__)
        x._bitarray = self._bitarray | other._bitarray
        return x

    def __xor__(self, other: BitStore, /) -> BitStore:
        x = super().__new__(self.__class__)
        x._bitarray = self._bitarray ^ other._bitarray
        return x

    def find(self, bs: BitStore, start: int, end: int, bytealigned: bool) -> int:
        if not bytealigned:
            return self._bitarray.find(bs._bitarray, start, end)
        try:
            return next(self.findall(bs, start, end, bytealigned))
        except StopIteration:
            return -1

    def rfind(self, bs: BitStore, start: int, end: int, bytealigned: bool):
        if not bytealigned:
            return self._bitarray.find(bs._bitarray, start, end, right=True)
        try:
            return next(self.rfindall(bs, start, end, bytealigned))
        except StopIteration:
            return -1

    def findall(self, bs: BitStore, start: int, end: int, bytealigned: bool) -> Iterator[int]:
        if bytealigned is True and len(bs) % 8 == 0:
            # Special case, looking for whole bytes on whole byte boundaries
            bytes_ = bs.to_bytes()
            # Round up start byte to next byte, and round end byte down.
            # We're only looking for whole bytes, so can ignore bits at either end.
            start_byte = (start + 7) // 8
            end_byte = end // 8
            b = self._bitarray[start_byte * 8: end_byte * 8].tobytes()
            byte_pos = 0
            bytes_to_search = end_byte - start_byte
            while byte_pos < bytes_to_search:
                byte_pos = b.find(bytes_, byte_pos)
                if byte_pos == -1:
                    break
                yield (byte_pos + start_byte) * 8
                byte_pos = byte_pos + 1
            return
        # General case
        i = self._bitarray.itersearch(bs._bitarray, start, end)
        if not bytealigned:
            for p in i:
                yield p
        else:
            for p in i:
                if (p % 8) == 0:
                    yield p

    def rfindall(self, bs: BitStore, start: int, end: int, bytealigned: bool) -> Iterator[int]:
        i = self._bitarray.itersearch(bs._bitarray, start, end, right=True)
        if not bytealigned:
            for p in i:
                yield p
        else:
            for p in i:
                if (p % 8) == 0:
                    yield p

    def count(self, value, /) -> int:
        return self._bitarray.count(value)

    def reverse(self) -> BitStore:
        x = self.__class__()
        ba = bitarray.bitarray(self._bitarray)
        ba.reverse()
        x._bitarray = bitarray.frozenbitarray(ba)
        return x

    def __iter__(self) -> Iterable[bool]:
        for i in range(len(self)):
            yield self.getindex(i)

    def copy(self) -> BitStore:
        """Always creates a copy, even if instance is immutable."""
        s_copy = self.__class__()
        s_copy._bitarray = copy.copy(self._bitarray)
        return s_copy

    def __getitem__(self, item: int | slice, /) -> int | BitStore:
        # Use getindex or getslice instead
        raise NotImplementedError

    def getindex(self, index: int, /) -> bool:
        return bool(self._bitarray.__getitem__(index))

    def getslice_withstep(self, key: slice, /) -> BitStore:
        x = super().__new__(self.__class__)
        x.bitoffset = 0
        x._bitarray = self._bitarray.__getitem__(key)
        return x

    def getslice(self, start: int | None, stop: int | None, /) -> BitStore:
        x = super().__new__(self.__class__)
        x.bitoffset = 0
        x._bitarray = self._bitarray[start:stop]
        return x

    def invert(self, index: int | None = None, /) -> BitStore:
        x = self.__class__()
        ba = bitarray.bitarray(self._bitarray)
        if index is not None:
            ba.invert(index)
        else:
            ba.invert()
        x._bitarray = bitarray.frozenbitarray(ba)
        return x

    def any_set(self) -> bool:
        return self._bitarray.any()

    def all_set(self) -> bool:
        return self._bitarray.all()

    def __len__(self) -> int:
        return len(self._bitarray)

    def set(self, value: int, pos: int | slice) -> BitStore:
        x = self.copy()
        ba = bitarray.bitarray(x._bitarray)
        ba.__setitem__(pos, value)
        x._bitarray = bitarray.frozenbitarray(ba)
        return x

    def set_from_iterable(self, value: int, pos: Iterable[int]) -> BitStore:
        x = self.copy()
        ba = bitarray.bitarray(x._bitarray)
        for p in pos:
            ba.__setitem__(p, value)
        x._bitarray = bitarray.frozenbitarray(ba)
        return x


class MutableBitStore(BitStore):
    """A mutable version of BitStore with an additional setitem method.

    This is used in the Array class to allow it to be changed after creation.
    """
    def __new__(cls, bs: BitStore | None = None):
        x = super().__new__(cls)
        x.bitoffset = 0
        if bs is not None:
            x._bitarray = bs._bitarray
        return x

    def setitem(self, key: int | slice, value: int | BitStore, /):
        ba = bitarray.bitarray(self._bitarray)
        if isinstance(value, BitStore):
            ba.__setitem__(key, value._bitarray)
        else:
            ba.__setitem__(key, value)
        self._bitarray = bitarray.frozenbitarray(ba)


