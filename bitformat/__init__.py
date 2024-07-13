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

__version__ = "0.1.0"

__author__ = "Scott Griffiths"


from ._bits import Bits
from ._array import Array, BitsProxy
from ._dtypes import DtypeDefinition, dtype_register, Dtype
from ._field import Field, FieldArray
from ._format import Format
from ._options import Options
from typing import List, Tuple, Literal

# The Options class returns a singleton.
options = Options()


# These methods convert a bit length to the number of characters needed to print it for different interpretations.
def hex_bits2chars(bitlength: int):
    # One character for every 4 bits
    return bitlength // 4


def oct_bits2chars(bitlength: int):
    # One character for every 3 bits
    return bitlength // 3


def bin_bits2chars(bitlength: int):
    # One character for each bit
    return bitlength


def bytes_bits2chars(bitlength: int):
    # One character for every 8 bits
    return bitlength // 8


def uint_bits2chars(bitlength: int):
    # How many characters is largest possible int of this length?
    return len(str((1 << bitlength) - 1))


def int_bits2chars(bitlength: int):
    # How many characters is largest negative int of this length? (To include minus sign).
    return len(str((-1 << (bitlength - 1))))


def float_bits2chars(bitlength: Literal[16, 32, 64]):
    # These bit lengths were found by looking at lots of possible values
    if bitlength in [16, 32]:
        return 23  # Empirical value
    else:
        return 24  # Empirical value


def bits_bits2chars(bitlength: int):
    # For bits type we can see how long it needs to be printed by trying any value
    temp = Bits.zeros(bitlength)
    return len(temp._simple_str())


def bool_bits2chars(_: Literal[1]):
    # Bools are printed as 1 or 0, not True or False, so are one character each
    return 1


dtype_definitions = [
    # Integer types
    DtypeDefinition('u', Bits._setuint, Bits._getuint, int, False, uint_bits2chars,
                    description="a two's complement unsigned int"),
    DtypeDefinition('i', Bits._setint, Bits._getint, int, True, int_bits2chars,
                    description="a two's complement signed int"),
    # String types
    DtypeDefinition('hex', Bits._sethex, Bits._gethex, str, False, hex_bits2chars,
                    allowed_lengths=(0, 4, 8, ...), description="a hexadecimal string"),
    DtypeDefinition('bin', Bits._setbin_safe, Bits._getbin, str, False, bin_bits2chars,
                    description="a binary string"),
    DtypeDefinition('oct', Bits._setoct, Bits._getoct, str, False, oct_bits2chars,
                    allowed_lengths=(0, 3, 6, ...), description="an octal string"),
    # Float types
    DtypeDefinition('f', Bits._setfloat, Bits._getfloat, float, True, float_bits2chars,
                    allowed_lengths=(16, 32, 64), description="a big-endian floating point number"),
    # Other known length types
    DtypeDefinition('bits', Bits._setbits, Bits._getbits, Bits, False, bits_bits2chars,
                    description="a Bits object"),
    DtypeDefinition('bool', Bits._setbool, Bits._getbool, bool, False, bool_bits2chars,
                    allowed_lengths=(1,), description="a bool (True or False)"),
    DtypeDefinition('bytes', Bits._setbytes, Bits._getbytes, bytes, False, bytes_bits2chars,
                    multiplier=8, description="a bytes object"),
    # Special case pad type
    DtypeDefinition('pad', Bits._setpad, Bits._getpad, None, False, None,
                    description="a skipped section of padding")
    ]


aliases: List[Tuple[str, str]] = [
    # Longer aliases for some popular types
    ('i', 'int'),
    ('u', 'uint'),
    ('f', 'float'),
]

for dt in dtype_definitions:
    dtype_register.add_dtype(dt)
for alias in aliases:
    dtype_register.add_dtype_alias(alias[0], alias[1])


__all__ = ['Bits', 'Dtype', 'Format', 'Field', 'Array', 'FieldArray', 'BitsProxy', 'Options', 'options']
