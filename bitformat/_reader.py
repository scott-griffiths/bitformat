from __future__ import annotations

from typing import Any

from ._bits import Bits
from ._fieldtype import FieldType
from ._dtypes import Dtype, DtypeSingle
from ._common import DtypeKind


class Reader:
    """
    Wraps a Bits object and a bit position to allow reading and parsing as a stream of bits.

    **Methods:**

    - ``read()``: Read from the current bit position, and interpret according to the given format.
    - ``peek()``: Peek from the current bit position, and interpret according to the given format without changing the pos.
    - ``parse()``: Parse a fieldtype from the current bit position, returning the number of bits parsed.

    **Properties:**

    - ``bits``: The ``Bits`` object.
    - ``pos``: The current bit position to read and parse from.
    """

    def __init__(self, bits: Bits, pos: int = 0) -> None:
        self.bits = bits
        self._pos = pos

    @property
    def bits(self) -> Bits:
        """
        Get or set the Bits object associated with the Reader.

        Changing the Bits object may invalidate the bit position, but it's left
        to the user to manage this.

        **Returns:**
            Bits: The current Bits object.

        **Raises:**
            ValueError: If the provided value is not a valid BitsType.
        """
        return self._bits

    @bits.setter
    def bits(self, value: Bits) -> None:
        if not isinstance(value, Bits):
            help_ = ""
            if isinstance(value, str):
                help_ = " Perhaps use 'Bits.from_string()'?"
            elif isinstance(value, (bytes, bytearray, memoryview)):
                help_ = " Perhaps use 'Bits.from_bytes()'?"
            raise TypeError(f"A Reader should be initialised with a 'Bits' object, but received a {type(value)}.{help_}")
        self._bits = value

    @property
    def pos(self) -> int:
        """
        Get or set the current bit position.
        Should be a positive int, but no attempt is made to check if the position is valid before it is used.

        **Returns:**
            int: The current bit position.

        **Raises:**
            ValueError: If the provided position is not an integer.
        """
        return self._pos

    @pos.setter
    def pos(self, value: int) -> None:
        self._pos = int(value)

    def read(self, dtype: Dtype | str | int, /) -> Any | tuple[Any] | list[Any | tuple[Any]]:
        """Read from the current bit position, and interpret according to the given dtype."""
        if isinstance(dtype, int):
            dtype = DtypeSingle.from_params(DtypeKind.BITS, dtype)
        elif isinstance(dtype, str):
            dtype = Dtype.from_string(dtype)
        if self._pos + dtype.bit_length > len(self._bits):
            raise ValueError(
                f"Reading '{dtype}' needs {dtype.bit_length} bits, but at position {self._pos} only {len(self._bits) - self._pos} bits remain."
            )
        x = dtype.unpack(self.bits[self._pos : self._pos + dtype.bit_length])
        self._pos += dtype.bit_length
        return x

    def peek(self, dtype: Dtype | str | int, /) -> Any | tuple[Any] | list[Any | tuple[Any]]:
        """Peek from the current bit position, and interpret according to the given dtype."""
        current_pos = self._pos
        value = self.read(dtype)
        self._pos = current_pos
        return value

    def parse(self, f: FieldType, /) -> int:
        """Parse a fieldtype from the current bit position, returning the number of bits parsed."""
        try:
            bits_parsed = f.parse(self._bits[self._pos :])
        except AttributeError:
            raise TypeError(f"parse() requires a FieldType. Got {f!r} of type {type(f)}.")
        self._pos += bits_parsed
        return bits_parsed

    def __str__(self) -> str:
        return f"Reader(<Bits class of length {len(self._bits)} bits>, pos={self._pos})"

    def __repr__(self) -> str:
        return str(self)

    def __len__(self) -> int:
        return len(self.bits)
