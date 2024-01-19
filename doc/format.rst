.. currentmodule:: bitformat


.. class:: Format(name: str | None = None, fields: Iterable[Format | Bits | Dtype | str | Tuple[str, Any, Any]])

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
            ('height', 'u12'),  # A field named 'height' that is also a u12
            ('flag', 'bool', True)  # A boolean field named 'flag' that is set to True
            ])

    Here we have four fields, two of which are bit literals, with the other two needing a value before a complete binary object can be constructed.


    .. method:: values() -> Iterator[Any]

    Returns an iterator over the values contained in the ``Format``.

    Fields that do not have a value are skipped.


    ..

f = Format('header', ['0x000001b3', 'u12', ('height', 'u12', 288), ('flag', 'bool', True)])