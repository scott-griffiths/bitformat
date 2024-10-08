.. currentmodule:: bitformat
.. _introduction:

Introduction
============

Working with binary data in Python can be straight-forward. The built-in `bytes <https://docs.python.org/3/library/stdtypes.html#bytes>`_ and `bytearray <https://docs.python.org/3/library/stdtypes.html#bytearray>`_ types can be used to store binary data, and the `struct <https://docs.python.org/3/library/struct.html#module-struct>`_ module can be used to pack and unpack binary data into Python objects.
If all you need to do is simple manipulation of whole byte binary data then these tools are usually sufficient.

Sometimes you might need to deal with things that are not a whole number of bytes long, or use binary formats beyond those that can be represented by the `struct` module.
There are a few third-party packages that can help with this, for example `bitstring <https://pypi.org/project/bitstring/>`_ and `bitarray <https://pypi.org/project/bitarray/>`_ are well established libraries for working with arbitrary length binary data. For dealing with binary formats the `construct <https://pypi.org/project/construct/>`_ library is well regarded.
These libraries all have their strengths and weaknesses, and I am personally well aware of the good and bad points of `bitstring` in particular as I have been writing and maintaining it since 2006.

The `bitformat` library has the lofty ambition to be as expressive as `bitstring`, as efficient as `bitarray`, and as powerful as `construct`.
I don't yet know if it will succeed, but the early alpha versions are already quite usable, with most of the future work needed to build out the support for formats. I'm happy for feedback from any early adopters, but if you don't want to use a library still in alpha then any of the above libraries are good choices.

.. note::

    ``bitformat`` vs. ``bitstring``

    bitformat is from the same author as the `bitstring <https://github.com/scott-griffiths/bitstring>`_ package, which is widely used and has been actively maintained since 2006.
    It covers much of the same ground, but is designed to have a stronger emphasis on performance, a simpler API and a more expressive syntax for binary formats.

    ``bitstring``

    * Simple and flexible syntax for binary data manipulation.
    * Reasonable performance, but difficult to improve further.
    * Very mature and stable - maintained since 2006.
    * Hundreds of dependant projects and millions of downloads per month.


    ``bitformat``

    * Expressive syntax for complex binary formats.
    * Emphasis on performance.
    * Several major features still to be added.
    * In alpha stage - still quite unstable.

    I am hoping that ``bitformat`` will become a worthy successor, but even if ``bitformat`` is successful I plan to support ``bitstring`` indefinitely - at the time of writing their respective download counts are 88 million for bitstring and 882 for bitformat!

    There are many similarities between bitformat and bitstring, but there has been no attempt to make them compatible.
    Much of the reason for making a new package was to revisit many of the design decisions that were made almost two
    decades ago when George W. Bush was president, the Nintendo Wii was the latest must-have tech, and Python 2.4 was the latest version.


This introduction will start with a brief tour of the main features of `bitformat`, followed by a more in depth look at the main classes.
For more thorough documentation see the :ref:`API reference<api>`.

TLDR;
-----

The most fundamental classes in `bitformat` are the :class:`Bits` class, which just stores bits, and the :class:`Dtype` (data type) class which says how those bits should be interpreted.

The binary data can be any length, and is immutable once created. The data types include binary and hexadecimal strings, integers, floats, bit and bytes literals, and more.

A common theme amongst the classes provided by `bitformat` is that most can be constructed from a string.
The principal classes all have constructor methods called ``from_string`` and the ``__init__`` method just redirects to the ``from_string`` method. This allows for some very concise code, while keeping the flexibility to construct objects more programmatically.

Some examples creating ``Bits`` from strings::

    a = Bits('0b110')  # 3 bits long from a binary string
    b = Bits('0xabc')  # 12 bits long from a hex string
    c = Bits('f16 = 3.8')  # A 16 bit IEEE float
    d = Bits('u6 = 0')  # A 6 bit unsigned integer

and the same values created with other methods::

    a = Bits.pack('bin', '110')
    b = Bits.from_string('0xabc')
    c = Bits.pack('f16', 3.8)
    d = Bits.zeros(6)

Once created they are all just binary data, so can be interpreted as any other data type. For example::

    >>> a.unpack('i3')  # A 3 bit signed integer
    -2
    >>> c.unpack('hex4')  # 4 characters of hexadecimal
    '439a'

The strings such as ``'i3'`` used here are another example of strings being promoted to the appropriate types.
Instead of ``'i3'`` we could have written ``Dtype('i3')`` or even more verbosely ``Dtype.from_params('i', 3)``.
There is also a way to be even more concise when unpacking the whole of a :class:`Bits` as a single :class:`Dtype`, which is to use the dtype name as a property::

    >>> a.i
    -2
    >>> c.hex
    '439a'

As well as packing and unpacking bits with a dtype, you can also equivalently pack and unpack a dtype with bits::

    >>> Dtype('i3').pack(-2)
    Bits('0110')
    >>> Dtype('f16').unpack('0x439a')
    3.80078125

Here the value of ``-2`` was packed into a 3 bit signed integer ``Dtype`` to create a 3 bit ``Bits`` object.
Then a 16 bit ``Bits`` was implicitly created from the hexadecimal string ``'0x439a'`` and unpacked as a 16 bit IEEE float value.

A very convenient feature is 'auto' initialisation, where various types will be promoted to a :class:`Bits` when appropriate.
This has already happened in some of the examples above, but some more examples are::

    >>> b = Bits.from_bytes(b'some') + b'more'
    >>> b.replace('0b01', '0b0')
    Bits('0x6575214bb08')
