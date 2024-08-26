.. currentmodule:: bitformat

User Manual
===========

The ``bitformat`` Python package is designed to make working with binary data and formats easier and more intuitive.
It allows arbitrary length binary data to be created and parsed using a simple and flexible syntax.

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
* In pre-alpha stage - still quite unstable.

When deciding which one to use the TLDR; for most people is that you should use ``bitstring`` for anything at all serious, at least for now.
I am hoping that ``bitformat`` will become a worthy successor, and I'd be very happy for you to try it out and give feedback.
Even if ``bitformat`` is successful I plan to support ``bitstring`` indefinitely - at the time of writing their respective download counts are 88 million for bitstring and 882 for bitformat!

.. warning::

    While there are many similarities between bitformat and bitstring, there has been no attempt to make them compatible.
    Much of the reason for making a new package was to revisit many of the design decisions that were made almost two
    decades ago when George W. Bush was president, the Nintendo Wii was the latest must-have tech, and Python 2.4 was the latest version.

    While both packages have classes such as ``Bits``, ``Dtype`` and ``Array`` and many similar methods,
    they do have many differences in their behaviour and API.



