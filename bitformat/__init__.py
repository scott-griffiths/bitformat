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

__version__ = "0.2.0"

__author__ = "Scott Griffiths"


from ._bits import Bits
from ._array import Array, BitsProxy
from ._dtypes import DtypeDefinition, Register, Dtype, DtypeTuple
from ._fieldtype import FieldType
from ._field import Field
from ._format import Format
from ._if import If
from ._pass import Pass
from ._repeat import Repeat
from ._options import Options
from ._common import Expression, Endianness, byteorder
from ._reader import Reader
from typing import Literal


# These methods convert a bit length to the number of characters needed to print it for different interpretations.


def uint_bits2chars(bit_length: int):
    # How many characters is largest possible int of this length?
    return len(str((1 << bit_length) - 1))


def int_bits2chars(bit_length: int):
    # How many characters is largest negative int of this length? (To include minus sign).
    return len(str((-1 << (bit_length - 1))))


def float_bits2chars(bit_length: Literal[16, 32, 64]):
    # These bit lengths were found by looking at lots of possible values
    if bit_length in [16, 32]:
        return 23  # Empirical value
    else:
        return 24  # Empirical value


def bits_bits2chars(bit_length: int):
    # For bits type we can see how long it needs to be printed by trying any value
    temp = Bits.from_zeros(bit_length)
    return len(temp._simple_str())


def bool_bits2chars(_: Literal[1]):
    # Bools are printed as 1 or 0, not True or False, so are one character each
    return 1


dtype_definitions = [
    # Integer types
    DtypeDefinition(
        "u",
        "a two's complement unsigned int",
        Bits._setuint,
        Bits._getuint,
        int,
        False,
        uint_bits2chars,
        endianness_variants=True,
    ),
    DtypeDefinition(
        "i",
        "a two's complement signed int",
        Bits._setint,
        Bits._getint,
        int,
        True,
        int_bits2chars,
        endianness_variants=True,
    ),
    # Literal types
    DtypeDefinition(
        "bin",
        "a binary string",
        Bits._setbin_safe,
        Bits._getbin,
        str,
        False,
        bits_per_character=1,
    ),
    DtypeDefinition(
        "oct",
        "an octal string",
        Bits._setoct,
        Bits._getoct,
        str,
        False,
        bits_per_character=3,
    ),
    DtypeDefinition(
        "hex",
        "a hexadecimal string",
        Bits._sethex,
        Bits._gethex,
        str,
        False,
        bits_per_character=4,
    ),
    DtypeDefinition(
        "bytes",
        "a bytes object",
        Bits._setbytes,
        Bits._getbytes,
        bytes,
        False,
        bits_per_character=8,
    ),
    # Float types
    DtypeDefinition(
        "f",
        "an IEEE floating point number",
        Bits._setfloat,
        Bits._getfloat,
        float,
        True,
        float_bits2chars,
        endianness_variants=True,
        allowed_sizes=(16, 32, 64),
    ),
    # Other known length types
    DtypeDefinition(
        "bits",
        "a Bits object",
        Bits._setbits,
        Bits._getbits,
        Bits,
        False,
        bits_bits2chars,
    ),
    DtypeDefinition(
        "bool",
        "a bool (True or False)",
        Bits._setbool,
        Bits._getbool,
        bool,
        False,
        bool_bits2chars,
        allowed_sizes=(1,),
    ),
    # Special case pad type
    DtypeDefinition(
        "pad",
        "a skipped section of padding",
        Bits._setpad,
        Bits._getpad,
        None,
        False,
        None,
    ),
]


for dt in dtype_definitions:
    Register().add_dtype(dt)


__all__ = [
    "Bits",
    "Dtype",
    "DtypeTuple",
    "Format",
    "FieldType",
    "Field",
    "Array",
    "BitsProxy",
    "Expression",
    "Options",
    "Repeat",
    "Register",
    "Endianness",
    "If",
    "Pass",
    "Reader",
]

# Set the __module__ of each of the types in __all__ to 'bitformat' so that they appear as bitformat.Bits instead of bitformat._bits.Bits etc.
for name in __all__:
    locals()[name].__module__ = "bitformat"

__all__.extend(["byteorder"])
