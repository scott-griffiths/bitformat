from __future__ import annotations

from typing import Any

from bitformat._bits import Bits, BitsType
from bitformat._fieldtype import FieldType
from bitformat._dtypes import Dtype, DtypeList


class Reader:

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

    def read(self, v: int | Dtype | DtypeList | str, /) -> Any | list[Any]:
        if isinstance(v, int):
            if self.pos + v > len(self.bits):
                raise ValueError(f"Cannot read {v} bits at position {self.pos} as only {len(self.bits) - self.pos} bits remain.")
            x = self.bits[self.pos:self.pos + v]
            self.pos += v
            return x
        if isinstance(v, str):
            if ',' in v:
                v = DtypeList.from_string(v)
            else:
                v = Dtype.from_string(v)
        if self.pos + v.bitlength > len(self.bits):
            raise ValueError(f"Reading '{v}' needs {v.bitlength} bits, but at position {self.pos} only {len(self.bits) - self.pos} bits remain.")
        x = v.unpack(self.bits[self.pos:self.pos + v.bitlength])
        self.pos += v.bitlength
        return x

    def parse(self, f: FieldType | str) -> int:
        if isinstance(f, str):
            f = FieldType.from_string(f)
        bits_parsed = f.parse(self.bits[self.pos:])
        self.pos += bits_parsed
        return bits_parsed

    def __str__(self):
        return f"Reader({self.bits}, {self.pos})"

    def __repr__(self):
        return str(self)