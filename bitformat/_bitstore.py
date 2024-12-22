from __future__ import annotations

import bitarray
import bitarray.util
import copy
from typing import Sequence, Iterator, Iterable


class BitStore:
    """A light wrapper around bitarray"""

    __slots__ = ("_bitarray", "startbit", "endbit", "mutable")

    @classmethod
    def from_zeros(cls, i: int, mutable: bool = False) -> BitStore:
        x = super().__new__(cls)
        x.mutable = mutable
        x.startbit = 0
        x._bitarray = bitarray.frozenbitarray(i)
        x.endbit = len(x._bitarray)
        return x

    @classmethod
    def from_ones(cls, i: int, mutable: bool = False) -> BitStore:
        x = super().__new__(cls)
        x.mutable = mutable
        x.startbit = 0
        ba = bitarray.bitarray(i)
        ba.setall(True)
        x._bitarray = bitarray.frozenbitarray(ba)
        x.endbit = len(x._bitarray)
        return x

    @classmethod
    def from_bytes(cls, b: bytes | bytearray | memoryview, mutable: bool = False, /) -> BitStore:
        x = super().__new__(cls)
        x.mutable = mutable
        x.startbit = 0
        ba = bitarray.bitarray()
        ba.frombytes(b)
        x._bitarray = bitarray.frozenbitarray(ba)
        x.endbit = len(x._bitarray)
        return x

    @classmethod
    def from_bin(cls, binstring: str, mutable: bool = False, /) -> BitStore:
        x = super().__new__(cls)
        x.mutable = mutable
        x.startbit = 0
        try:
            x._bitarray = bitarray.frozenbitarray(binstring)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid symbol in binary initialiser '{binstring}'")
        x.endbit = len(x._bitarray)
        return x

    @classmethod
    def from_hex(cls, hexstring: str, mutable: bool = False, /) -> BitStore:
        x = super().__new__(cls)
        x.mutable = mutable
        x.startbit = 0
        try:
            x._bitarray = bitarray.frozenbitarray(bitarray.util.hex2ba(hexstring))
        except (TypeError, ValueError):
            raise ValueError(f"Invalid symbol in hex initialiser '{hexstring}'")
        x.endbit = len(x._bitarray)
        return x

    @classmethod
    def from_oct(cls, octstring: str, mutable: bool = False, /) -> BitStore:
        x = super().__new__(cls)
        x.mutable = mutable
        x.startbit = 0
        try:
            x._bitarray = bitarray.frozenbitarray(bitarray.util.base2ba(8, octstring))
        except (TypeError, ValueError):
            raise ValueError(f"Invalid symbol in oct initialiser '{octstring}'.")
        x.endbit = len(x._bitarray)
        return x

    @classmethod
    def from_int(cls, i: int, length: int, signed: bool, mutable: bool = False, /) -> BitStore:
        x = super().__new__(cls)
        x.mutable = mutable
        x.startbit = 0
        x._bitarray = bitarray.frozenbitarray(
            bitarray.util.int2ba(i, length=length, endian="big", signed=signed)
        )
        x.endbit = len(x._bitarray)
        return x

    @classmethod
    def join(cls, seq: Sequence[BitStore], mutable: bool = False, /) -> BitStore:
        x = super().__new__(cls)
        x.mutable = mutable
        ba = bitarray.bitarray()
        x.startbit = 0
        for i in seq:
            ba += i._to_bitarray()
        x._bitarray = bitarray.frozenbitarray(ba)
        x.endbit = len(x._bitarray)
        return x

    def _to_bitarray(self) -> bitarray.frozenbitarray:
        return self._bitarray[self.startbit : self.endbit]

    def to_bytes(self) -> bytes:
        return self._to_bitarray().tobytes()

    def to_uint(self) -> int:
        return bitarray.util.ba2int(self._to_bitarray(), signed=False)

    def to_int(self) -> int:
        return bitarray.util.ba2int(self._to_bitarray(), signed=True)

    def to_hex(self) -> str:
        return bitarray.util.ba2hex(self._to_bitarray())

    def to_bin(self) -> str:
        return self._to_bitarray().to01()

    def to_oct(self) -> str:
        return bitarray.util.ba2base(8, self._to_bitarray())

    def __eq__(self, other: BitStore, /) -> bool:
        return self._to_bitarray() == other._to_bitarray()

    def __and__(self, other: BitStore, /) -> BitStore:
        x = super().__new__(self.__class__)
        x._bitarray = self._to_bitarray() & other._to_bitarray()
        x.startbit = 0
        x.endbit = len(self)
        x.mutable = self.mutable
        return x

    def __or__(self, other: BitStore, /) -> BitStore:
        x = super().__new__(self.__class__)
        x._bitarray = self._to_bitarray() | other._to_bitarray()
        x.startbit = 0
        x.endbit = len(self)
        x.mutable = self.mutable
        return x

    def __xor__(self, other: BitStore, /) -> BitStore:
        x = super().__new__(self.__class__)
        x._bitarray = self._to_bitarray() ^ other._to_bitarray()
        x.startbit = 0
        x.endbit = len(self)
        x.mutable = self.mutable
        return x

    # TODO: Returning -1 is really bad style. Just return None instead.
    def find(self, bs: BitStore, bytealigned: bool) -> int:
        if not bytealigned:
            p = self._bitarray.find(bs._bitarray, self.startbit, self.endbit)
            if p == -1:
                return -1
            return p - self.startbit
        try:
            return next(self.findall(bs, bytealigned))
        except StopIteration:
            return -1

    def rfind(self, bs: BitStore, bytealigned: bool):
        if not bytealigned:
            p = self._bitarray.find(
                bs._bitarray, self.startbit, self.endbit, right=True
            )
            if p == -1:
                return -1
            return p - self.startbit
        try:
            return next(self.rfindall(bs, bytealigned))
        except StopIteration:
            return -1

    def findall(self, bs: BitStore, bytealigned: bool) -> Iterator[int]:
        # TODO: Reinstate this special case. Currently has issues with startbit or endbit.
        # if bytealigned is True and len(bs) % 8 == 0:
        #     # Special case, looking for whole bytes on whole byte boundaries
        #     bytes_ = bs.to_bytes()
        #     # Round up start byte to next byte, and round end byte down.
        #     # We're only looking for whole bytes, so can ignore bits at either end.
        #     start_byte = (self.startbit + 7) // 8
        #     end_byte = self.endbit // 8
        #     b = self._bitarray[start_byte * 8 : end_byte * 8].tobytes()
        #     byte_pos = 0
        #     bytes_to_search = end_byte - start_byte
        #     while byte_pos < bytes_to_search:
        #         byte_pos = b.find(bytes_, byte_pos)
        #         if byte_pos == -1:
        #             break
        #         yield (byte_pos + start_byte) * 8
        #         byte_pos = byte_pos + 1
        #     return
        # General case
        i = self._bitarray.search(bs._bitarray, self.startbit, self.endbit)
        if not bytealigned:
            for p in i:
                yield p - self.startbit
        else:
            for p in i:
                if (p - self.startbit) % 8 == 0:
                    yield p - self.startbit

    def rfindall(self, bs: BitStore, bytealigned: bool) -> Iterator[int]:
        i = self._bitarray.search(bs._bitarray, self.startbit, self.endbit, right=True)
        if not bytealigned:
            for p in i:
                yield p - self.startbit
        else:
            for p in i:
                if (p % 8) == 0:
                    yield p - self.startbit

    def count(self, value, /) -> int:
        return self._to_bitarray().count(value)

    def reverse(self) -> BitStore:
        x = self.__class__()
        ba = bitarray.bitarray(self._to_bitarray())
        ba.reverse()
        x._bitarray = bitarray.frozenbitarray(ba)
        x.startbit = 0
        x.endbit = len(x._bitarray)
        x.mutable = False
        return x

    def __iter__(self) -> Iterable[bool]:
        for i in range(len(self)):
            yield self.getindex(i)

    def __getitem__(self, item: int | slice, /) -> int | BitStore:
        # Use getindex or getslice instead
        raise NotImplementedError

    def getindex(self, index: int, /) -> bool:
        return bool(self._bitarray.__getitem__(index + self.startbit))

    def getslice(self, start: int, stop: int | None, /) -> BitStore:
        assert start >= 0
        assert stop is None or stop >= 0
        x = super().__new__(self.__class__)
        x.mutable = False
        x.startbit = start + self.startbit
        if stop is None:
            stop = len(self)
        x.endbit = stop + self.startbit
        if x.endbit > len(self._bitarray):
            raise ValueError(
                f"Slice out of range. Start: {start}, Stop: {stop}, Length: {len(self)}, Startbit: {self.startbit}, Endbit: {self.endbit}"
            )
        if x.endbit <= x.startbit:
            x.endbit = x.startbit
            x._bitarray = bitarray.frozenbitarray(0)
            return x
        # This is just a view onto the other bitarray, so no copy needed.
        x._bitarray = self._bitarray
        return x

    def invert(self, index: int | None = None, /) -> BitStore:
        x = self.__class__()
        x.mutable = False
        ba = bitarray.bitarray(self._to_bitarray())
        if index is not None:
            ba.invert(index)
        else:
            ba.invert()
        x._bitarray = bitarray.frozenbitarray(ba)
        x.startbit = 0
        x.endbit = len(self)
        return x

    def any_set(self) -> bool:
        return self._to_bitarray().any()

    def all_set(self) -> bool:
        return self._to_bitarray().all()

    def __len__(self) -> int:
        return self.endbit - self.startbit

    def set_index(self, value: int, pos: int) -> BitStore:
        ba = bitarray.bitarray(self._to_bitarray())
        ba[pos] = value
        x = self.__class__()
        x._bitarray = bitarray.frozenbitarray(ba)
        x.startbit = 0
        x.endbit = len(x._bitarray)
        return x

    def set_from_slice(self, value: int, pos: slice) -> BitStore:
        ba = bitarray.bitarray(self._to_bitarray())
        ba.__setitem__(pos, value)
        x = self.__class__()
        x.mutable = False
        x._bitarray = bitarray.frozenbitarray(ba)
        x.startbit = 0
        x.endbit = len(x._bitarray)
        return x

    def set_from_iterable(self, value: bool, pos: Iterable[int]) -> BitStore:
        ba = bitarray.bitarray(self._to_bitarray())
        for p in pos:
            ba.__setitem__(p, value)
        x = self.__class__()
        x.mutable = False
        x._bitarray = bitarray.frozenbitarray(ba)
        x.startbit = 0
        x.endbit = len(x._bitarray)
        return x

    def get_mutable_copy(self) -> BitStore:
        x = self.__class__()
        x.mutable = True
        x.startbit = 0
        ba = copy.copy(self._to_bitarray())
        x._bitarray = bitarray.frozenbitarray(ba)
        x.endbit = len(x._bitarray)
        return x

    def set_mutable_slice(self, startbit: int, endbit:int, value: BitStore, /) -> None:
        if self.mutable is False:
            raise ValueError("Cannot setitem on an immutable BitStore.")
        ba = bitarray.bitarray(self._to_bitarray())
        ba.__setitem__(slice(startbit, endbit, None), value._bitarray)
        self._bitarray = bitarray.frozenbitarray(ba)
        self.startbit = 0
        self.endbit = len(self._bitarray)
