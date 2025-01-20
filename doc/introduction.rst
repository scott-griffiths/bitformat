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
For more exhaustive documentation see the :ref:`API reference<api>`.

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

    a = Bits.from_dtype('bin', '110')
    b = Bits.from_string('0xabc')
    c = Bits.from_dtype('f16', 3.8)
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
    >>> DtypeTuple('u1, u2, u3, u4').pack([1, 1, 1, 1])
    Bits('0b1010010001')
    >>> DtypeTuple('hex2, u4, [bool; 4]').unpack('0x439a')
    ['43', 9, (True, False, True, False)]

Here the value of ``-2`` was packed into a 3 bit signed integer ``Dtype`` to create a 3 bit ``Bits`` object.
Then a 16 bit ``Bits`` was implicitly created from the hexadecimal string ``'0x439a'`` and unpacked as a 16 bit IEEE float value. For packing and unpacking multiple values in one go the :class:`DtypeTuple` class is available.

A very convenient feature is 'auto' initialisation, where various types will be promoted to a :class:`Bits` when appropriate.
This has already happened in some of the examples above, but some more examples are::

    >>> b = Bits.from_bytes(b'some') + b'more'
    >>> b.replace('0b01', '0b0')
    Bits('0x6575214bb08')


Common Use Cases
================

Case 1: Constructing binary data from data types with values
------------------------------------------------------------

You have some values of a particular type, say an integer or a floating point format, and you want to store them as binary data.

a) A simple Dtype
^^^^^^^^^^^^^^^^^

The simplest data types are just a type and a length. Things like ``'i16'`` for a 16 bit signed integer, or ``'f32'`` for a 32 bit floating point number.
Actually some types are even simpler as they don't need the length - a ``'bool'`` is always a single bit. ::

    >>> b = Bits.from_dtype('u12', 160)
    >>> b.u
    160
    >>> b.bin
    '000010100000'
    >>> b.hex
    '0a0'

Here we create a :class:`Bits` object using a :class:`Dtype` constructed from the ``'u12'`` string, and give it the value of 160.
There are some convenient properties of the ``Bits`` object that allow it to be converted back into a value by interpreting it with a new data type.
In this case we first used the ``u`` property to check that when interpreted as an unsigned integer it is indeed the value we expect. Then the ``bin`` and ``hex`` properties emphasis that this is indeed an object representing a 12-bit sequence.

Once the ``Bits`` is created it is just a collection of bits, and has no way of knowing how it was created, so all of these interpretations are equally true and valid.

The properties used above are useful and convenient but not very general. The more general way of seeing the value would be to use the :meth:`Bits.unpack` method. ::

    >>> b.unpack('u')
    160

You can also construct from literal binary, octal or hexadecimal values::

    >>> p = Bits.from_dtype('bin', '001')
    >>> q = Bits.from_dtype('hex', 'beef')

There are several class constructor methods available to create ``Bits`` objects. As well as :meth:`Bits.from_dtype` there are :meth:`Bits.from_bytes`, :meth:`Bits.from_bools`, :meth:`Bits.from_joined`, :meth:`Bits.from_zeros`, :meth:`Bits.from_ones` and :meth:`Bits.from_string`.

Creating from a formatted string is often very convenient::

    >>> b = Bits.from_string('u12 = 160')
    >>> p = Bits.from_string('bin = 001')
    >>> q = Bits.from_string('hex = beef')

It's so frequently used that the default constructor for ``Bits`` is just an alias for the :meth:`Bits.from_string` method. Add to that the short-cut of using a ``'0b'`` prefix for binary and ``'0x'`` for hexadecimal, you can instead write ::

    >>> b = Bits('u12 = 160')
    >>> p = Bits('0b001')
    >>> q = Bits('0xbeef')


To get back from the ``Bits`` object to a Python-native object you can use the :meth:`Bits.to_bytes` method::

    >>> q.to_bytes()
    b'\xbe\xef'

Note that if your ``Bits`` is not a whole number of bytes long then this method will add up to seven zero bits to make it a whole-byte quantity.
If you are doing lots of bit manipulation work then converting to bytes is often the final stage.


b) An array Dtype
^^^^^^^^^^^^^^^^^

You can also have a data type that represents an fixed-size array of simple data types. For example you might want to have a group of boolean flags, or a chunk of binary data as ``'u8'`` bytes. Note that this shouldn't be confused with the :class:`Array` class, which is a higher level mutable container that we'll come to later.

The format strings for these are borrowed from the Rust programming language::

    >>> a = Bits.from_dtype('[u8; 5]', (104, 101, 108, 108, 111))
    >>> f = Bits.from_dtype('[bool; 4]', [True, True, False, True])

The :class:`Dtype` made from the string ``'[u8; 5]'`` represents an array of five 8-bit unsigned integers, and ``'[bool; 4]'`` is an array of four single bit booleans.
Of course these array data types also work when unpacking::

    >>> a.unpack('[i4; 10]')
    (6, -8, 6, 5, 6, -4, 6, -4, 6, -1)

where we have chosen to unpack the 40 bits of data as ten signed 4 bit integers.

c) A sequence of Dtypes
^^^^^^^^^^^^^^^^^^^^^^^

The array Dtype above can only be used for a sequence of data types that are the same. You can also mix and match data types in a :class:`DtypeTuple`. ::

    >>> dt = DtypeTuple('[bool; 4], u12, u12')
    >>> t = Bits.from_dtype(dt, [[1, 1, 0, 1], 160, 120])
    >>> t.bin
    '1101000010100000000001111000'

We've been a bit more explicit when creating the ``DtypeTuple`` here, as we could have just supplied the initialisation string to the ``from_dtype`` method and it would have worked just as well. We are going to use the data type again though, so creating the ``DtypeTuple`` object means it won't have to parse the string more than once ::

    >>> t.unpack(dt)
    [(True, True, False, True), 160, 120]


d) A format specification
^^^^^^^^^^^^^^^^^^^^^^^^^

For more complex needs the :class:`Format` class allows a rich specification language that we'll only touch upon in this section.

Combining some of our earlier creations we could make this format::

    >>> fmt = Format("header = (const hex4 = 0x0147, flags: [bool; 4], w: u12, h: u12)")
    >>> print(fmt)
    header = (
        const hex4 = 0147
        flags: [bool; 4]
        w: u12
        h: u12
    )

Here we have introduced named fields and const fields. It's then easy to set and get the named fields::

    >>> fmt['flags'].value = [1, 1, 0, 1]
    >>> fmt['w'].value = 160
    >>> fmt['h'].value = 120
    >>> print(fmt)
    header = (
        const hex4 = 0147
        flags: [bool; 4] = (True, True, False, True)
        w: u12 = 160
        h: u12 = 120
    )
    >>> fmt.unpack()
    ['0147', (True, True, False, True), 160, 120]
    >>> fmt.to_bytes()
    b'\x01G\xd0\xa0\x07\x80'


Another way to create using the format is via the :meth:`Format.pack` method::

    >>> fmt.clear()
    >>> fmt.pack([[0, 0, 0, 0], 999, 5])
    >>> print(fmt)
    header = (
        const hex4 = 0147
        flags: [bool; 4] = (False, False, False, False)
        w: u12 = 999
        h: u12 = 5
    )


Case 2: Manipulating binary data
--------------------------------

The :class:`Bits` class represents an immutable container of bits. In much the same way as a standard Python ``bytes`` contains immutable bytes and ``str`` contains immutable characters.

Case 3: Querying values contained in a binary format
----------------------------------------------------
