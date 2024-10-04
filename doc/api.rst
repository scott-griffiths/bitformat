.. currentmodule:: bitformat

API Reference
=============

This reference guide is mostly built from the documentation strings in the library, but some introductory notes are also
included in each section.

For a more structured introduction to the library see the `Tour of bitformat <https://nbviewer.org/github/scott-griffiths/bitformat/blob/main/doc/bitformat_tour.ipynb>`_.

Main Classes
------------

The :class:`Bits` and :class:`Dtype` classes are the most fundamental ones to use and understand.
The others in this section build upon them to provide more specialised structures.

* :ref:`Bits <bits>` -- An immutable container for storing binary data.
* :ref:`Dtype <dtype>` -- A data type used to interpret binary data.
* :ref:`Array <array>` -- A mutable container for contiguously allocated objects with the same `Dtype`.
* :ref:`Field <field>` -- Represents an optionally named, well-defined amount of binary data with a single data type.
* :ref:`Format <format>` -- A sequence of :class:`FieldType` objects, such as :class:`Field` or :class:`Format` instances.
* :ref:`If <if>` -- A pair of :class:`FieldType` obejcts, one of which is selected based on a condition.
* :ref:`Pass <pass>` -- An empty :class:`FieldType` used as a placeholder.

Other Classes
-------------
* :ref:`Options <options>` -- Getting and setting module-wide options.
* :ref:`BitsProxy <bitsproxy>` -- Used by :class:`Array` to allow the data to behave more like :class:`Bits`.
* :ref:`FieldType <fieldtype>` -- The abstract base class for :class:`Field`, :class:`Format` etc.
* :ref:`Register <register>` -- The register of allowed :class:`Dtype` types.

Miscellaneous
-------------

* :ref:`Everything else <misc>`

.. toctree::
    :maxdepth: 1
    :hidden:

    bits.rst
    dtype.rst
    array.rst
    field.rst
    format.rst
    if.rst
    pass.rst
    options.rst
    bitsproxy.rst
    fieldtype.rst
    register.rst
    misc.rst

