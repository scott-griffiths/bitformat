.. currentmodule:: bitformat

Fields, Structs, Formats and more
=================================

FieldType
---------

A ``FieldType`` is an abstract base class for all of the other classes in this section.
Although you shouldn't need to deal with this type directly it is helpful to take a look at the methods that are common between all of the other types. ::

  .. class:: FieldType()

      .. method:: FieldType.build(values: List[Any], kwargs: Dict) -> Bits

        Given positional and keyword values, fill in the empty fields a build a `Bits` object.
        Note that this modifies the fieldtype in-place.

      .. method:: FieldType.parse(b: Bits) -> int

        Takes a `Bits` object, parses it according to the field structure and returns the number of bits used.
        Note that this modifies the fieldtype in-place.

      .. method:: FieldType.value() -> Any

        Returns the 'value' of the field.
        For example with a simple ``Field`` representing an integer this would return an integer; for a ``Format`` this would return a list of the values of each field in the ``Format``.

      .. method:: FieldType.flatten() -> List[FieldType]

        Returns a flat list of FieldsTypes.

      .. method:: FieldType.bits() -> Bits

        Converts the contents to a `Bits` bit literal.

      .. method:: FieldType.bytes() -> bytes

        Converts the contents to a `bytes` object.
        Between 0 and 7 zero bits will be added at the end to make it a whole number of bytes long.

      .. method:: FieldType.vars() -> Tuple[List[Any], Dict]

        Returns the positional and keyword values that are contained in the field.

      .. method:: FieldType.clear() -> None

        Clears the field of everything that is not a bit literal.

      Every `FieldType` also has a name string, which should either be an empty string or a valid Python variable name.

      .. property:: name: str

        The name of the fieldtype - used to identify it in other fields.


Field
-----

A `Field` is the fundamental building block in `bitformat`.

.. class:: Field(dtype: Dtype | Bits | str, name: str = '', value: Any = None, items: int = 1)

    A `Field` has a data type (`dtype`) that describes how to interpret binary data and optionally a `name` and a concrete `value` for the `dtype`.

    ``dtype``: The data type can be:
        * A `Dtype` object (e.g. ``Dtype('float', 16)``).
        * A string that can be used to construct a `Dtype` (e.g. ``'float16'``).
        * A string that can be used to construct a `Dtype` with a value (e.g. ``'uint12=105'``)

        For convenience you can also give either a `Bits` object (e.g. ``Bits('0x47')``), or a string that can be used to construct a `Bits` object (e.g. ``'0x47'``).
        This will will cause the `dtype` to be set to ``Dtype('bits')`` and the `value` to be set to the `Bits` object.

    ``name``: An optional string used to identify the `Field` when it is contained inside a `Format`.
    It is an error to use two `Field`s with the same `name` in a `Format` object, though you may have multiple unnamed `Field`s.

    ``value``: A value can be supplied for the ``Dtype`` - this should be something suitable for the type, for example you can't give the value of ``2`` to a ``bool``, or ``123xyz`` to a ``hex`` dtype.
    Note that if a value has already been given as part of the `dtype` parameter it shouldn't be specified here as well.

    ``items``: An array of items of the same type can be specified by setting `items` to be greater than one.

    As a shortcut the `dtype` parameter can be used to specify the whole field.
    To do this the name should be of the format::

        "dtype <name> = value"

    For example instead of ``Field(Dtype('uint', 12), 'width' 100)`` you could say just ``Field('uint12 <width> = 100')``.
    The whitespace between the elements is optional.

    An example for a bit literal would be instead of ``Field(Bits(bytes=b'\0x00\x00\x01\xb3'), 'sequence_header')`` you could use ``Field('<sequence_header> = 0x000001b3')``.


Format
------

A `Format` can be considered as a list of `FieldType` objects.
In its simplest form is could just be a flat list of ``Field`` objects, but it can also contain other ``Format`` objects and the other types described in this section.

.. class:: Format(fieldtypes: Sequence[FieldType | Bits | Dtype | str] | None = None, name: str = '')


Repeat
------

A `Repeat` field simply repeats another field a given number of times.

.. class:: Repeat(count: int | Iterable[int] | str, fieldtype: [FieldType | Bits | Dtype | str] | None = None, name: str = '')

The `count` parameter can be either an integer or an iterable of integers, so for example a ``range`` object is accepted.
The `name` parameter is used to give the index a name that can be referenced elsewhere.


Find
----

.. class:: Find(bits: Bits | str, bytealigned=True, name: str = '')

:meth:`Find.parse` will seek to the next occurrence of `b`.

If `bytealigned` is `True` it will only search on byte boundaries.

The optional `name` parameter is used to give the number of bits skipped a name that can be referenced elsewhere.

:meth:`Find.build` does nothing and returns an empty `Bits` object.

:meth:`Find.value`  returns the number of bits skipped to get to the start of the found bits.
Note that the value will always be in bits, not bytes and that `None` will be returned if the bits could not be found.

:meth:`Find.bits` returns an empty `Bits` and :meth:`Find.bytes` returns an empty `bytes`.












