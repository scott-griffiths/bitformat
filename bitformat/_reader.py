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
            self._bits = Bits.from_auto(bits)
        self._pos = pos

    @property
    def bits(self) -> Bits:
        return self._bits

    @bits.setter
    def bits(self, value: BitsType) -> None:
        self._bits = Bits.from_auto(value)

    @property
    def pos(self) -> int:
        return self._pos

    @pos.setter
    def pos(self, value: int) -> None:
        self._pos = int(value)

    def read(self, fmt: int | Dtype | DtypeList | str, /) -> Any | list[Any]:
        """Read from the current bit position, and interpret according to the given format."""
        if isinstance(fmt, int):
            if self.pos + fmt > len(self.bits):
                raise ValueError(f"Cannot read {fmt} bits at position {self.pos} as only {len(self.bits) - self.pos} bits remain.")
            x = self.bits[self.pos:self.pos + fmt]
            self.pos += fmt
            return x
        if isinstance(fmt, str):
            if ',' in fmt:
                fmt = DtypeList.from_string(fmt)
            else:
                fmt = Dtype.from_string(fmt)
        if self.pos + fmt.bitlength > len(self.bits):
            raise ValueError(f"Reading '{fmt}' needs {fmt.bitlength} bits, but at position {self.pos} only {len(self.bits) - self.pos} bits remain.")
        x = fmt.unpack(self.bits[self.pos:self.pos + fmt.bitlength])
        self.pos += fmt.bitlength
        return x

    def parse(self, f: FieldType, /) -> int:
        """Parse a fieldtype from the current bit position, returning the number of bits parsed."""
        try:
            bits_parsed = f.parse(self.bits[self.pos:])
        except AttributeError:
            raise ValueError(f"parse() requires a FieldType. Got {f!r} of type {type(f)}.")
        self.pos += bits_parsed
        return bits_parsed

    def __str__(self):
        return f"Reader('{self.bits}', pos={self.pos})"

    def __repr__(self):
        return str(self)