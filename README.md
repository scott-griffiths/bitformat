> :warning: **This project is currently in the planning stage. The documentation is only partially accurate and there are lots of bugs and missing features!**

[![bitformat](https://raw.githubusercontent.com/scott-griffiths/bitformat/main/doc/bitformat_logo_small.png)](https://github.com/scott-griffiths/bitformat)

[![CI badge](https://github.com/scott-griffiths/bitformat/actions/workflows/.github/workflows/ci.yml/badge.svg)](https://github.com/scott-griffiths/bitformat/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/readthedocs/bitformat?logo=readthedocs&logoColor=white)](https://bitformat.readthedocs.io/en/latest/)
[![Dependents (via libraries.io)](https://img.shields.io/librariesio/dependents/pypi/bitformat?logo=libraries.io&logoColor=white)](https://libraries.io/pypi/bitformat)
[![Codacy Badge](https://img.shields.io/codacy/grade/8869499b2eed44548fa1a5149dd451f4?logo=codacy)](https://app.codacy.com/gh/scott-griffiths/bitstring/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
&nbsp; &nbsp;
[![Pepy Total Downlods](https://img.shields.io/pepy/dt/bitformat?logo=python&logoColor=white&labelColor=blue&color=blue)](https://www.pepy.tech/projects/bitformat)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/bitformat?label=%40&labelColor=blue&color=blue)](https://pypistats.org/packages/bitformat)

---------

**bitformat** is a Python module for creating and parsing file formats, especially at the bit rather than byte level.

It is intended to complement the [**bitstring**](https://github.com/scott-griffiths/bitstring) module from the same author, and uses its `Dtype`, `Bits` and `Array` classes as the basis for building complex bit formats.



----

Features
--------
* A bitformat is a specification of a binary format using fields that can say how to build it from supplied values, or how to parse binary data to retrieve those values.
* A wide array of data types is supported.  Want to use a 13 bit integer or an 8-bit float? Fine - there are no special hoops to jump through.
* Several field types are available:
  * The simplest is just a `Field` which contains a single data type, and either a single value or an array of values. These can usually be constructed from just a string. 
  * A `Format` contains a list of other fields. These can be nested to any depth.
  * Fields like `Repeat`, `Find` and `Condition` can be used to add more logical structure.
* The values of other fields can be used in later calculations via an f-string-like expression syntax.
* Data is always stored efficiently as a contiguous array of bits.

An Example
----------

A quick example to whet the appetite: the MPEG-2 video standard specifies a 'sequence_header' that could be defined in bitformat by

    seq_header = Format(['hex32 <sequence_header_code> = 0x000001b3',
                         'u12   <horizontal_size_value>',
                         'u12   <vertical_size_value>',
                         'u4    <aspect_ratio_information>',
                         'u4    <framte_rate_code>',
                         'u18   <bit_rate_value>',
                         'bool  <marker_bit>',
                         'u10   <vbv_buffer_size_value>',
                         'bool  <constrained_parameters_flag>',
                         'bool  <load_intra_quantizer_matrix>',
                         Repeat('{load_intra_quantizer_matrix}',
                             'u8 * 64 <intra_quantizer_matrix>'),
                         'bool  <load_non_intra_quantizer_matrix>',
                         Repeat('{load_non_intra_quantizer_matrix}',
                             'u8 * 64 <non_intra_quantizer_matrix>'),
                         Find('0x000001')
                         ], 'sequence_header')

To parse such a header you can write simply

    seq_header.parse(some_bytes_object)

then you can access and modify the field values

    seq_header['bit_rate_value'].value *= 2

before rebuilding the binary object

    b = seq_header.build()


<sub>Copyright (c) 2024 Scott Griffiths</sub>
