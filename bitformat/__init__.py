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
from ._bits import Bits
from ._array import Array, BitsProxy
from ._dtypes import DtypeDefinition, Register, Dtype, DtypeSingle, DtypeArray, DtypeTuple
from ._fieldtype import FieldType
from ._field import Field
from ._format import Format
from ._if import If
from ._pass import Pass
from ._repeat import Repeat
from ._options import Options
from ._common import Expression, Endianness, byteorder, DtypeKind
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
    DtypeDefinition(DtypeKind.UINT, "a two's complement unsigned int", "unsigned int",
                    Bits._set_u, Bits._get_u, int,
                    False, uint_bits2chars, endianness_variants=True),
    DtypeDefinition(DtypeKind.INT, "a two's complement signed int", "signed int",
                    Bits._set_i, Bits._get_i, int,
                    True, int_bits2chars, endianness_variants=True),

    # Literal types
    DtypeDefinition(DtypeKind.BIN, "a binary string", "binary string",
                    Bits._set_bin_safe, Bits._get_bin, str,
                    False, bits_per_character=1),
    DtypeDefinition(DtypeKind.OCT, "an octal string", "octal string",
                    Bits._set_oct, Bits._get_oct, str,
                    False, bits_per_character=3),
    DtypeDefinition(DtypeKind.HEX, "a hexadecimal string", "hex string",
                    Bits._set_hex, Bits._get_hex, str,
                    False, bits_per_character=4),
    DtypeDefinition(DtypeKind.BYTES, "a bytes object", "bytes",
                    Bits._set_bytes, Bits._get_bytes, bytes,
                    False, bits_per_character=8),

    # Float types
    DtypeDefinition(DtypeKind.FLOAT, "an IEEE floating point number", "float",
                    Bits._set_f, Bits._get_f, float,
                    True, float_bits2chars, endianness_variants=True, allowed_sizes=(16, 32, 64)),

    # Other known length types
    DtypeDefinition(DtypeKind.BITS, "a Bits object", "Bits",
                    Bits._set_bits, Bits._get_bits, Bits,
                    False, bits_bits2chars),
    DtypeDefinition(DtypeKind.BOOL, "a bool (True or False)", "bool",
                    Bits._set_bool, Bits._get_bool, bool,
                    False, bool_bits2chars, allowed_sizes=(1,)),

    # Special case pad type
    DtypeDefinition(DtypeKind.PAD, "a skipped section of padding", "padding",
                    Bits._set_pad, Bits._get_pad, None,
                    False, None),
]


for dt in dtype_definitions:
    Register().add_dtype(dt)


__all__ = ["Bits", "Dtype", "DtypeSingle", "DtypeArray", "DtypeTuple", "Format", "FieldType", "Field", "Array", "BitsProxy", "Expression",
           "Options", "Repeat", "Register", "Endianness", "If", "Pass", "Reader", "DtypeKind"]

# Set the __module__ of each of the types in __all__ to 'bitformat' so that they appear as bitformat.Bits instead of bitformat._bits.Bits etc.
for name in __all__:
    locals()[name].__module__ = "bitformat"

__all__.extend(["byteorder"])
