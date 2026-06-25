.. currentmodule:: bitformat
.. _tldr:


TLDR;
-----

The most fundamental classes in `bitformat` are the :class:`Tibs` class, which just stores bits, and the :class:`Dtype` (data type) class which says how those bits should be interpreted.

The binary data can be any length, and is immutable once created. The data types include binary and hexadecimal strings, integers, floats, bit and bytes literals, and more.

A common theme amongst the classes provided by `bitformat` is that most can be constructed from a string.
The principal classes all have constructor methods called ``from_string`` and the ``__init__`` method just redirects to the ``from_string`` method. This allows for some very concise code, while keeping the flexibility to construct objects more programmatically.

Some examples creating ``Tibs`` from literals and bitformat data types::

    a = Tibs('0b110')  # 3 bits long from a binary string
    b = Tibs('0xabc')  # 12 bits long from a hex string
    c = Tibs.from_dtype('f16', 3.8)  # A 16 bit IEEE float
    d = Tibs.from_dtype('u6', 0)  # A 6 bit unsigned integer

and the same values created with other methods::

    a = Tibs.from_dtype('bin', '110')
    b = Tibs.from_string('0xabc')
    c = Tibs.from_dtype('f16', 3.8)
    d = Tibs.from_zeros(6)

Once created they are all just binary data, so can be interpreted as any other data type. For example::

    >>> a.unpack('i3')  # A 3 bit signed integer
    -2
    >>> c.unpack('hex4')  # 4 characters of hexadecimal
    '439a'

The strings such as ``'i3'`` used here are another example of strings being promoted to the appropriate types.
Instead of ``'i3'`` we could have written ``Dtype('i3')`` or even more verbosely ``Dtype.from_params('i', 3)``.
There is also a way to be even more concise when unpacking the whole of a :class:`Tibs` as a single :class:`Dtype`, which is to use the dtype name as a property::

    >>> a.i
    -2
    >>> c.hex
    '439a'

As well as packing and unpacking bits with a dtype, you can also equivalently pack and unpack a dtype with bits::

    >>> Dtype('i3').pack(-2)
    Tibs('0110')
    >>> Dtype('f16').unpack('0x439a')
    3.80078125
    >>> Dtype('u1, u2, u3, u4').pack([1, 1, 1, 1])
    Tibs('0b1010010001')
    >>> Dtype('hex2, u4, [bool; 4]').unpack('0x439a')
    ['43', 9, (True, False, True, False)]

Here the value of ``-2`` was packed into a 3 bit signed integer ``Dtype`` to create a 3 bit ``Tibs`` object.
Then a 16 bit ``Tibs`` was implicitly created from the hexadecimal string ``'0x439a'`` and unpacked as a 16 bit IEEE float value. Packing and unpacking multiple values in one go can also be done.

A very convenient feature is 'auto' initialisation, where various types will be promoted to a :class:`Tibs` when appropriate.
This has already happened in some of the examples above, but some more examples are::

    >>> b = Tibs.from_bytes(b'some') + b'more'
    >>> b.replaced('0b01', '0b0')
    Tibs('0x6575214bb08')
