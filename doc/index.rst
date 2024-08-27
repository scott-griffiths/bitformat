
.. currentmodule:: bitformat

.. warning::
    This library is in the planning stages.
    The API will be very unstable and I do not recommend its use for anything serious.

    This documentation may in places be more aspirational than accurate.


.. image:: bitformat_logo.png
   :width: 400px

`bitformat <https://github.com/scott-griffiths/bitformat/>`_ is a Python module for creating and parsing file formats, especially at the bit rather than byte level.

It is intended to complement the `bitstring <https://github.com/scott-griffiths/bitstring>`_ module from the same author, and uses its `Dtype <https://bitstring.readthedocs.io/en/latest/dtypes.html#dtypes>`_, `Bits <https://bitstring.readthedocs.io/en/latest/bits.html#bits>`_ and `Array <https://bitstring.readthedocs.io/en/latest/array.html#array>`_ classes as the basis for building complex bit formats.

Features
^^^^^^^^
* A bitformat is a specification of a binary format using fields that can say how to build it from supplied values, or how to parse binary data to retrieve those values.
* A wide array of data types is supported.  Want to use a 13 bit integer or an 8-bit float? Fine - there are no special hoops to jump through.
* Several field types are available:

  * The simplest is just a `Field` which contains a single data type, and either a single value or an array of values. These can usually be constructed from just a string.
  * A `Format` contains a list of other fields. These can be nested to any depth.
  * [Coming soon] Fields like `Repeat`, `Find` and `If` can be used to add more logical structure.
* The values of other fields can be used in later calculations via an f-string-like expression syntax.
* Data is always stored efficiently as a contiguous array of bits.


Installation and download
^^^^^^^^^^^^^^^^^^^^^^^^^
I am planning on a minimal viable product release by September 2024, with a fuller release later in the year.
If you wish to try it out now then I recommend installing from the main branch on GitHub as that will be far ahead of the release on PyPI. ::

    pip install git+https://github.com/scott-griffiths/bitformat

To download the module, as well as for defect reports, enhancement requests and Git repository browsing go to `the project's home on GitHub. <https://github.com/scott-griffiths/bitformat/>`_



Documentation
^^^^^^^^^^^^^

.. toctree::
   :hidden:

   self

.. toctree::

    manual
    tour
    autoapi/bitformat/index


These docs are styled using the `Piccolo theme <https://github.com/piccolo-orm/piccolo_theme>`_.


