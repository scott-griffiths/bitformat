.. currentmodule:: bitformat
.. _mutable_bits:

Mutibs
===========

The ``Mutibs`` class is the mutable counterpart to :class:`Tibs`.

It has a very similar API to :class:`Tibs` and adds capabilities for changing the bits in-place.

The new methods are:

* :meth:`~Mutibs.append`
* :meth:`~Mutibs.byte_swap`
* :meth:`~Mutibs.clear`
* :meth:`~Mutibs.extend`
* :meth:`~Mutibs.extend_left`
* :meth:`~Mutibs.insert`
* :meth:`~Mutibs.invert`
* :meth:`~Mutibs.replace`
* :meth:`~Mutibs.reverse`
* :meth:`~Mutibs.rotate_left`
* :meth:`~Mutibs.rotate_right`
* :meth:`~Mutibs.set`
* :meth:`~Mutibs.unset`

The mutating methods use tibs-native return values. For example :meth:`~Mutibs.replace` mutates in place and returns the number of replacements made.

You can switch between :class:`Mutibs` and :class:`Tibs` using the :meth:`Mutibs.to_tibs` and :meth:`Tibs.to_mutibs` methods.

The :meth:`~Mutibs.reserve` and :meth:`~Mutibs.capacity` methods can be used to manage the capacity of the :class:`Mutibs` to avoid unneccesary reallocations, but their use is purely for performance optimization.

----

.. autoclass:: bitformat.Mutibs
   :members:
   :member-order: groupwise
   :undoc-members:
   :inherited-members:
