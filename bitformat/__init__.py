r"""
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


__author__ = "Scott Griffiths"


from ._version import VERSION as __version__
from ._bits import Bits, MutableBits, dtype_token_to_bits
from ._array import Array
from ._dtypes import DtypeDefinition, Register, Dtype, DtypeSingle, DtypeArray, DtypeTuple
from ._fieldtype import FieldType
from ._field import Field
from ._format import Format
from ._if import If
from ._pass import Pass
from ._let import Let
from ._repeat import Repeat
from ._while import While
from ._options import Options
from ._common import Expression, Endianness, byteorder, DtypeKind
from ._reader import Reader
from ._dtype_definitions import dtype_definitions

# This lets us pass in a Python method for the Rust parser to use.
from .bit_rust import set_dtype_parser
set_dtype_parser(dtype_token_to_bits)


for dt in dtype_definitions:
    Register().add_dtype(dt)


__all__ = ["Bits", "Dtype", "DtypeSingle", "DtypeArray", "DtypeTuple", "Format", "FieldType", "Field", "Array", "Expression",
           "Options", "Repeat", "While", "Register", "Endianness", "If", "Pass", "Let", "Reader", "DtypeKind", "MutableBits"]

# Set the __module__ of each of the types in __all__ to 'bitformat' so that they appear as bitformat.Bits instead of bitformat._bits.Bits etc.
for name in __all__:
    locals()[name].__module__ = "bitformat"

__all__.extend(["byteorder"])
