
.. currentmodule:: bitformat

.. image:: bitformat_logo.png
   :width: 400px

`bitformat <https://github.com/scott-griffiths/bitformat/>`_ is a Python module for creating and parsing file formats, especially at the bit rather than byte level.

It is from the author of the `bitstring <https://github.com/scott-griffiths/bitstring>`_ module.

----

Features
--------

* A bitformat is a specification of a binary format using fields that can say how to build it from supplied values, or how to parse binary data to retrieve those values.
* A wide array of data types is supported.  Want to use a 13 bit integer or an 8-bit float? Fine - there are no special hoops to jump through.
* Several field types are available:

  * The simplest is just a `Field` which contains a single data type, and either a single value or an array of values. These can usually be constructed from just a string.
  * A `Format` contains a list of other fields. These can be nested to any depth.
  * [Coming soon] Field types like `Repeat`, `Find` and `If` can be used to add more logical structure.
* [Coming soon] The values of other fields can be used in later calculations via an f-string-like expression syntax.
* Data is always stored efficiently as a contiguous array of bits.

----

Installation and download
-------------------------

I am planning on a minimal viable product release by September 2024, with a fuller release later in the year.
If you wish to try it out now then I recommend installing from the main branch on GitHub as that will be far ahead of the release on PyPI. ::

    pip install git+https://github.com/scott-griffiths/bitformat

To download the module, as well as for defect reports, enhancement requests and Git repository browsing go to `the project's home on GitHub. <https://github.com/scott-griffiths/bitformat/>`_

----

bitformat vs. bitstring
-----------------------

bitformat is from the same author as the `bitstring <https://github.com/scott-griffiths/bitstring>`_ package, which is widely used and has been actively maintained since 2006.
It covers much of the same ground, but is designed to have a stronger emphasis on performance, a simpler API and a more expressive syntax for binary formats.

``bitstring``

* Simple and flexible syntax for binary data manipulation.
* Reasonable performance, but difficult to improve further.
* Very mature and stable - maintained since 2006.
* Hundreds of dependant projects and millions of downloads per month.


``bitformat``

* Expressive syntax for complex binary formats.
* Emphasis on performance.
* Several major features still to be added.
* In alpha stage - still quite unstable.

When deciding which one to use the TLDR; for most people is that you should use ``bitstring`` for anything at all serious, at least for now.
I am hoping that ``bitformat`` will become a worthy successor, and I'd be very happy for you to try it out and give feedback.
Even if ``bitformat`` is successful I plan to support ``bitstring`` indefinitely - at the time of writing their respective download counts are 88 million for bitstring and 882 for bitformat!

.. note::

    There are many similarities between bitformat and bitstring, but there has been no attempt to make them compatible.
    Much of the reason for making a new package was to revisit many of the design decisions that were made almost two
    decades ago when George W. Bush was president, the Nintendo Wii was the latest must-have tech, and Python 2.4 was the latest version.

----

Documentation
-------------

A tour of the features of bitformat is given in notebook form:

* `A Tour of bitformat <https://nbviewer.org/github/scott-griffiths/bitformat/blob/main/doc/bitformat_tour.ipynb>`_

The API documentation is available here:

.. toctree::
   :hidden:

   self

.. toctree::
    :maxdepth: 1

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
