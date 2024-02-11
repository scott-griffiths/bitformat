
.. currentmodule:: bitformat

.. warning::
    This library is in the planning stages.
    The API will be very unstable and I do not recommend its use for anything serious.

    This documentation may in places be more aspirational than accurate.


.. image:: bitformat_logo.png
   :width: 400px

`bitformat <https://github.com/scott-griffiths/bitformat/>`_ is a Python module for creating and parsing file formats, especially at the bit rather than byte level.

It is intended to complement the `bitstring <https://github.com/scott-griffiths/bitstring>`_ module from the same author, and uses its `Dtype`, `Bits` and `Array` classes as the basis for building complex bit formats.


Installation and download
^^^^^^^^^^^^^^^^^^^^^^^^^
I am planning on a minimal viable product release by April 2024, with a fuller release later in the year.
If you wish to try it out now then I recommend installing from the main branch on GitHub as that will be far ahead of the release on PyPI. ::

    pip install git+https://github.com/scott-griffiths/bitformat

To download the module, as well as for defect reports, enhancement requests and Git repository browsing go to `the project's home on GitHub. <https://github.com/scott-griffiths/bitformat/>`_



Documentation
^^^^^^^^^^^^^

.. toctree::
   :hidden:

   self

.. toctree::

    quick_reference
    format
    fields



These docs are styled using the `Piccolo theme <https://github.com/piccolo-orm/piccolo_theme>`_.


