from __future__ import annotations

import bitarray
import bitarray.util
import copy
from typing import Sequence, Iterator


class BitStore:
    """A light wrapper around bitarray"""

    __slots__ = ('_bitarray', 'startbit', 'endbit')

    def __new__(cls):
        x = super().__new__(cls)
        x.startbit = 0
        x.endbit = 0
        x._bitarray = bitarray.frozenbitarray()
        return x

    @classmethod
    def from_zeros(cls, i: int) -> BitStore:
        x = super().__new__(cls)
        x.startbit = 0
        x._bitarray = bitarray.frozenbitarray(i)
        x.endbit = len(x._bitarray)
        return x

    @classmethod
    def from_ones(cls, i: int) -> BitStore:
        x = super().__new__(cls)
        x.startbit = 0
        ba = bitarray.bitarray(i)
        ba.setall(True)
        x._bitarray = bitarray.frozenbitarray(ba)
        x.endbit = len(x._bitarray)
        return x

    @classmethod
    def from_bytes(cls, b: bytes | bytearray | memoryview, /) -> BitStore:
        x = super().__new__(cls)
        x.startbit = 0
        ba = bitarray.bitarray()
        ba.frombytes(b)
        x._bitarray = bitarray.frozenbitarray(ba)
        x.endbit = len(x._bitarray)
        return x

    @classmethod
    def from_bin(cls, binstring: str, /) -> BitStore:
        x = super().__new__(cls)
        x.startbit = 0
        try:
            x._bitarray = bitarray.frozenbitarray(binstring)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid symbol in binary initialiser '{binstring}'")
        x.endbit = len(x._bitarray)
        return x

    @classmethod
    def from_hex(cls, hexstring: str, /) -> BitStore:
        x = super().__new__(cls)
        x.startbit = 0
        try:
            x._bitarray = bitarray.frozenbitarray(bitarray.util.hex2ba(hexstring))
        except (TypeError, ValueError):
            raise ValueError(f"Invalid symbol in hex initialiser '{hexstring}'")
        x.endbit = len(x._bitarray)
        return x

    @classmethod
    def from_oct(cls, octstring: str, /) -> BitStore:
        x = super().__new__(cls)
        x.startbit = 0
        try:
            x._bitarray = bitarray.frozenbitarray(bitarray.util.base2ba(8, octstring))
        except (TypeError, ValueError):
            raise ValueError(f"Invalid symbol in oct initialiser '{octstring}'.")
        x.endbit = len(x._bitarray)
        return x

    @classmethod
    def from_int(cls, i: int, length: int, signed: bool, /) -> BitStore:
        x = super().__new__(cls)
        x.startbit = 0
        x._bitarray = bitarray.frozenbitarray(bitarray.util.int2ba(i, length=length, endian='big', signed=signed))
        x.endbit = len(x._bitarray)
        return x

    @classmethod
    def join(cls, iterable: Sequence[BitStore], /) -> BitStore:
        x = super().__new__(cls)
        ba = bitarray.bitarray()
        x.startbit = 0
        for i in iterable:
            ba += i._bitarray[i.startbit:i.endbit]
        x._bitarray = bitarray.frozenbitarray(ba)
        x.endbit = len(x._bitarray)
        return x

    def to_bytes(self) -> bytes:
        return self._bitarray[self.startbit:self.endbit].tobytes()

    def to_uint(self) -> int:
        return bitarray.util.ba2int(self._bitarray[self.startbit:self.endbit], signed=False)

    def to_int(self) -> int:
        return bitarray.util.ba2int(self._bitarray[self.startbit:self.endbit], signed=True)

    def to_hex(self) -> str:
        return bitarray.util.ba2hex(self._bitarray[self.startbit:self.endbit])

    def to_bin(self) -> str:
        return self._bitarray[self.startbit:self.endbit].to01()

    def to_oct(self) -> str:
        return bitarray.util.ba2base(8, self._bitarray[self.startbit:self.endbit])

    def __eq__(self, other: BitStore, /) -> bool:
        return self._bitarray[self.startbit:self.endbit] == other._bitarray[other.startbit:other.endbit]

    def __and__(self, other: BitStore, /) -> BitStore:
        x = super().__new__(self.__class__)
        x._bitarray = self._bitarray[self.startbit:self.endbit] & other._bitarray[other.startbit:other.endbit]
        x.startbit = 0
        x.endbit = len(x._bitarray)
        return x

    def __or__(self, other: BitStore, /) -> BitStore:
        x = super().__new__(self.__class__)
        x._bitarray = self._bitarray[self.startbit:self.endbit] | other._bitarray[other.startbit:other.endbit]
        x.startbit = 0
        x.endbit = len(x._bitarray)
        return x

    def __xor__(self, other: BitStore, /) -> BitStore:
        x = super().__new__(self.__class__)
        x._bitarray = self._bitarray[self.startbit:self.endbit] ^ other._bitarray[other.startbit:other.endbit]
        x.startbit = 0
        x.endbit = len(x._bitarray)
        return x

    def find(self, bs: BitStore, bytealigned: bool) -> int:
        if not bytealigned:
            return self._bitarray.find(bs._bitarray, self.startbit, self.endbit)
        try:
            return next(self.findall(bs, bytealigned))
        except StopIteration:
            return -1

    def rfind(self, bs: BitStore, bytealigned: bool):
        if not bytealigned:
            return self._bitarray.find(bs._bitarray, self.startbit, self.endbit, right=True)
        try:
            return next(self.rfindall(bs, bytealigned))
        except StopIteration:
            return -1

    def findall(self, bs: BitStore, bytealigned: bool) -> Iterator[int]:
        if bytealigned is True and len(bs) % 8 == 0:
            # Special case, looking for whole bytes on whole byte boundaries
            bytes_ = bs.to_bytes()
            # Round up start byte to next byte, and round end byte down.
            # We're only looking for whole bytes, so can ignore bits at either end.
            start_byte = (self.startbit + 7) // 8
            end_byte = self.endbit // 8
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
        i = self._bitarray.itersearch(bs._bitarray, self.startbit, self.endbit)
        if not bytealigned:
            for p in i:
                yield p
        else:
            for p in i:
                if (p % 8) == 0:
                    yield p

    def rfindall(self, bs: BitStore, bytealigned: bool) -> Iterator[int]:
        i = self._bitarray.itersearch(bs._bitarray, self.startbit, self.endbit, right=True)
        if not bytealigned:
            for p in i:
                yield p
        else:
            for p in i:
                if (p % 8) == 0:
                    yield p

    def count(self, value, /) -> int:
        return self._bitarray[self.startbit:self.endbit].count(value)

    def reverse(self) -> BitStore:
        x = self.__class__()
        ba = bitarray.bitarray(self._bitarray[self.startbit:self.endbit])
        ba.reverse()
        x._bitarray = bitarray.frozenbitarray(ba)
        x.startbit = 0
        x.endbit = len(x._bitarray)
        return x

    def __iter__(self) -> Iterable[bool]:
        for i in range(len(self)):
            yield self.getindex(i)

    def __getitem__(self, item: int | slice, /) -> int | BitStore:
        # Use getindex or getslice instead
        raise NotImplementedError

    def getindex(self, index: int, /) -> bool:
        return bool(self._bitarray.__getitem__(index + self.startbit))

    def getslice_withstep(self, key: slice, /) -> BitStore:
        x = super().__new__(self.__class__)
        x.startbit = 0
        start = key.start + self.startbit if key.start is not None else self.startbit
        stop = key.stop + self.startbit if key.stop is not None else self.endbit
        key = slice(start, stop, key.step)
        x._bitarray = self._bitarray.__getitem__(key)
        x.endbit = len(x._bitarray)
        return x

    def getslice(self, start: int | None, stop: int | None, /) -> BitStore:
        x = super().__new__(self.__class__)
        if start is None:
            x.startbit = self.startbit
        else:
            if start < 0:
                start = len(self) + start
            x.startbit = start + self.startbit
        if stop is None:
            x.endbit = self.endbit
        else:
            if stop < 0:
                stop = len(self) + stop
            x.endbit = stop + self.startbit
        if x.endbit > len(self._bitarray):
            raise ValueError(f"Slice out of range. Start: {start}, Stop: {stop}, Length: {len(self)}, Startbit: {self.startbit}, Endbit: {self.endbit}")
        # This is just a view onto the other bitarray, so no copy needed.
        x._bitarray = self._bitarray
        return x

    def invert(self, index: int | None = None, /) -> BitStore:
        x = self.__class__()
        ba = bitarray.bitarray(self._bitarray[self.startbit:self.endbit])
        if index is not None:
            ba.invert(index)
        else:
            ba.invert()
        x._bitarray = bitarray.frozenbitarray(ba)
        x.startbit = 0
        x.endbit = len(x._bitarray)
        return x

    def any_set(self) -> bool:
        return self._bitarray[self.startbit:self.endbit].any()

    def all_set(self) -> bool:
        return self._bitarray[self.startbit:self.endbit].all()

    def __len__(self) -> int:
        return self.endbit - self.startbit

    def set(self, value: int, pos: int | slice) -> BitStore:
        ba = bitarray.bitarray(self._bitarray[self.startbit:self.endbit])
        ba.__setitem__(pos, value)
        x = self.__class__()
        x._bitarray = bitarray.frozenbitarray(ba)
        x.startbit = 0
        x.endbit = len(x._bitarray)
        return x

    def set_from_iterable(self, value: int, pos: Iterable[int]) -> BitStore:
        ba = bitarray.bitarray(self._bitarray[self.startbit:self.endbit])
        for p in pos:
            ba.__setitem__(p, value)
        x = self.__class__()
        x._bitarray = bitarray.frozenbitarray(ba)
        x.startbit = 0
        x.endbit = len(x._bitarray)
        return x


class MutableBitStore(BitStore):
    """A mutable version of BitStore with an additional setitem method.

    This is used in the Array class to allow it to be changed after creation.
    """
    def __new__(cls, bs: BitStore | None = None):
        x = super().__new__(cls)
        x.startbit = 0
        if bs is not None:
            ba = copy.copy(bs._bitarray[bs.startbit:bs.endbit])
            x._bitarray = bitarray.frozenbitarray(ba)
        else:
            x._bitarray = bitarray.frozenbitarray()
        x.endbit = len(x._bitarray)
        return x

    def setitem(self, key: int | slice, value: int | BitStore, /):
        ba = bitarray.bitarray(self._bitarray[self.startbit:self.endbit])
        if isinstance(value, BitStore):
            ba.__setitem__(key, value._bitarray)
        else:
            ba.__setitem__(key, value)
        self._bitarray = bitarray.frozenbitarray(ba)
        self.startbit = 0
        self.endbit = len(self._bitarray)

    def copy(self) -> BitStore:
        s_copy = self.__class__()
        s_copy._bitarray = copy.copy(self._bitarray[self.startbit:self.endbit])
        s_copy.startbit = 0
        s_copy.endbit = len(s_copy._bitarray)
        return s_copy
