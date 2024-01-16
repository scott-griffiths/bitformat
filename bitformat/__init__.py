from __future__ import annotations
"""
A library for creating and interpreting binary formats.
"""

__licence__ = """
The MIT License

Copyright (c) 2024 Scott Griffiths (dr.scottgriffiths@gmail.com)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

__version__ = "0.0.1"

__author__ = "Scott Griffiths"


from bitstring import Bits, Dtype
from typing import Iterable, Union, Any

class Format:

    def __init__(self, fmt: Union[Union[Bits, Dtype, str, Format, None], Iterable[Union[Bits, Dtype, str, Format]]] = None) -> None:
        if isinstance(fmt, Bits):
            self.tokens = [fmt]
        else:
            if not isinstance(fmt, Iterable):
                fmt = [fmt]
            self.tokens = fmt

    def pack(self, *values: Iterable[Any]) -> Bits:
        out_bits = []
        value_iter = iter(values)
        for token in self.tokens:
            if isinstance(token, Bits):
                out_bits.append(token)
            elif isinstance(token, Dtype):
                b = Bits()
                token.set_fn(b, next(value_iter))
                out_bits.append(b)
        out = Bits().join(out_bits)
        return out


__all__ = ['Bits', 'Dtype', 'Format']