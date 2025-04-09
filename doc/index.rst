
.. currentmodule:: bitformat

.. image:: bitformat_logo.png
   :width: 400px

`bitformat <https://github.com/scott-griffiths/bitformat/>`_ is a Python library for creating and parsing file formats, especially at the bit rather than byte level.

It is from the author of the `bitstring <https://github.com/scott-griffiths/bitstring>`_ library.

----

Features
--------

* A bitformat is a specification of a binary format using fields that can say how to build it from supplied values, or how to parse binary data to retrieve those values.
* A wide array of data types is supported.  Want to use a 13 bit integer or an 8-bit float? Fine - there are no special hoops to jump through.
* Several field types are available:

  * The simplest is just a `Field` which contains a single data type, and either a single value or an array of values. These can usually be constructed from just a string.
  * A `Format` contains a list of other fields. These can be nested to any depth.
  * Field types like `Repeat` and `If` can be used to add more logical structure.
* The values of other fields can be used in later calculations via an f-string-like expression syntax.
* Data is always stored efficiently as a contiguous array of bits, with the core of the library written in Rust.

----

Installation and download
-------------------------

The first product release was made in September 2024, with a 0.2 release in January 2025 that moved the core of the library to be compiled in Rust. More features were added in the 0.3 release in April, and further releases are planned for 2025.

To install the module, use pip:

    pip install bitformat

There are pre-built wheels for Windows, Linux and MacOS, and more will be added later. It is compatible with Python 3.11 and later.

To download the library, as well as for defect reports, enhancement requests and Git repository browsing go to `the project's home on GitHub. <https://github.com/scott-griffiths/bitformat/>`_

----

Documentation
-------------

A tour of the features of bitformat is given in notebook form:

* `A Tour of bitformat <https://nbviewer.org/github/scott-griffiths/bitformat/blob/main/doc/bitformat_tour.ipynb>`_

The main documentation is available here:

.. toctree::
   :hidden:

   self

.. toctree::
    :maxdepth: 2

    introduction
    api

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
