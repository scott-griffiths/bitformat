.. currentmodule:: bitformat


.. class:: Format(name: str | None = None, fields: Sequence[Format | Bits | Dtype | str] | None = None)

    A ``Format`` describes how to create and / or parse a binary object.

    It consists of a sequence of fields, each of which can be any of:

        * A literal bitstring. This can be either a ``Bits`` object or a ``str`` that can be used to create one.
        * A data type ('dtype'). This can be either a ``Dtype`` object or a ``str`` that can be used to create one.
        * Another ``Format`` object.
        * A ``tuple`` whose first value is a ``str`` used to name the field.
          The second value should be a ``Bits``, ``Dtype``, ``Format`` or a ``str`` that can be used to create one.
          The optional third value can be used to initialise a ``Dtype`` in the second value.

    Some examples::

        f = Format('header', [
            '0x000001b3',  # String converts to 32 bit Bits object
            'u12',  # String converts to Dtype for a 12 bit unsigned int
            '<height> u12',  # A field named 'height' that is also a u12
            '<flag> bool = True')  # A boolean field named 'flag' that is set to True
            ])

    Here we have four fields, two of which are bit literals, with the other two needing a value before a complete binary object can be constructed.


.. class:: Field(name: str | None = None, dtype: Dtype | Bits | str, value: Any = None)

    A `Field` has a data type (`dtype`) that describes how to interpret binary data and optionally a `name` and a concrete `value` for the `dtype`.

    ``name``: An optional string used to identify the `Field` when it is contained inside a `Format`.
    Using an empty string (``''``) is the same as using ``None``.
    It is an error to use two `Field`s with the same `name` in a `Format` object, though you may have multiple unnamed `Field`s.

    ``dtype``: The data type can be:
        * A `Dtype` object (e.g. ``Dtype('float', 16)``).
        * A string that can be used to construct a `Dtype` (e.g. ``'float16'``).
        * A string that can be used to construct a `Dtype` with a value (e.g. ``'uint12=105'``)

        For convenience you can also give either a `Bits` object (e.g. ``Bits('0x47')``), or a string that can be used to construct a `Bits` object (e.g. ``'0x47'``).
        This will will cause the `dtype` to be set to ``Dtype('bits')`` and the `value` to be set to the `Bits` object.

    ``value``: A value can be supplied for the ``Dtype`` - this should be something suitable for the type, for example you can't give the value of ``2`` to a ``bool``, or ``123xyz`` to a ``hex`` dtype.
    Note that if a value has already been given as part of the `dtype` parameter it shouldn't be specified here as well.

    As a shortcut the `name` parameter can be used to specify the whole field.
    To do this the name should be of the format::

        "<name> dtype = value"

    For example instead of ``Field('width', Dtype('uint', 12), 100)`` you could say just ``Field('<width> uint12 = 100')``.
    The whitespace between the elements is optional.

    An example for a bit literal would be instead of ``Field('sequence_header', Bits(bytes=b'\0x00\x00\x01\xb3'))`` you would use ``Field('<sequence_header> = 0x000001b3')``.

    The `name`, `dtype` and `value` are all properties of the `Field` and can be read and altered after creation. ::

        f = Field('<