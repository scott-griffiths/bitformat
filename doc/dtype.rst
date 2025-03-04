.. currentmodule:: bitformat
.. _dtype:

Dtype
=====

Data type classes are used to represents ways to interpret binary data.
The :class:`Dtype` class is an abstract base class, but its constructor can be used to conveniently create the correct sub-class.

The concrete data-type classes are:

* :class:`DtypeSingle` which is used for a data type representing a single value a kind of interpretation, such as a 32-bit float, or a 10 bit integer.
* :class:`DtypeArray` which adds an item count to represent an array of values of the same type, such as 1000 ``u8`` or 5 ``bool`` flags.
* :class:`DtypeTuple` is a sequence of data types that can be of different value types.

These classes all have a ``from_params`` method to create them, but also have a particular formatting that can be used in the base :class:`Dtype` ``from_string`` method which will delegate to the correct sub-class.

It's usually best to create them via a call to ``Dtype('some_formatted_string')``.

In places where a ``Dtype`` is expected as a parameter you can just supply the string format and it find the correct type automatically.

Some examples of equivalent types, going from most verbose to least::

    DtypeSingle.from_params(DtypeKind.UINT, 8)
    DtypeSingle('u8')
    Dtype('u8')
    'u8'  # When used as a parameter

::

    DtypeArray.from_params(DtypeKind.FLOAT, 16, 20)
    DtypeArray('[f16; 20]')
    Dtype('[f16; 20]')
    '[f16; 20]'  # When used as a parameter

::

    DtypeTuple.from_params([DtypeSingle.from_params(DtypeKind.UINT, 8), DtypeArray.from_params(DtypeKind.FLOAT, 16, 20)])
    DtypeTuple.from_params(['u8', '[f16; 20]'])
    DtypeTuple('(u8, [f16; 20])')
    Dtype('(u8, [f16; 20])')
    '(u8, [f16; 20])'  # When used as a parameter

----

.. autoclass:: bitformat.Dtype
   :members:
   :undoc-members:
   :member-order: groupwise
   :show-inheritance:

.. _dtypesingle:

DtypeSingle
===========

----

.. autoclass:: bitformat.DtypeSingle
   :members:
   :undoc-members:
   :member-order: groupwise
   :show-inheritance:

.. _dtypearray:

DtypeArray
==========

----

.. autoclass:: bitformat.DtypeArray
   :members:
   :undoc-members:
   :member-order: groupwise
   :show-inheritance:


.. _dtypetuple:

DtypeTuple
==========

----

The ``DtypeTuple`` class represents a sequence of :class:`Dtype` objects.


.. autoclass:: bitformat.DtypeTuple
   :members:
   :undoc-members:
   :member-order: groupwise
   :show-inheritance:

