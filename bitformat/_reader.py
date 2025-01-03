from __future__ import annotations

from typing import Any

from bitformat._bits import Bits, BitsType
from bitformat._fieldtype import FieldType
from bitformat._dtypes import Dtype, DtypeList


class Reader:
    """
    Wraps a Bits object and a bit position to allow reading and parsing as a stream of bits.

    **Methods:**

    - ``read()``: Read from the current bit position, and interpret according to the given format.
    - ``parse()``: Parse a fieldtype from the current bit position, returning the number of bits parsed.

    **Properties:**

    - ``bits``: The ``Bits`` object.
    - ``pos``: The current bit position to read and parse from.
    """

    def __init__(self, bits: BitsType | None = None, pos: int = 0) -> None:
        if bits is None:
            self._bits = Bits()
        else:
            self._bits = Bits.from_any(bits)
        self._pos = pos

    @property
    def bits(self) -> Bits:
        """
        Get or set the Bits object associated with the Reader.
        Can be set from anything valid for :class:`Bits.from_auto`, for example
        ``bytes`` objects, formatted strings, or :class:`Bits` objects.

        Changing the Bits object may invalidate the bit position, but it's left
        to the user to manage this.

        **Returns:**
            Bits: The current Bits object.

        **Raises:**
            ValueError: If the provided value is not a valid BitsType.
        """
        return self._bits

    @bits.setter
    def bits(self, value: BitsType) -> None:
        self._bits = Bits.from_any(value)

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

    def read(
        self, dtype: Dtype | DtypeList | str, /
    ) -> Any | tuple[Any] | list[Any | tuple[Any]]:
        """Read from the current bit position, and interpret according to the given dtype."""
        if isinstance(dtype, str):
            if "," in dtype:
                dtype = DtypeList.from_string(dtype)
            else:
                dtype = Dtype.from_string(dtype)
        if self._pos + dtype.bitlength > len(self._bits):
            raise ValueError(
                f"Reading '{dtype}' needs {dtype.bitlength} bits, but at position {self._pos} only {len(self._bits) - self._pos} bits remain."
            )
        x = dtype.unpack(self.bits[self._pos : self._pos + dtype.bitlength])
        self._pos += dtype.bitlength
        return x

    def parse(self, f: FieldType, /) -> int:
        """Parse a fieldtype from the current bit position, returning the number of bits parsed."""
        try:
            bits_parsed = f.parse(self._bits[self._pos :])
        except AttributeError:
            raise ValueError(
                f"parse() requires a FieldType. Got {f!r} of type {type(f)}."
            )
        self._pos += bits_parsed
        return bits_parsed

    def __str__(self) -> str:
        return f"Reader(<Bits class of length {len(self._bits)} bits>, pos={self._pos})"

    def __repr__(self) -> str:
        return str(self)
