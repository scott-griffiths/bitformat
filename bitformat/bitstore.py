from __future__ import annotations

import bitarray
import bitarray.util
import copy
import struct
from typing import Union, Iterable, Iterator, Any

def tidy_input_string(s: str) -> str:
    """Return string made lowercase and with all whitespace and underscores removed."""
    try:
        t = s.split()
    except (AttributeError, TypeError):
        raise ValueError(f"Expected str object but received a {type(s)} with value {s}.")
    return ''.join(t).lower().replace('_', '')


class BitStore:
    """A light wrapper around bitarray"""

    __slots__ = ('_bitarray',)

    def __init__(self) -> None:
        self._bitarray = bitarray.bitarray()

    @classmethod
    def from_bitarray(cls, b: bitarray.bitarray) -> BitStore:
        x = super().__new__(cls)
        x._bitarray = b
        return x

    @classmethod
    def from_zeros(cls, i: int) -> BitStore:
        x = super().__new__(cls)
        x._bitarray = bitarray.bitarray(i)
        return x

    @classmethod
    def from_binstr(cls, s: str) -> BitStore:
        x = super().__new__(cls)
        x._bitarray = bitarray.bitarray(s)
        return x

    @classmethod
    def from_bytes(cls, b: Union[bytes, bytearray, memoryview], /) -> BitStore:
        x = super().__new__(cls)
        x._bitarray = bitarray.bitarray()
        x._bitarray.frombytes(b)
        return x

    @classmethod
    def from_hex(cls, hexstring: str, /) -> BitStore:
        hexstring = tidy_input_string(hexstring)
        hexstring = hexstring.replace('0x', '')
        try:
            ba = bitarray.util.hex2ba(hexstring)
        except ValueError:
            raise ValueError(f"Invalid symbol in hex initialiser: '{hexstring}'")
        return BitStore.from_bitarray(ba)

    @classmethod
    def from_oct(cls, octstring: str, /) -> BitStore:
        octstring = tidy_input_string(octstring)
        octstring = octstring.replace('0o', '')
        try:
            ba = bitarray.util.base2ba(8, octstring)
        except ValueError:
            raise ValueError("Invalid symbol in oct initialiser.")
        return BitStore.from_bitarray(ba)

    @classmethod
    def from_bin(cls, binstring: str, /) -> BitStore:
        binstring = tidy_input_string(binstring)
        binstring = binstring.replace('0b', '')
        try:
            return BitStore.from_binstr(binstring)
        except ValueError:
            raise ValueError(f"Invalid character in bin initialiser {binstring}.")

    @classmethod
    def from_int(cls, i: int, length: int, signed: bool, /) -> BitStore:
        i = int(i)
        try:
            return BitStore.from_bitarray(bitarray.util.int2ba(i, length=length, endian='big', signed=signed))
        except OverflowError as e:
            if signed:
                if i >= (1 << (length - 1)) or i < -(1 << (length - 1)):
                    raise ValueError(f"{i} is too large a signed integer for a Bits of length {length}. "
                                     f"The allowed range is [{-(1 << (length - 1))}, {(1 << (length - 1)) - 1}].")
            else:
                if i >= (1 << length):
                    raise ValueError(f"{i} is too large an unsigned integer for a Bits of length {length}. "
                                     f"The allowed range is [0, {(1 << length) - 1}].")
                if i < 0:
                    raise ValueError("uint cannot be initialised with a negative number.")
            raise e

    @classmethod
    def from_float(cls, f: Union[str, float], length: int) -> BitStore:
        f = float(f)
        fmt = {16: '>e', 32: '>f', 64: '>d'}[length]
        try:
            b = struct.pack(fmt, f)
        except OverflowError:
            # If float64 doesn't fit it automatically goes to 'inf'. This reproduces that behaviour for other types.
            b = struct.pack(fmt, float('inf') if f > 0 else float('-inf'))
        return BitStore.from_bytes(b)

    def setall(self, value: int, /) -> None:
        self._bitarray.setall(value)

    def to_bytes(self) -> bytes:
        return self._bitarray.tobytes()

    def slice_to_uint(self, start: int | None = None, end: int | None = None) -> int:
        return bitarray.util.ba2int(self.getslice(start, end)._bitarray, signed=False)

    def slice_to_int(self, start: int | None = None, end: int | None = None) -> int:
        return bitarray.util.ba2int(self.getslice(start, end)._bitarray, signed=True)

    def slice_to_hex(self, start: int | None = None, end: int | None = None) -> str:
        return bitarray.util.ba2hex(self.getslice(start, end)._bitarray)

    def slice_to_bin(self, start: int | None = None, end: int | None = None) -> str:
        return self.getslice(start, end)._bitarray.to01()

    def slice_to_oct(self, start: int | None = None, end: int | None = None) -> str:
        return bitarray.util.ba2base(8, self.getslice(start, end)._bitarray)

    def __iadd__(self, other: BitStore, /) -> BitStore:
        self._bitarray += other._bitarray
        return self

    def __add__(self, other: BitStore, /) -> BitStore:
        bs = self._copy()
        bs += other
        return bs

    def __eq__(self, other: Any, /) -> bool:
        return self._bitarray == other._bitarray

    def __and__(self, other: BitStore, /) -> BitStore:
        return BitStore.from_bitarray(self._bitarray & other._bitarray)

    def __or__(self, other: BitStore, /) -> BitStore:
        return BitStore.from_bitarray(self._bitarray | other._bitarray)

    def __xor__(self, other: BitStore, /) -> BitStore:
        return BitStore.from_bitarray(self._bitarray ^ other._bitarray)

    def __iand__(self, other: BitStore, /) -> BitStore:
        self._bitarray &= other._bitarray
        return self

    def __ior__(self, other: BitStore, /) -> BitStore:
        self._bitarray |= other._bitarray
        return self

    def __ixor__(self, other: BitStore, /) -> BitStore:
        self._bitarray ^= other._bitarray
        return self

    def find(self, bs: BitStore, start: int, end: int, bytealigned: bool = False) -> int:
        if not bytealigned:
            return self._bitarray.find(bs._bitarray, start, end)
        try:
            return next(self.findall(bs, start, end, bytealigned))
        except StopIteration:
            return -1

    def rfind(self, bs: BitStore, start: int, end: int, bytealigned: bool = False):
        if not bytealigned:
            return self._bitarray.find(bs._bitarray, start, end, right=True)
        try:
            return next(self.rfindall(bs, start, end, bytealigned))
        except StopIteration:
            return -1

    def findall(self, bs: BitStore, start: int, end: int, bytealigned: bool = False) -> Iterator[int]:
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

    def rfindall(self, bs: BitStore, start: int, end: int, bytealigned: bool = False) -> Iterator[int]:
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

    def clear(self) -> None:
        self._bitarray.clear()

    def reverse(self) -> None:
        self._bitarray.reverse()

    def __iter__(self) -> Iterable[bool]:
        for i in range(len(self)):
            yield self.getindex(i)

    def _copy(self) -> BitStore:
        """Always creates a copy, even if instance is immutable."""
        s_copy = self.__class__()
        s_copy._bitarray = copy.copy(self._bitarray)
        return s_copy

    def __getitem__(self, item: Union[int, slice], /) -> Union[int, BitStore]:
        # Use getindex or getslice instead
        raise NotImplementedError

    def getindex(self, index: int, /) -> bool:
        return bool(self._bitarray.__getitem__(index))

    def getslice_withstep(self, key: slice, /) -> BitStore:
        return BitStore.from_bitarray(self._bitarray.__getitem__(key))

    def getslice(self, start: int | None, stop: int | None, /) -> BitStore:
        return BitStore.from_bitarray(self._bitarray[start:stop])

    def invert(self, index: int | None = None, /) -> None:
        if index is not None:
            self._bitarray.invert(index)
        else:
            self._bitarray.invert()

    def any_set(self) -> bool:
        return self._bitarray.any()

    def all_set(self) -> bool:
        return self._bitarray.all()

    def __len__(self) -> int:
        return len(self._bitarray)

    def setitem(self, key, value, /):
        if isinstance(value, BitStore):
            self._bitarray.__setitem__(key, value._bitarray)
        else:
            self._bitarray.__setitem__(key, value)
