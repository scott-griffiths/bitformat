
.. currentmodule:: bitformat

.. image:: bitformat_logo.png
   :width: 400px

`bitformat <https://github.com/scott-griffiths/bitformat/>`_ is a Python module for creating and parsing file formats, especially at the bit rather than byte level.

It is intended to complement the `bitstring <https://github.com/scott-griffiths/bitstring>`_ module, but is currently at a planning stage and is not yet recommended for use.

----

The `bitformat` module provides the ``Format`` class which is used to define how to create and parse binary formats. ::

    from bitformat import Format, Dtype, Bits

    f1 = Format([Bits('0xabc')])  # A bit literal (12 bits long)
    f2 = Format([Dtype('u5')])    # A 5-bit unsigned integer

    f3 = Format([f1, f2, f2])   # A format made of other formats

    d = f3.pack(3, 10)          # A Bits object packed with the values 3 and 10
    f3.parse(d)




These docs are styled using the `Piccolo theme <https://github.com/piccolo-orm/piccolo_theme>`_.


