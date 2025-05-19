.. currentmodule:: bitformat
.. _mutable_bits:

MutableBits
===========

The ``MutableBits`` class is the mutable version of :class:`Bits`.

It has almost all of the methods and properties of :class:`Bits` and adds capabilities for changing the bits in-place.

The new methods are:

* :meth:`~MutableBits.append`
* :meth:`~MutableBits.byte_swap`
* :meth:`~MutableBits.insert`
* :meth:`~MutableBits.invert`
* :meth:`~MutableBits.prepend`
* :meth:`~MutableBits.replace`
* :meth:`~MutableBits.reverse`
* :meth:`~MutableBits.rol`
* :meth:`~MutableBits.ror`
* :meth:`~MutableBits.set`

You can switch between :class:`MutableBits` and :class:`Bits` using the :meth:`MutableBits.to_bits` and :meth:`Bits.to_mutable_bits` methods.

----

.. autoclass:: bitformat.MutableBits
   :members:
   :member-order: groupwise
   :undoc-members:
   :inherited-members:
