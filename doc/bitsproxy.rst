.. currentmodule:: bitformat
.. _bitsproxy:

BitsProxy
=========

The :class:`BitsProxy` class is used to allow the data stored in an :class:`Array` to be accessed using the methods and properties of a :class:`Bits` object.
It is returned when the :attr:`Array.data` property is used.

The difference between the ``BitsProxy`` and ``Bits`` should not be usually be noticed by the user. The reason it is needed is that an :class:`Array` is mutable whereas a :class:`Bits` object is immutable, and it would often be inefficient to copy data to an immutable :class:`Bits` just to use its methods.


----

.. autoclass:: bitformat.BitsProxy
   :members:
   :undoc-members:
   :member-order: groupwise
