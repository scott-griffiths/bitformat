
[![bitformat](https://raw.githubusercontent.com/scott-griffiths/bitformat/main/doc/bitformat_logo_small.png)](https://github.com/scott-griffiths/bitformat)

A Python library for creating and parsing binary formats.

[![PyPI - Version](https://img.shields.io/pypi/v/bitformat?label=PyPI&logo=pypi&logoColor=white)](https://pypi.org/project/bitformat/)
[![CI badge](https://github.com/scott-griffiths/bitformat/actions/workflows/.github/workflows/test.yml/badge.svg)](https://github.com/scott-griffiths/bitformat/actions/workflows/test.yml)
[![Docs](https://img.shields.io/readthedocs/bitformat?logo=readthedocs&logoColor=white)](https://bitformat.readthedocs.io/en/latest/)
[![Codacy Badge](https://img.shields.io/codacy/grade/b61ae16cc6404d0da5dbcc21ee19ddda?logo=codacy)](https://app.codacy.com/gh/scott-griffiths/bitformat/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
<!--
[![Dependents (via libraries.io)](https://img.shields.io/librariesio/dependents/pypi/bitformat?logo=libraries.io&logoColor=white)](https://libraries.io/pypi/bitformat)
&nbsp; &nbsp;
[![Pepy Total Downlods](https://img.shields.io/pepy/dt/bitformat?logo=python&logoColor=white&labelColor=blue&color=blue)](https://www.pepy.tech/projects/bitformat)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/bitformat?label=%40&labelColor=blue&color=blue)](https://pypistats.org/packages/bitformat)
-->
---------

**bitformat** is a Python module for creating, manipulating and interpreting binary data.
It also supports parsing and creating more complex binary formats.

It is from the author of the widely used [**bitstring**](https://github.com/scott-griffiths/bitstring) module.


----

## Features
* The `Bits` class represents a sequence of binary data of arbitrary length. It provides methods for creating, modifying and interpreting the data.
* The `Format` class provides a way to define a binary format using a simple and flexible syntax.
* A wide array of data types is supported with no arbitrary restrictions on length.
* Data is always stored as a contiguous array of bits.
* The core is written is Rust for efficiency.

> [!NOTE]
> To see what been added, improved or fixed, and also to see what's coming in the next version, see the [release notes](https://github.com/scott-griffiths/bitformat/blob/main/release_notes.md).

## Installation

There should be pre-built wheels available for most platforms so you can just `pip install bitformat`. If a wheel isn't available then please file a bug report and optionally take a look at the `build.sh` script.

## Documentation

* [The bitformat documentation](https://bitformat.readthedocs.io/en/latest/) includes a full reference for the library.
* [A Tour of bitformat](https://nbviewer.org/github/scott-griffiths/bitformat/blob/main/doc/bitformat_tour.ipynb) is a notebook
which gives a quick introduction to the library and some worked examples.

## Some Examples

### Creating some Bits

A variety of constructor methods are available to create `Bits`, including from binary, hexadecimal or octal strings, formatted strings, byte literals and iterables.

```pycon
>>> from bitformat import *

>>> a = Bits('0b1010')  # Create from a binary string
>>> b = Bits('u12 = 54')  # Create from a formatted string.
>>> c = Bits.from_bytes(b'\x01\x02\x03')  # Create from a bytes or bytearray object.
>>> d = Bits.from_dtype('f16', -0.75)  # Pack a value into a data type.
>>> e = Bits.from_joined([a, b, c, d])  # The best way to join lots of bits together.
```

### Interpreting those Bits

Although the examples above were created from a variety of data types, the `Bits` instance doesn't retain any knowledge of how it was created - it's just a sequence of bits.
You can therefore interpret them however you'd like:

```pycon
>>> a.i
-6
>>> b.hex
'036'
>>> c.unpack(['u4', 'f16', 'u4'])
[0, 0.0005035400390625, 3]
>>> d.bytes
b'\xba\x00'
```

The `unpack` method is available as a general-case way to unpack the bits into a single or multiple data types.
If you only want to unpack to a single data type you can use properties of the `Bits` as a short-cut.

### Data types

A wide range of data types are supported. These are essentially descriptions on how binary data can be converted to a useful value. The `Dtype` class is used to define these, but usually just the string representation can be used.

Some example data type strings are:

* `'u3'` - a 3 bit unsigned integer.
* `'i_le32'` - a 32 bit little-endian signed integer.
* `'f64'` - a 64 bit IEEE float. Lengths of 16, 32 and 64 are supported.
* `'bool'` - a single bit boolean value.
* `'bytes10'` - a 10 byte sequence.
* `'hex'` - a hexadecimal string.
* `'bin'` - a binary string.
* `'[u8; 40]'` - an array of 40 unsigned 8 bit integers.

Byte endianness for floating point and integer data types is specified with `_le`, `_be` and `_ne` suffixes to the base type. 

### Bit operations

An extensive set of operations are available to query `Bits` or to create new ones. For example:

```pycon
>>> a + b  # Concatenation
Bits('0xa036')
>>> c.find('0b11')  # Returns found bit position
22
>>> b.replace('0b1', '0xfe')
Bits('0x03fbf9fdfc')
>>> b[0:10] | d[2:12]  # Slicing and logical operators
Bits('0b1110101101')
```

### Arrays

An `Array` class is provided which stores a contiguous sequence of `Bits` of the same data type.
This is similar to the `array` type in the standard module of the same name, but it's not restricted to just a dozen or so types.

```pycon
>>> r = Array('i5', [4, -3, 0, 1, -5, 15])  # An array of 5 bit signed ints
>>> r -= 2  # Operates on each element
>>> r.unpack()
[2, -5, -2, -1, -7, 13]
>>> r.dtype = 'u6'  # You can freely change the data type
>>> r
Array('u6', [5, 47, 55, 60, 45])
>>> r.to_bits()
Bits('0b000101101111110111111100101101')
```

### A `Format` example

The `Format` class can be used to give structure to bits, as well as storing the data in a human-readable form.

```pycon
>>> f = Format('(width: u12, height: u12, flags: [bool; 4])')
>>> f.pack([320, 240, [True, False, True, False]])
Bits('0x1400f0a')
>>> print(f)
(
    width: u12 = 320
    height: u12 = 240
    flags: [bool; 4] = (True, False, True, False)
)
>>> f['height'].value /= 2
>>> f.to_bits()
Bits('0x140078a')
>>> f.to_bits() == 'u12=320, u12=120, 0b1010'
True
```

The `Format` and its fields can optionally have names (the `Format` above is unnamed, but its fields are named).
In this example the `pack` method was used with appropriate values, which then returned a `Bits` object.
The `Format` now contains all the interpreted values, which can be easily accessed and modified.

The final line in the example above demonstrates how new `Bits` objects can be created when needed by promoting other types, in this case the formatted string is promoted to a `Bits` object before the comparison is made.

The `Format` can be used symmetrically to both create and parse binary data:

```pycon
>>> f.parse(b'x\x048\x10')
28
>>> f
Format([
    'width: u12 = 1920',
    'height: u12 = 1080',
    'flags: [bool; 4] = (False, False, False, True)'
])
```

The `parse` method is able to lazily parse the input bytes, and simply returns the number of bits that were consumed. The actual values of the individual fields aren't calculated until they are needed, which allows large and complex file formats to be efficiently dealt with.

## More to come

The `bitformat` library is still in beta and is being actively developed.
The first release was in September 2024, with the second arriving in January 2025 and the third in April. More features are being added steadily.

There are a number of important features planned, some of which are from the `bitstring` library on which much of the core is based, and others are needed for a full binary format experience.

The (unordered) :todo: list includes:


* **~~Streaming methods~~.**  :sparkles: Done in v0.2 - see the `Reader` class :sparkles: .
* **~~Field expressions~~.**  :sparkles: Done in v0.3 :sparkles:  Rather than hard-coding everything in a field, some parts will be calculated during the parsing process. For example in the format `'(w: u16, h: u16, [u8; {w * h}])'` the size of the `'u8'` array would depend on the values parsed just before it.
* **~~New field types~~.** :sparkles: Done in v0.3 :sparkles:  Fields like `Repeat` and `If` are planned which will allow more flexible formats to be written.
* **Exotic floating point types.** In `bitstring` there are a number of extra floating point types such as `bfloat` and the MXFP 8, 6 and 4-bit variants. These will be ported over to `bitformat`.
* **Performance improvements.** A primary focus on the design of `bitformat` is that it should be fast. Early versions won't be well optimized, but tests so far are quite promising, and the design philosophy should mean that it can be made even more performant later.
* **LSB0.** Currenlty all bit positions are done with the most significant bit being bit zero (MSB0). I plan to add support for least significant bit zero (LSB0) bit numbering as well.

<sub>Copyright (c) 2024-2025 Scott Griffiths</sub>
