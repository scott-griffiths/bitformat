.. currentmodule:: bitformat
.. _field:

Field
=====

The :class:`Field` class is the most fundamental building block when creating a binary format.
It represents a well-defined amount of binary data with a single data type.


.. _Field strings:

Field strings
-------------

As a shortcut a single string can usually be used to specify the whole `Field`.
To do this it should be a string of the format::

    "name: dtype = value"

or ::

    "name: [dtype; items] = value"

for array-like Dtypes.

The ``'name:'`` and ``'= value'`` parts are optional, and usually a ``'value'`` would only be specified for a field if it is a constant.

To specify a ``const`` field use either ::

    "name: const dtype = value"

or ::

    "name: const [dtype; items] = value"

When ``const`` is used the `value` must be set.


For example instead of ``Field.from_params(Dtype.from_params(DtypeKind.UINT, 12), 'width', 100)`` you could say ``Field('width: u12 = 100')``.
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


----

.. autoclass:: bitformat.Field
   :members:
   :inherited-members:
   :undoc-members:
   :member-order: groupwise
   :show-inheritance:
