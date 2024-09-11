.. currentmodule:: bitformat
.. _bitsproxy:

BitsProxy
=========

The :class:`BitsProxy` class is used to allow the data stored in an :class:`Array` to be accessed using the methods and properties of a :class:`Bits` object.

This should usually not be noticed by the user - the reason it is needed is that an :class:`Array` is mutable whereas a :class:`Bits` object immutable, and it would often be inefficient to copy data to an immutable :class:`Bits` just to use its methods.

.. autoclass:: bitformat.BitsProxy
   :members:
   :undoc-members:
   :member-order: groupwise
