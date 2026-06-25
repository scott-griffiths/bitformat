.. currentmodule:: bitformat
.. _bits:

Tibs
====

The ``Tibs`` class represents an immutable sequence of bits, similar to how the built-in ``bytes`` is an immutable sequence of bytes, and a ``str`` is an immutable sequence of characters.

If you need to modify the data after creation there is also a :class:`Mutibs` class, but the more efficient :class:`Tibs` should be preferred if the extra capabilities are not needed.

You can switch between :class:`Tibs` and :class:`Mutibs` using the :meth:`Tibs.to_mutibs` and :meth:`Mutibs.to_tibs` methods.


----

.. autoclass:: bitformat.Tibs
   :members:
   :member-order: groupwise
   :undoc-members:
   :inherited-members:
