.. currentmodule:: bitformat

Fields, Formats and More
========================

A bitformat is a specification of a binary format that can say how to build it from supplied values, or how to parse binary data to retrieve those values.


FieldType
---------

A ``FieldType`` is an abstract base class for all of the other classes in this section.
It could represent a single piece of data, it could be a container for other `FieldType` objects or it could represent an action or decision.
Although you shouldn't need to deal with this type directly it is helpful to take a look at the methods that are common between all of the other types.


.. class:: FieldType()

      .. method:: FieldType.build(values: list[Any], kwargs: dict) -> Bits

        Given positional and keyword values, fill in the any empty field(s) and build a `Bits` object.
        Note that this modifies the fieldtype in-place.

      .. method:: FieldType.parse(b: Bits | bytes | bytearray) -> int

        Takes a `Bits` object, parses it according to the field structure and returns the number of bits used.
        Note that this modifies the fieldtype in-place.

      .. method:: FieldType.flatten() -> list[FieldType]

        Removes any nesting of fields and returns a flat list of FieldsTypes.

      .. method:: FieldType.tobits() -> Bits

        Converts the contents to a `Bits` bit literal.

      .. method:: FieldType.tobytes() -> bytes

        Converts the contents to a `bytes` object.
        Between 0 and 7 zero bits will be added at the end to make it a whole number of bytes long.

      .. method:: FieldType.vars() -> tuple[list[Any], dict]

        Returns the positional and keyword values that are contained in the field.

      .. method:: FieldType.clear() -> None

        Sets the `value` of everything that is not a marked as const to `None`.

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

    A `Field` has a data type (`dtype`) that describes how to interpret binary data and optionally a `name` and a concrete `value` for the `dtype`.

    ``dtype``: The data type can be either:
        * A `Dtype` object (e.g. ``Dtype('float', 16)``).
        * A string that can be used to construct a `Dtype` (e.g. ``'float16'``).

    ``name``: An optional string used to identify the `Field`.
    It must either be a valid Python identifier (a string that could be used as a variable name) or the empty string ``''``.

    ``value``: A value can be supplied for the ``Dtype`` - this should be something suitable for the type, for example you can't give the value of ``2`` to a ``bool``, or ``123xyz`` to a ``hex`` dtype.
    If a `value` is given then the `const` parameter will default to `True`.

    ``items``: An array of items of the same dtype can be specified by setting `items` to be greater than one.

    ``const``: By default fields do not have a single set value - the value is deduced by parsing a binary input.
    You can declare that a field is a constant bit literal by setting `const` to `True` - this means that it won't need its value set when building, and will require its value present when parsing.
    You can only set `const` to `True` when creating a field if you also provide a value.

    .. classmethod:: frombits(bits: Bits | str | bytes | bytearray) -> Field

        For convenience you can also construct either a `Bits` object, a ``bytes`` or ``bytearray``, or a string that can be used to construct a `Bits` object (e.g. ``'0x47'``).
        This will will cause the `dtype` to be set to ``Dtype('bits')`` and the `value` to be set to the `Bits` object.
        Setting a bit literal in this way will cause the `const` parameter to default to `True`.

    .. classmethod:: fromstring(s: str, /)

        Often the easiest way to construct a `Field` is to use a formatted string to set the `name`, `value`, `items` and `const` parameters - see :ref:`Field strings` below.


.. _Field strings:

Field strings
^^^^^^^^^^^^^

As a shortcut the a single string can usually be used to specify the whole field.
To do this it should be a string of the format::

    "dtype [* items] [<name>] [= value]"

You can also use ``:`` instead of ``=`` before the value, which will mean that the `Field` has a value but is not set as `const`.
This isn't usually what you want when setting a `Field` - non-const values are usually present after a bitstring has been parsed.

For example instead of ``Field(Dtype('uint', 12), 'width', 100)`` you could say ``Field.fromstring('uint12 <width> = 100')``.
The whitespace between the elements is optional.

An example for a bit literal would be instead of ``Field(Bits(bytes=b'\0x00\x00\x01\xb3'), 'sequence_header')`` you could use ``Field.fromstring('bits32 <sequence_header> = 0x000001b3')``.

This becomes more useful when the field is part of a larger structure, and the string can be used on its own to specify the field, for example::

    f = Format([
                'hex8 <start_code> = 0x47',
                'u12 <width>',
                'u12 <height>',
                'bool * 5'
               ])

This creates four fields within a `Format` object. The first is a named bit literal and will have the `const` flag set.
The next two are named 12 bit unsigned integer fields, and the final field is an unnamed array of five bools.


Format
------

A `Format` can be considered as a list of `FieldType` objects.
In its simplest form is could just be a flat list of ``Field`` objects, but it can also contain other ``Format`` objects and the other types described in this section.

.. class:: Format(fieldtypes: Sequence[FieldType | str] | None = None, name: str = '')


FieldArray
----------

An `FieldArray` field contains multiple copies of other fields that have well-defined lengths.

.. class:: FieldArray(count: int | Iterable[int] | str, fieldtypes: Sequence[FieldType | str] | None = None, name: str = '')

The `count` parameter can be either an integer or an iterable of integers, so for example a ``range`` object is accepted.
The `name` parameter is used to give the FieldArray a name that can be referenced elsewhere.

The main restriction is that every field in `fieldtypes` must have a well-defined length, so that each element in the `FieldArray` has the same length.
This means that conditional fields, fields with variable lengths or fields whose length depends on the value of another field are not allowed.

For example::

    f = FieldArray(20, ['u6', 'bool', 'bool'])

This creates an array of 20 fields, each containing a 6-bit unsigned integer followed by two bools.

If you want to repeat a single field then it is usually simpler to have one field and use the `items` parameter rather than use the `FieldArray` class.
So instead of ::

    a = FieldArray(80, ['bool'])

use ::

    a = Field.fromstring('bool * 80')

If you need to repeat fields whose lengths aren't known at the time of construction then you can use a `Repeat` field as described below.
If you have a choice then choose the `FieldArray` class over the `Repeat` class, as it is more efficient and easier to use.

Repeat
------

A `Repeat` field simply repeats another field a given number of times.

.. class:: Repeat(count: int | Iterable[int] | str, fieldtype: [FieldType | str] | None = None, name: str = '')

The `count` parameter can be either an integer or an iterable of integers, so for example a ``range`` object is accepted.
The `name` parameter is used to give the index a name that can be referenced elsewhere.

If you want to repeat a single field then it is usually better to have one field and use the `items` parameter rather than use the `Repeat` class.
So instead of ::

    r = Repeat(10, 'float64')  # This creates ten fields, each a single float64

use ::

    r = Field.fromstring('float64 * 10')  # Creates a single field with an array of ten float64

For simple repetition of a field of a known length the `FieldArray` class will be more efficient and easier to use.


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


Condition
---------

.. class:: Condition(cond: lambda, fieldtype: [FieldType | str] | None = None, name: str = '')




Expressions
===========

`bitformat` supports a limited evaluation syntax that looks a little like Python f-strings.
This allows the values of named fields to be reused elsewhere with little effort.

To do this, you can use braces within a string to substitute a value or expression.
This is probably easiest to explain by example::

    f = Format([
                'u12 <width>',
                'u12 <height>',
                'u8 * {width * height} <area>'
               ])

Here we have two named fields followed by an array whose size is given by the product of the other two fields.
This means that when this `Format` is used to `parse` a bitstring the amount of data it will consume depends on the `height` and `width` fields it reads in first.

The operations allowed are limited in scope, but include simple mathematical operations, indexing and boolean comparisions.
You could for example simulate an 'if' condition by using a `Repeat` field with a boolean count.
This will then be repeated either zero or one time::

    f = Format(['float32 <val>',
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

    f = Format(['hex8 <sync_byte> = 0xff',
                'u16 <items>',
                'bool * {items + 1} <flags>',
                Repeat('{items + 1}', Format([
                       'u4 <byte_cluster_size>',
                       'bytes{byte_cluster_size}'
                       ]), 'clusters'),
                'u8 = {clusters[0][0] << 4}'
                ])



