.. currentmodule:: bitstring

.. _quick_reference:

Quick Reference
===============

This section gives a summary of the `bitformat` module's classes, functions and attributes.

Class Overview
--------------

Objects in `bitformat` that can be parsed and built are constructed from the `FieldType` objects that are listed in the table below.
Some of these types will usually be used as part of a larger structure, where they can be optionally constructed from strings - for these types a string example is given in the description.

.. |nbsp| unicode:: 0xa0
   :trim:

.. list-table::
   :header-rows: 1

   * - Class
     - String format?
     - Description

   * - :ref:`fieldtype_quick_reference`
     - n/a
     - The abstract base class for the other classes listed here.
   * - :ref:`field_quick_reference`
     - ✓
     - A single data type, with optional name and value.
   * -
     -
     - ``'dtype <name> = value'``
   * - :ref:`fieldarray_quick_reference`
     - ✓
     - An array of a single fixed-length data type, with optional name and value.
   * -
     -
     - ``'dtype * items <name> = value'``
   * - :ref:`format_quick_reference`
     - ×
     - A sequence of other FieldTypes, with optional name.
   * -
     -
     - ``Format([field1, field2, ...], 'name'])``
   * - :ref:`repeat_quick_reference`
     - ×
     - Repeat another field type a number of times, with optional name.
   * -
     -
     - ``Repeat(10, 'float64', 'a_name')``


.. _fieldtype_quick_reference:

FieldType
---------

The `FieldType` class shouldn't be used directly, but is a base class containing the most fundamental methods that all of the other classes here support.

.. class:: FieldType

    .. method:: tobits() -> Bits
        :abstractmethod:

        Return data as a Bits object.

    .. method:: build(values: list[Any] | None = None, kwargs: dict[str, Any] | None = None) -> Bits
        :abstractmethod:

    .. method:: tobytes() -> bytes
        :abstractmethod:

        Return data as bytes object, padding with up to 7 zero bits at the end if needed.

    .. method:: clear() -> None
        :abstractmethod:

    .. method:: flatten() -> list[FieldType]
        :abstractmethod:

    .. method:: parse(b: Bits | bytes | bytearray, /) -> int
        :abstractmethod:

        Fill in values for empty Fields by parsing a binary object.

    .. method:: __eq__
        :abstractmethod:

        Equality test.

    .. property:: name: str


.. _field_quick_reference:

Field
-----

The `Field` is the fundamental building block in `bitformat`.


.. class:: Field(dtype: Dtype | str, name: str = '', value: Any = None, const: bool | None = None)

    .. classmethod:: frombits(bits: Bits | str | bytes | bytearray, name: str = '') -> Self

    .. classmethod:: fromstring(s: str, /) -> Self

    .. property:: const:: bool

    .. property:: dtype:: Dtype

    .. property:: value:: Any

        The value of the data type. Will be `None` for an empty Field.


.. _fieldarray_quick_reference:

FieldArray
----------

A `FieldArray` has a single data type like `Field`, but instead holds an array of that type.
The dtype must have a fixed length to be used in a `FieldArray` (most do).

.. class:: FieldArray(dtype: Dtype | str, items: str | int, name: str = '', value: Any = None, const: bool | None = None)

    .. classmethod:: fromstring(s: str, /) -> Self

    .. property:: const:: bool

    .. property:: dtype:: Dtype

    .. property:: items:: int

    .. property:: value:: list[Any]


.. _format_quick_reference:

Format
------

The `Format` type is central to creating useful objects in `bitformat`.
It contains a sequence of other `FieldType` objects, which can include nested `Format`s.

.. class:: Format(fieldtypes: Sequence[FieldType | str], name: str = '')


.. _repeat_quick_reference:

Repeat
------

A `Repeat` field simply repeats another field a given number of times.

.. class:: Repeat(count: int | Iterable[int] | str, fieldtype: [FieldType | str] | None = None, name: str = '')

The `count` parameter can be either an integer or an iterable of integers, so for example a ``range`` object is accepted.
The `name` parameter is used to give the index a name that can be referenced elsewhere.


----



