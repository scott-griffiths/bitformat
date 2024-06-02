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

__version__ = "0.0.2"

__author__ = "Scott Griffiths"


import sys
from .field import Field, FieldArray
from .format import Format, Repeat
from .bits import Bits
from .dtypes import DtypeDefinition, dtype_register, Dtype
from .bits import Bits
from .bitstring_options import Options
from .bitarray_ import BitArray
from .array_ import Array
from .exceptions import Error, ReadError, InterpretError, ByteAlignError, CreationError
from .dtypes import DtypeDefinition, dtype_register, Dtype
import types
from typing import List, Tuple, Literal

# The Options class returns a singleton.
options = Options()

# These get defined properly by the module magic below. This just stops mypy complaining about them.
bytealigned = lsb0 = None


# An opaque way of adding module level properties. Taken from https://peps.python.org/pep-0549/
# This is now deprecated. Use the options object directly instead.
class _MyModuleType(types.ModuleType):
    @property
    def bytealigned(self) -> bool:
        """Determines whether a number of methods default to working only on byte boundaries."""
        return options.bytealigned

    @bytealigned.setter
    def bytealigned(self, value: bool) -> None:
        """Determines whether a number of methods default to working only on byte boundaries."""
        options.bytealigned = value

    @property
    def lsb0(self) -> bool:
        """If True, the least significant bit (the final bit) is indexed as bit zero."""
        return options.lsb0

    @lsb0.setter
    def lsb0(self, value: bool) -> None:
        """If True, the least significant bit (the final bit) is indexed as bit zero."""
        options.lsb0 = value


sys.modules[__name__].__class__ = _MyModuleType










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



def bfloat_bits2chars(_: Literal[16]):
    # Found by looking at all the possible values
    return 23  # Empirical value


def bits_bits2chars(bitlength: int):
    # For bits type we can see how long it needs to be printed by trying any value
    temp = Bits(bitlength)
    return len(str(temp))


def bool_bits2chars(_: Literal[1]):
    # Bools are printed as 1 or 0, not True or False, so are one character each
    return 1


dtype_definitions = [
    # Integer types
    DtypeDefinition('uint', Bits._setuint, Bits._getuint, int, False, uint_bits2chars,
                    description="a two's complement unsigned int"),
    DtypeDefinition('uintle', Bits._setuintle, Bits._getuintle, int, False, uint_bits2chars,
                    allowed_lengths=(8, 16, 24, ...), description="a two's complement little-endian unsigned int"),
    DtypeDefinition('uintbe', Bits._setuintbe, Bits._getuintbe, int, False, uint_bits2chars,
                    allowed_lengths=(8, 16, 24, ...), description="a two's complement big-endian unsigned int"),
    DtypeDefinition('int', Bits._setint, Bits._getint, int, True, int_bits2chars,
                    description="a two's complement signed int"),
    DtypeDefinition('intle', Bits._setintle, Bits._getintle, int, True, int_bits2chars,
                    allowed_lengths=(8, 16, 24, ...), description="a two's complement little-endian signed int"),
    DtypeDefinition('intbe', Bits._setintbe, Bits._getintbe, int, True, int_bits2chars,
                    allowed_lengths=(8, 16, 24, ...), description="a two's complement big-endian signed int"),
    # String types
    DtypeDefinition('hex', Bits._sethex, Bits._gethex, str, False, hex_bits2chars,
                    allowed_lengths=(0, 4, 8, ...), description="a hexadecimal string"),
    DtypeDefinition('bin', Bits._setbin_safe, Bits._getbin, str, False, bin_bits2chars,
                    description="a binary string"),
    DtypeDefinition('oct', Bits._setoct, Bits._getoct, str, False, oct_bits2chars,
                    allowed_lengths=(0, 3, 6, ...), description="an octal string"),
    # Float types
    DtypeDefinition('float', Bits._setfloatbe, Bits._getfloatbe, float, True, float_bits2chars,
                    allowed_lengths=(16, 32, 64), description="a big-endian floating point number"),
    DtypeDefinition('floatle', Bits._setfloatle, Bits._getfloatle, float, True, float_bits2chars,
                    allowed_lengths=(16, 32, 64), description="a little-endian floating point number"),
    DtypeDefinition('bfloat', Bits._setbfloatbe, Bits._getbfloatbe, float, True, bfloat_bits2chars,
                    allowed_lengths=(16,), description="a 16 bit big-endian bfloat floating point number"),
    DtypeDefinition('bfloatle', Bits._setbfloatle, Bits._getbfloatle, float, True, bfloat_bits2chars,
                    allowed_lengths=(16,), description="a 16 bit little-endian bfloat floating point number"),
    # Other known length types
    DtypeDefinition('bits', Bits._setbits, Bits._getbits, Bits, False, bits_bits2chars,
                    description="a bitstring object"),
    DtypeDefinition('bool', Bits._setbool, Bits._getbool, bool, False, bool_bits2chars,
                    allowed_lengths=(1,), description="a bool (True or False)"),
    DtypeDefinition('bytes', Bits._setbytes, Bits._getbytes, bytes, False, bytes_bits2chars,
                    multiplier=8, description="a bytes object"),
    # Unknown length types
    DtypeDefinition('se', Bits._setse, Bits._getse, int, True, None,
                    variable_length=True, description="a signed exponential-Golomb code"),
    DtypeDefinition('ue', Bits._setue, Bits._getue, int, False, None,
                    variable_length=True, description="an unsigned exponential-Golomb code"),
    DtypeDefinition('sie', Bits._setsie, Bits._getsie, int, True, None,
                    variable_length=True, description="a signed interleaved exponential-Golomb code"),
    DtypeDefinition('uie', Bits._setuie, Bits._getuie, int, False, None,
                    variable_length=True, description="an unsigned interleaved exponential-Golomb code"),
    # Special case pad type
    DtypeDefinition('pad', Bits._setpad, Bits._getpad, None, False, None,
                    description="a skipped section of padding")
    ]


aliases: List[Tuple[str, str]] = [
    # Floats default to big endian
    ('float', 'floatbe'),
    ('bfloat', 'bfloatbe'),

    # Some single letter aliases for popular types
    ('int', 'i'),
    ('uint', 'u'),
    ('hex', 'h'),
    ('oct', 'o'),
    ('bin', 'b'),
    ('float', 'f'),
]

# Create native-endian aliases depending on the byteorder of the system
byteorder: str = sys.byteorder
if byteorder == 'little':
    aliases.extend([
        ('uintle', 'uintne'),
        ('intle', 'intne'),
        ('floatle', 'floatne'),
        ('bfloatle', 'bfloatne'),
    ])
else:
    aliases.extend([
        ('uintbe', 'uintne'),
        ('intbe', 'intne'),
        ('floatbe', 'floatne'),
        ('bfloatbe', 'bfloatne'),
    ])


for dt in dtype_definitions:
    dtype_register.add_dtype(dt)
for alias in aliases:
    dtype_register.add_dtype_alias(alias[0], alias[1])


__all__ = ['Bits', 'Dtype', 'Format', 'Field', 'Array', 'FieldArray', 'Repeat',
           'BitArray',
           'Error', 'ReadError', 'InterpretError',
           'ByteAlignError', 'CreationError', 'bytealigned', 'lsb0', 'Dtype', 'options']