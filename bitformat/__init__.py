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
from ._bits import Tibs, Mutibs
from ._array import Array
from ._dtypes import Register, Dtype, DtypeSingle, DtypeArray, DtypeTuple
from ._fieldtype import FieldType
from ._field import Field
from ._format import Format
from ._if import If
from ._pass import Pass
from ._let import Let
from ._repeat import Repeat
from ._while import While
from ._options import Options
from ._common import Expression, Endianness, DtypeKind, byteorder
from ._reader import Reader
from ._dtype_definitions import dtype_definitions as _dtype_definitions


__all__ = ["Tibs", "Dtype", "DtypeSingle", "DtypeArray", "DtypeTuple", "Format", "FieldType", "Field", "Array", "Expression",
           "Options", "Repeat", "While", "Register", "Endianness", "If", "Pass", "Let", "Reader", "DtypeKind", "Mutibs"]


def _init():
    for _dt in _dtype_definitions:
        Register().add_dtype(_dt)

_init()

# Set the __module__ of each bitformat-defined type in __all__ to 'bitformat'
# so that they appear as bitformat.Dtype instead of bitformat._dtypes.Dtype etc.
for _name in __all__:
    if _name not in {"Tibs", "Mutibs"}:
        locals()[_name].__module__ = "bitformat"
