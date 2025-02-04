.. currentmodule:: bitformat
.. _api:

API Reference
=============

This reference guide is mostly built from the documentation strings in the library, but some introductory notes are also
included in each section.

For a more structured introduction to the library see the `Tour of bitformat <https://nbviewer.org/github/scott-griffiths/bitformat/blob/main/doc/bitformat_tour.ipynb>`_.

.. mermaid::

    ---
    title: Basic bitformat classes
    config:
        class:
            hideEmptyMembersBox: true
    ---
    classDiagram
        direction BT
        class Bits {
            + from_string()
            + from_dtype()
            + from_bytes()
        }
        class Array {
            + int size
            + Dtype dtype
            + from_iterable()
        }
        class Dtype {
            <<abstract>>
            + endianness
            + from_string()
        }
        class DtypeSingle {
            + str name
            + int size
        }
        class DtypeArray {
            + str name
            + int size
            + int items
        }
        class DtypeTuple {
            + List[Dtype] dtypes
        }
        class Reader {
            + Bits bits
            + int pos
        }
        DtypeSingle --|> Dtype
        DtypeArray --|> Dtype
        DtypeTuple --|> Dtype
        Array --* "1" Dtype : contains
        Array --> Bits : interprets
        Reader --* "1" Bits : contains


The Basics
----------
The :class:`Bits` and :class:`Dtype` classes are the most fundamental ones to use and understand.

* :ref:`Bits <bits>` -- An immutable container for storing binary data.
* :ref:`Dtype <dtype>` -- A data type used to interpret binary data.
* :ref:`DtypeTuple <dtypetuple>` -- A sequence of :class:`Dtype` objects.
* :ref:`Array <array>` -- A mutable container for contiguously allocated objects with the same `Dtype`.
* :ref:`Reader <reader>` -- Read and parse :class:`Bits` as a bit stream with a bit position.


.. mermaid::

    ---
    title: Field types
    config:
        class:
            hideEmptyMembersBox: true
    ---
    classDiagram
        direction BT
        class Bits
        class Dtype
        class FieldType{
            <<abstract>>
            + str name
        }
        class Field{
            + Dtype dtype
        }
        class If{
            + Expression condition
            + FieldType then_
            + FieldType else_
        }
        class Repeat{
            + int n
            + FieldType field
        }
        class Format{
            + List[FieldType] fields
        }
        Field --|> FieldType
        Format --|> FieldType
        If --|> FieldType
        Repeat --|> FieldType
        Field --* "1" Dtype : contains
        Field --* "0..1" Bits : contains


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

