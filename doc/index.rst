
.. currentmodule:: bitformat

.. image:: bitformat_logo.png
   :width: 400px

A Python library for creating and parsing binary formats.

bitformat
---------

* Efficiently store and manipulate binary data in idiomatic Python using the :ref:`bits` and :ref:`array` classes.
* Powerful binary packing and unpacking functions.
* Bit-level slicing, joining, searching, replacing and more.
* A wide array of data types is supported.  Want to use a 13-bit integer or a 16-bit float? Fine - there are no special hoops to jump through.
* Several field types are available to build up a :ref:`format`, which can then be used to :meth:`~Format.pack`, :meth:`~Format.unpack` or :meth:`~Format.parse` data:

  * The simplest is just a :ref:`field` which contains an optionally named value with a data type.
  * A :ref:`format` contains a list of other fields. These can be nested to any depth.
  * Field types like :ref:`repeat` and :ref:`if` can be used to add more logical structure.
* The values of fields can be used in later calculations via an f-string-like expression syntax.
* Data is always stored efficiently as a contiguous array of bits, with the core of the library written in Rust.


It is from the author of the `bitstring <https://github.com/scott-griffiths/bitstring>`_ library.


----

Installation and download
-------------------------

To install the module, use pip::

    pip install bitformat

There are pre-built wheels for Windows, Linux and MacOS, and more will be added later. It is compatible with Python 3.11 and later.

To download the library, as well as for defect reports, enhancement requests and Git repository browsing go to `the project's home on GitHub. <https://github.com/scott-griffiths/bitformat/>`_

----

Documentation
-------------

The main documentation is available here:

.. toctree::
   :hidden:

   self

.. toctree::
    :maxdepth: 2

    introduction
    use_cases
    api


There is also a notebook with a tour of the features of bitformat:

* `A Tour of bitformat <https://nbviewer.org/github/scott-griffiths/bitformat/blob/main/doc/bitformat_tour.ipynb>`_


----

.. raw:: html

   <style>
       .small-font {
           font-size: 0.9em;
       }
   </style>
   <div class="small-font">
       These docs are styled using the <a href="https://github.com/piccolo-orm/piccolo_theme">Piccolo theme</a>.
   </div>
