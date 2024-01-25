.. currentmodule:: bitstring

.. _quick_reference:

Quick Reference
===============

This section gives a summary of the `bitformat` module's classes, functions and attributes.


Field
-----

:class:`Field` describes which define a binary sequence.


``Field(dtype: Dtype | Bits | str, name: str | None = None, value: Any = None, items: int = 1)``

Methods
^^^^^^^

* :meth:`~Field.build` --
* :meth:`~Field.parse` -- Fill in values for empty Fields by parsing a binary object.
* :meth:`~Field.tobits` -- Return data as a Bits object.
* :meth:`~Field.tobytes` -- Return data as bytes object, padding with zero bits at the end if needed.

Special methods
^^^^^^^^^^^^^^^

Also available are these operators:

* :meth:`== <Field.__eq__>` / :meth:`\!= <Field.__ne__>` -- Equality tests.


Properties
^^^^^^^^^^

* :attr:`~Field.dtype` -- The data type of the field.
* :attr:`~Field.name` -- A name for the Field that should be a valid Python identifier. Can be left empty.
* :attr:`~Field.value` -- The value of the data type. Can be None for an empty Field.
* :attr:`~Field.bits` -- For non-empty Fields this contains the binary digits of the Field.
* :attr:`~Field.items` -- The number of items of the dtype (to create an Array). Defaults to 1.



----

Format
------

:class:`Format` describes a sequence of :class:`Field`s and other nested ``Format``s which define a binary sequence.


``Format(name: str | None = None, fields: Sequence[Format | Bits | Dtype | str] | None = None)``

Methods
^^^^^^^

* :meth:`~Format.append` -- Add a new field to the end of the current fields.
* :meth:`~Format.build` --
* :meth:`~Format.flatten` -- Returns a flat list of the Fields in the Format
* :meth:`~Format.parse` -- Fill in values for empty Fields by parsing a binary object.
* :meth:`~Format.tobits` -- Return data as a Bits object.
* :meth:`~Format.tobytes` -- Return data as bytes object, padding with zero bits at the end if needed.
* :meth:`~Format.copy` -- Return a copy of the `Format`.
* :meth:`~Format.pp` -- Pretty print the Format.
* :meth:`~Format.clear` -- Remove values for all Fields that aren't bit literals.

Special methods
^^^^^^^^^^^^^^^

Also available are these operators:

* :meth:`== <Format.__eq__>` / :meth:`\!= <Format.__ne__>` -- Equality tests.
* :meth:`[] <Format.__getitem__>` -- Get a field either by index or by name.
* :meth:`+ <Format.__add__>` -- Add a new field to the end of the current fields.
* :meth:`[] <Format.__setitem__>` -- Set a field either by index or by name.
* :meth:`del <Format.__delitem__>` -- Delete a field either by index or by name.
* :meth:`+= <Format.__iadd__>` -- Append a new field to the current Format.


Properties
^^^^^^^^^^

* :attr:`~Format.name` -- A name for the Format. Can be left empty.
* :attr:`~Format.fields` -- The list of Fields or nested Formats.
* :attr:`~Format.empty_fields` -- The number of Fields in the Format which do not have a value.



