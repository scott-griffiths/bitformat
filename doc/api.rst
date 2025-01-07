.. currentmodule:: bitformat
.. _api:

API Reference
=============

This reference guide is mostly built from the documentation strings in the library, but some introductory notes are also
included in each section.

For a more structured introduction to the library see the `Tour of bitformat <https://nbviewer.org/github/scott-griffiths/bitformat/blob/main/doc/bitformat_tour.ipynb>`_.

The Basics
----------
The :class:`Bits` and :class:`Dtype` classes are the most fundamental ones to use and understand.

* :ref:`Bits <bits>` -- An immutable container for storing binary data.
* :ref:`Dtype <dtype>` -- A data type used to interpret binary data.
* :ref:`DtypeTuple <dtypetuple>` -- A sequence of :class:`Dtype` objects.
* :ref:`Array <array>` -- A mutable container for contiguously allocated objects with the same `Dtype`.
* :ref:`Reader <reader>` -- Read and parse :class:`Bits` as a bit stream with a bit position.

Field Types
-----------
These classes build upon those above to provide richer and more complex data structures.

* :ref:`FieldType <fieldtype>` -- The abstract base class for the other classes in this section.
* :ref:`Format <format>` -- A sequence of :class:`FieldType` objects, such as :class:`Field` or other :class:`Format` instances.
* :ref:`Field <field>` -- A well-defined amount of binary data with a single data type, and optionally a name.
* :ref:`If <if>` -- A pair of :class:`FieldType` obejcts, one of which is selected based on a condition.
* :ref:`Repeat <repeat>` -- Used to repeat another :class:`FieldType` a number of times.
* :ref:`Pass <pass>` -- An empty :class:`FieldType` used as a placeholder.

Other Classes
-------------
* :ref:`Options <options>` -- Getting and setting module-wide options.
* :ref:`BitsProxy <bitsproxy>` -- Used by :class:`Array` to allow the data to behave more like :class:`Bits`.
* :ref:`Register <register>` -- The register of allowed :class:`Dtype` types.

Miscellaneous
-------------

* :ref:`Everything else <misc>`

.. toctree::
    :maxdepth: 1
    :hidden:

    bits.rst
    dtype.rst
    dtypetuple.rst
    array.rst
    reader.rst
    fieldtype.rst
    field.rst
    format.rst
    if.rst
    repeat.rst
    pass.rst
    options.rst
    bitsproxy.rst
    register.rst
    misc.rst

