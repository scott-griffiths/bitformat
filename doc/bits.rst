.. currentmodule:: bitformat
.. _bits:

Tibs
====

The ``Tibs`` class represents an immutable sequence of bits, similar to how the built-in ``bytes`` is an immutable sequence of bytes, and a ``str`` is an immutable sequence of characters.

If you need to modify the data after creation there is also a :class:`Mutibs` class, but the more efficient :class:`Tibs` should be preferred if the extra capabilities are not needed.

You can switch between :class:`Tibs` and :class:`Mutibs` using the :meth:`Tibs.to_mutibs` and :meth:`Mutibs.to_tibs` methods.

For direct byte-endian interpretation, prefer the tibs-native endian views::

    >>> t = Tibs('0x3412')
    >>> t.le.u
    4660
    >>> t.be.u
    13330
    >>> Tibs.from_value('u16_le', 0x1234)
    Tibs('0x3412')
    >>> Tibs.from_values('u16_le', [0x1234, 0x5678])
    Tibs('0x34127856')

In bitformat format strings and dtypes, use explicit ``_le`` or ``_be`` suffixes, for example ``u16_le`` or ``f32_be``.
There is no native-endian suffix.

Because :class:`Tibs` is the actual :class:`tibs.Tibs` class, the reference below also includes methods inherited directly from the :mod:`tibs` package.
If a tibs method documents a ``byte_order`` parameter, it expects :class:`tibs.Endianness`, not :class:`bitformat.Endianness`.
The :class:`bitformat.Endianness` enum is only used for bitformat dtype objects; direct :class:`Tibs` code should normally use the ``le`` and ``be`` views shown above.


----

.. autoclass:: bitformat.Tibs
   :members:
   :member-order: groupwise
   :undoc-members:
   :inherited-members:
