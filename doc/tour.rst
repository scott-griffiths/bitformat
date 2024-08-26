
A Tour of bitformat
===================

A number of classes are available in bitformat to store and manipulate binary data.

* ``Bits`` - An immutable container of binary data.
* ``Dtype`` - A data type that gives an interpretation to binary data.
* ``Array`` - A container for contiguously allocated `Bits` objects with the same `Dtype`.

These are the building blocks for more complex fields that can be used to make a binary format.

* ``Field`` - Either one value or an array, with a single data type, with an optional name and value.
* ``Format`` - A sequence of other FieldTypes, with an optional name.

For this quick tour we'll assume that `bitformat` has been installed (``pip install bitformat``) and these classes have all been imported::

    from bitformat import Bits, Dtype, Array, Field, Format

Bits
----

The ``Bits`` class represents an immutable sequence of bits, similar to how the built-in ``bytes`` is an immutable sequence of bytes,
and a ``str`` is an immutable sequence of characters.

There are several builder class methods used to create ``Bits`` objects.

.. list-table::
   :header-rows: 1

   * - Method name
     - Description
   * - ``Bits.pack(dtype, value)``
     - Combine a data type with a value.
   * - ``Bits.from_string(s)``
     - Use a formatted string.
   * - ``Bits.from_bytes(b)``
     - Directly from a ``bytes`` object.
   * - ``Bits.from_iterable(i)``
     - Converts each element to a single bit.
   * - ``Bits.zeros(n)``
     - Initialise with zero bits.
   * - ``Bits.ones(n)``
     - Initialise with one bits.
   * - ``Bits.join(iterable)``
     - Concatenate from an iterable such as a list.

The ``Bits`` constructor can be used as a shortcut for the ``from_string`` method, so ``Bits(s)`` and ``Bits.from_string(s)`` are equivalent.

Creating from a string is often convenient and quite powerful.
The string can be a binary, octal or hexadecimal literal by starting with ``'0b'``, ``'0o'`` or ``'0x'`` respectively.
It can be a string that uses various data types of integer or floating point values, and it can be a sequence of tokens separated by commas. ::

    a = Bits('0b110')  # A 3-bit binary string
    b = Bits('0xabcde')  # A 20-bit hexadecimal string
    d = Bits('f32=13.5')  # A 32-bit IEEE floating point number
    e = Bits('i7=-31')  # A 7-bit signed integer
    f = Bits('0b001, u32=90, 0x5e')  # Three Bits objects concatenated together

Finally a data type can be used to create a `Bits` object by using the `pack` class method. ::

    g = Bits.pack('u8', 65)  # An 8-bit unsigned integer with the value 65
    h = Bits.pack('hex', 'abcde')  # A 20-bit hexadecimal string
    i = Bits.pack('bytes', b'hello')  # A 40-bit binary string
    j = Bits.pack('f16', -13.81)  # A 16-bit IEEE floating point number

The first parameter of ``pack`` is the data-type, which can be either a ``Dtype`` or a string that can be used to create one.
The second parameter is a value that makes sense for that data type, which could be a binary string, a floating point number, an integer etc. depending on the ``Dtype``.

Once you've created your ``Bits`` object there is a rich API for manipulating and interpreting the data.
One fundamental thing to do is to interpret the binary data according to a format or data-type; essentially the opposite to how the ``pack`` method works. ::

    g.unpack(['u8'])  # Returns [65]
    h.unpack(['hex'])  # Returns ['abcde']

The ``unpack`` method is quite powerful and is a bit of a sledgehammer for these simple cases, so as a shortcut you can use properties that are available for simple dtypes. ::

    g.u8  # Returns 65
    h.hex  # Returns 'abcde'

Of course the ``Bits`` object is just a collection of bits and doesn't know how it was created, so any interpretation that makes sense is allowed ::

    >>> a.unpack('oct')
    ['6']
    >>> b.unpack('u')  # unsigned int
    TODO
    >>> c.unpack('f64')
    TODO
    >>> d.unpack('hex')
    TODO
    >>> e.unpack('bin')
    TODO


In places where a ``Bits`` is expected, a formatted string that can be used to more conveniently create the `Bits` object.
For example, if ``a`` is a ``Bits`` object, instead of ::

    a += Bits.pack('u8', 65)

you can equivalently write ::

    a += 'u8 = 65'

Some examples of strings that can be converted to `Bits` objects:

* ``'0b00110'``: A binary string.
* ``'0x3fff0001'``: A hexadecimal string.
* ``'i15=-401'``: A 15 bit signed integer representing the number -401.
* ``'f64=1.3e5'``: A 64 bit floating point number representing 130000.
* ``'0b001, u32=90, 0x5e'``: A sequence of bits that represent a 3-bit binary number, a 32-bit unsigned integer and a 8-bit hexadecimal number.

Dtype
-----

The dtype (or data type) gives an interpretation to binary data.
Most of these have a type and a bit-length, and are usually created when needed from a string as in the previous section.

For example the data-type representing an unsigned integer of length 4 bits can be created by either ``Dtype('u', 4)`` or by using the string ``'u4'`` when a `Dtype` is required as a parameter.

Some examples of the data-types names available are:

.. list-table::
   :widths: 10 30
   :header-rows: 1

   * - Dtype string
     - Description
   * - ``'u10'``
     - A 10-bit unsigned integer
   * - ``'i7'``
     - A 7-bit signed two's complement integer
   * - ``'f32'``
     - A 32-bit IEEE floating point number
   * - ``'bin4'``
     - A 4-bit binary string
   * - ``'hex12'``
     - A 12-bit hexadecimal string (i.e. 3 hex characters)
   * - ``'bool'``
     - A single bit boolean
   * - ``'bits5'``
     - A Bits instance of length 5 bits
   * - ``'bytes20'``
     - 20 bytes of data
   * - ``'pad8'``
     - Pad bits that have no interpretation

Note that there are no unnatural restrictions on the length of a dtype.
If you want a 3-bit integer or 1001 padding bits then that's as easy to do as any other length.


Array
-----

The `Array` class is used as a container for contiguously allocated `Bits` objects with the same `Dtype`.

`Array` instances act very like an ordinary Python array, but with each element being a fixed-length dtype.



----

A bitformat is a specification of a binary format that says both how to build it from supplied values, and how to parse binary data to retrieve those values.


FieldType
---------

A ``FieldType`` is an abstract base class for all of the other classes in this section.
It could represent a single piece of data, it could be a container for other `FieldType` objects or it could represent an action or decision.
You shouldn't need to deal with this type directly but its methods are available for all of the other field types.

Methods

.. class:: FieldType()

      .. method:: FieldType.build(values: list[Any], kwargs: dict) -> Bits

        Given positional and keyword values, fill in the any empty field(s) and build a `Bits` object.
        Note that this modifies the fieldtype in-place.

      .. method:: FieldType.parse(b: Bits | bytes | bytearray) -> int

        Takes a `Bits` object, parses it according to the field structure and returns the number of bits used.
        Note that this modifies the fieldtype in-place.

      .. method:: FieldType.flatten() -> list[FieldType]

        Removes any nesting of fields and returns a flat list of FieldsTypes.

      .. method:: FieldType.to_bits() -> Bits

        Converts the contents to a `Bits` bit literal.

      .. method:: FieldType.to_bytes() -> bytes

        Converts the contents to a `bytes` object.
        Between 0 and 7 zero bits will be added at the end to make it a whole number of bytes long.

      .. method:: FieldType.vars() -> tuple[list[Any], dict]

        Returns the positional and keyword values that are contained in the field.

      .. method:: FieldType.clear() -> None

        Sets the `value` of everything that is not const to `None`.

      .. property:: value: Any

        A property to get and set the value of the field.
        For example with a simple ``Field`` representing an integer this would return an integer; for a ``Format`` this would return a list of the values of each field in the ``Format``.

      .. property:: name: str

        Every `FieldType` has a name string, which must be either an empty string or a valid Python identifier.
        It also must not contain a double underscore (``__``).
        The name can be used to refer to the contents of the `FieldType` from within another `FieldType`.


Field
-----

A `Field` is the fundamental building block in `bitformat`.
It represents a well-defined amount of binary data with a single data type.

.. class:: Field(dtype: Dtype | str, name: str = '', value: Any = None, items: int | str = 1, const: bool | None = None)
    :no-index:

    A `Field` has a data type (`dtype`) that describes how to interpret binary data and optionally a `name` and a concrete `value` for the `dtype`.

    ``dtype``: The data type can be either:
        * A `Dtype` object (e.g. ``Dtype('f', 16)``).
        * A string that can be used to construct a `Dtype` (e.g. ``'f16'``).

    ``name``: An optional string used to identify the `Field`.
    It must either be a valid Python identifier (a string that could be used as a variable name) or the empty string ``''``.

    ``value``: A value can be supplied for the ``Dtype`` - this should be something suitable for the type, for example you can't give the value of ``2`` to a ``bool``, or ``123xyz`` to a ``hex`` dtype.
    If a `value` is given then the `const` parameter will default to `True`.

    ``items``: An array of items of the same dtype can be specified by setting `items` to be greater than one.

    ``const``: By default fields do not have a single set value - the value is deduced by parsing a binary input.
    You can declare that a field is a constant bit literal by setting `const` to `True` - this means that it won't need its value set when building, and will require the correct value present when parsing.
    You can only set `const` to `True` when creating a field if you also provide a value.

    .. classmethod:: from_bits(bits: Bits | str | bytes | bytearray) -> Field
        :no-index:

        For convenience you can also construct either a `Bits` object, a ``bytes`` or ``bytearray``, or a string that can be used to construct a `Bits` object (e.g. ``'0x47'``).
        This will will cause the `dtype` to be set to ``Dtype('bits')`` and the `value` to be set to the `Bits` object.
        Setting a bit literal in this way will cause the `const` parameter to default to `True`.

    .. classmethod:: from_string(s: str, /)
        :no-index:

        Often the easiest way to construct a `Field` is to use a formatted string to set the `name`, `value` and `const` parameters - see :ref:`Field strings` below.


FieldArray
----------

An `FieldArray` field contains multiple copies of a single dtype that has a well-defined length.

.. class:: FieldArray(dtype: Dtype | str, items: int | str, name: str = '', value: Any = None, const: bool = False)
    :no-index:

The `items` parameter gives the length of the `FieldArray`.
The other parameters are the same as for the `Field` class.

This creates an array of 20 fields, each containing a 6-bit unsigned integer followed by two bools.

If you want to repeat a single field then it is usually simpler to have one field and use the `items` parameter rather than use the `FieldArray` class.
So instead of ::

    a = FieldArray(80, ['bool'])

use ::

    a = Field.from_string('[bool; 80]')

If you need to repeat fields whose lengths aren't known at the time of construction then you can use a `Repeat` field as described below.
If you have a choice then choose the `FieldArray` class over the `Repeat` class, as it is more efficient and easier to use.


.. _Field strings:

Field strings
^^^^^^^^^^^^^

As a shortcut a single string can usually be used to specify the whole `Field` or `FieldArray`.
To do this it should be a string of the format::

    "name: dtype = value"

for a `Field` or ::

    "name: [dtype; items] = value"

for a `FieldArray`.

The ``'name:'`` and ``'= value'`` parts are optional, and usually a ``'value'`` would only be specified for a field if it is a constant.

To specify a ``const`` field use either ::

    "name: const dtype = value"

for a ``Field`` or ::

    "name: const [dtype; items] = value"

for a ``FieldArray``. When ``const`` is used the `value` must be set.


For example instead of ``Field(Dtype('uint', 12), 'width', 100)`` you could say ``Field.from_string('width: u12 = 100')``.
The whitespace between the elements is optional.

An example for a bit literal would be instead of ``Field(Bits(bytes=b'\0x00\x00\x01\xb3'), 'sequence_header')`` you could use ``Field.from_string('sequence_header: bits32 = 0x000001b3')``.

This becomes more useful when the field is part of a larger structure, and the string can be used on its own to specify the field, for example::

    f = Format([
                'start_code: const hex8 = 0x47',
                'width: u12',
                'height: u12',
                '[bool; 5]'
               ])

This creates four fields within a `Format` object. The first is a named bit literal and will have the `const` flag set.
The next two are named 12 bit unsigned integer fields, and the final field is an unnamed array of five bools.


Format
------

A `Format` can be considered as a list of `FieldType` objects.
In its simplest form is could just be a flat list of ``Field`` objects, but it can also contain other ``Format`` objects and the other types described in this section.

.. class:: Format(fieldtypes: Sequence[FieldType | str] | None = None, name: str = '')
    :no-index:


Repeat
------

A `Repeat` field simply repeats another field a given number of times.

.. class:: Repeat(count: int | Iterable | str, fieldtype: FieldType | str | Dtype | Bits | Sequence[FieldType | str])

The `count` parameter can be either an integer or an iterable of integers, so for example a ``range`` object is accepted.

If you want to repeat a single dtype then it is usually better to a ``FieldArray`` rather than use the `Repeat` class.
So instead of ::

    r = Repeat(10, 'f64')  # This creates ten fields, each a 64 bit float

use ::

    r = Field.from_string('float64 * 10')  # Creates a single field with an array of ten float64


..
    Find
    ----

    .. class:: Find(bits: Bits | bytes | bytearray | str, bytealigned: bool = True, name: str = '')

    The `Find` field is used to seek to the next occurrence of a bitstring.

    :meth:`Find.parse` will seek to the start of the next occurrence of `bits`, and set `value` to be the number of bits that

    If `bytealigned` is `True` it will only search on byte boundaries.

    The optional `name` parameter is used to give the number of bits skipped a name that can be referenced elsewhere.

    :meth:`Find.build` does nothing and returns an empty `Bits` object.

    :meth:`Find.value`  returns the number of bits skipped to get to the start of the found bits.
    Note that the value will always be in bits, not bytes and that `None` will be returned if the bits could not be found.

    :meth:`Find.bits` returns an empty `Bits` and :meth:`Find.bytes` returns an empty `bytes`.

..
    Condition
    ---------

    .. class:: Condition(cond: lambda, fieldtype: [FieldType | str] | None = None, name: str = '')




Expressions
-----------

`bitformat` supports a limited evaluation syntax that looks a little like Python f-strings.
This allows the values of named fields to be reused elsewhere with little effort.

To do this, you can use braces within a string to substitute a value or expression.
This is probably easiest to explain by example::

    f = Format([
                'width: u12',
                'height: u12',
                'area: [u8; {width * height}]'
               ])

Here we have two named fields followed by an array whose size is given by the product of the other two fields.
This means that when this `Format` is used to `parse` a bitstring the amount of data it will consume depends on the `height` and `width` fields it reads in first.

The operations allowed are limited in scope, but include simple mathematical operations, indexing and boolean comparisions.
You could for example simulate an 'if' condition by using a `Repeat` field with a boolean count.
This will then be repeated either zero or one time::

    f = Format(['val: f32',
                Repeat('{val < 0.0}', [
                    'bytes16'])
                ])

The field of 16 bytes will only be present if the 32-bit float is negative, so that the condition evaluates to ``True`` which is the integer ``1``.

Expressions can be used in several places:

* To give the length of a dtype. ::

    f = Field('u{x + y}')

* As the `items` parameter in an array `Field`. ::

    f = Field('bool', items='{flag_count // 2 + 1}')

* As the `value` parameter in a `Field`. ::

    f = Field('float16', value='{(x > 0.0) * x}')

* As the `count` parameter in a `Repeat` field. ::

    f = Repeat('{i*2}', [...])


These are often most convenient when used in field-strings, for example::

    f = Format(['sync_byte: const hex8 = ff',
                'items: u16',
                'flags: [bool; {items + 1}]',
                Repeat('{items + 1}', Format([
                       'byte_cluster_size: u4',
                       'bytes{byte_cluster_size}'
                       ]), 'clusters'),
                'u8 = {clusters[0][0] << 4}'
                ])

