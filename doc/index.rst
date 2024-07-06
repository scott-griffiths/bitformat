
.. currentmodule:: bitformat

.. warning::
    This library is in the planning stages.
    The API will be very unstable and I do not recommend its use for anything serious.

    This documentation may in places be more aspirational than accurate.


.. image:: bitformat_logo.png
   :width: 400px

`bitformat <https://github.com/scott-griffiths/bitformat/>`_ is a Python module for creating and parsing file formats, especially at the bit rather than byte level.

It is intended to complement the `bitstring <https://github.com/scott-griffiths/bitstring>`_ module from the same author, and uses its `Dtype <https://bitstring.readthedocs.io/en/latest/dtypes.html#dtypes>`_, `Bits <https://bitstring.readthedocs.io/en/latest/bits.html#bits>`_ and `Array <https://bitstring.readthedocs.io/en/latest/array.html#array>`_ classes as the basis for building complex bit formats.

Features
^^^^^^^^
* A bitformat is a specification of a binary format using fields that can say how to build it from supplied values, or how to parse binary data to retrieve those values.
* A wide array of data types is supported.  Want to use a 13 bit integer or an 8-bit float? Fine - there are no special hoops to jump through.
* Several field types are available:

  * The simplest is just a `Field` which contains a single data type, and either a single value or an array of values. These can usually be constructed from just a string.
  * A `Format` contains a list of other fields. These can be nested to any depth.
  * [Coming soon] Fields like `Repeat`, `Find` and `Condition` can be used to add more logical structure.
* The values of other fields can be used in later calculations via an f-string-like expression syntax.
* Data is always stored efficiently as a contiguous array of bits.

An Example
^^^^^^^^^^

A quick example to whet the appetite: the MPEG-2 video standard specifies a 'sequence_header' that could be defined in bitformat by ::

    seq_header = Format(['sequence_header_code: const hex32 = 0x000001b3',
                         'horizontal_size_value: u12',
                         'vertical_size_value: u12',
                         'aspect_ratio_information: u4',
                         'frame_rate_code: u4',
                         'bit_rate_value: u18',
                         'marker_bit: bool',
                         'vbv_buffer_size_value: u10',
                         'constrained_parameters_flag: bool',
                         'load_intra_quantizer_matrix: bool',
                         Repeat('{load_intra_quantizer_matrix}',
                             'intra_quantizer_matrix: [u8; 64]'),
                         'load_non_intra_quantizer_matrix bool',
                         Repeat('{load_non_intra_quantizer_matrix}',
                             'non_intra_quantizer_matrix: [u8; 64]'),
                         Find('0x000001')
                         ], 'sequence_header')

To parse such a header you can write simply ::

    seq_header.parse(some_bytes_object)

then you can access and modify the field values ::

    seq_header['bit_rate_value'].value *= 2

before rebuilding the binary object ::

    b = seq_header.build()

Installation and download
^^^^^^^^^^^^^^^^^^^^^^^^^
I am planning on a minimal viable product release by April 2024, with a fuller release later in the year.
If you wish to try it out now then I recommend installing from the main branch on GitHub as that will be far ahead of the release on PyPI. ::

    pip install git+https://github.com/scott-griffiths/bitformat

To download the module, as well as for defect reports, enhancement requests and Git repository browsing go to `the project's home on GitHub. <https://github.com/scott-griffiths/bitformat/>`_



Documentation
^^^^^^^^^^^^^

.. toctree::
   :hidden:

   self

.. toctree::

    quick_reference
    manual
    api


These docs are styled using the `Piccolo theme <https://github.com/piccolo-orm/piccolo_theme>`_.


