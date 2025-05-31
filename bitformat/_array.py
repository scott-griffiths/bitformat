from __future__ import annotations

import math
from collections.abc import Sized, Sequence
from typing import Union, Iterable, Any, overload, TextIO

from bitformat._bits import Bits, BitsType, MutableBits, create_mutable_bitrust_from_any
from bitformat._dtypes import Dtype, Register, DtypeTuple, DtypeSingle
from bitformat._options import Options
from bitformat._common import Colour, DtypeKind
import operator
import sys
from bitformat.bit_rust import MutableBitRust, BitRust

__all__ = ["Array"]

# The possible types stored in each element of the Array
ElementType = Union[float, str, int, bytes, bool, Bits, MutableBits]


class Array:
    """
    An Array whose elements are all a single data type.

    The ``Array`` data is stored compactly as a ``MutableBits`` object and the ``Array`` behaves very like
    a list of items of the given format.

    If the data length is not a multiple of the dtype length then the ``Array`` will have ``trailing_bits``
    which will prevent some methods from appending to the ``Array``.

    To construct, use a builder 'from' method:

    * ``Array.from_iterable(dtype, iterable)`` - Create and initialise from an iterable.
    * ``Array.from_bits(dtype, bits)`` - Create with data from a :class:`Bits` or :class:`MutableBits` object.
    * ``Array.from_bytes(dtype, bytes_data)`` - Create with data from a ``bytes`` -like object.
    * ``Array.from_zeros(dtype, n)`` - Initialise with enough zero bits for ``n`` elements.

    Using the constructor ``Array(dtype, iterable)`` is an alias for ``Array.from_iterable(dtype, iterable)``,
    but this does not accept either ``Bits`` or ``bytes`` objects as the iterable to avoid confusion.

    **Other methods:**

    - ``append(item)``: Append a single item to the end of the Array.
    - ``as_type(dtype)``: Creates a new Array with a new data type, initialized from the current Array.
    - ``byte_swap()``: Change byte endianness of all items.
    - ``count(value)``: Count the number of occurrences of a value.
    - ``equals(other)``: Comparison method between Arrays.
    - ``extend(iterable)``: Append new items to the end of the Array from an iterable.
    - ``insert(index, item)``: Insert an item at a given position.
    - ``pop([index])``: Remove and return an item. Default is the last item.
    - ``pp([dtype1, dtype2, groups, width, show_offset, stream])``: Pretty print the Array.
    - ``reverse()``: Reverse the order of all items.
    - ``to_bits()``: Return a copy of the Array data as an immutable ``Bits``.
    - ``to_bytes()``: Return Array data as bytes object, padding with zero bits at the end if needed.
    - ``unpack()``: Return Array items as a list of values.

    **Special methods:**

    Also available are the operators ``[]``, ``==``, ``!=``, ``+``, ``*``, ``<<``, ``>>``, ``&``, ``|``, ``^``,
    plus the mutating operators ``[]=``, ``+=``, ``*=``, ``<<=``, ``>>=``, ``&=``, ``|=``, ``^=``.

    **Properties:**

    - ``bits``: The binary data of the ``Array`` as a ``MutableBits`` object.
    - ``dtype``: The data type of the elements in the ``Array``.
    - ``item_size``: The length *in bits* of a single item. Read only.
    - ``trailing_bits``: If the data length is not a multiple of the dtype length, this ``Bits``
      gives the leftovers at the end of the data.
    """

    _mutable_bitrust: MutableBitRust
    _dtype: Dtype

    def __new__(cls, dtype: str | Dtype, iterable: Iterable | None = None) -> Array:
        if isinstance(iterable, (Bits, MutableBits)):
            raise TypeError("The iterable argument in the Array init method should not be a Bits or MutableBits object. "
                            "Choose either from_bits() or from_iterable() instead.")
        if isinstance(iterable, (bytes, bytearray)):
            raise TypeError("The iterable argument in the Array init method should not be a bytes or bytearray object. "
                            "Choose either from_bytes() or from_iterable() instead.")
        x = cls.from_iterable(dtype, [] if iterable is None else iterable)
        return x

    @classmethod
    def from_bytes(cls, dtype: str | Dtype, bytes_data: bytes | bytearray | memoryview) -> Array:
        """Create a new :class:`Array` from a data type and a bytes object.

        :param dtype: The data type of the elements in the ``Array``.
        :type dtype: Dtype | str
        :param bytes_data: The bytes object to convert to a :class:`Bits`.
        :type bytes_data: bytes
        :rtype: Array

        .. code-block:: python

            a = Array.from_bytes('u8', b"some_bytes_maybe_from_a_file")

        """
        x = super().__new__(cls)
        x._set_dtype(dtype)
        x._mutable_bitrust = MutableBitRust.from_bytes(bytes_data)
        return x

    @classmethod
    def from_bits(cls, dtype: str | Dtype, bits: Bits) -> Array:
        x = super().__new__(cls)
        x._set_dtype(dtype)
        # We may change the internal BitRust, so need to make a copy here.
        if isinstance(bits, MutableBits):
            x._mutable_bitrust = bits._bitstore.clone()
        else:
            x._mutable_bitrust = bits._bitstore.clone_as_mutable()
        return x

    @classmethod
    def from_zeros(cls, dtype: str | Dtype, n: int) -> Array:
        x = super().__new__(cls)
        x._set_dtype(dtype)
        x._mutable_bitrust = MutableBitRust.from_zeros(n * x.item_size)
        return x

    @classmethod
    def from_iterable(cls, dtype: str | Dtype, iterable: Iterable) -> Array:
        x = super().__new__(cls)
        x._set_dtype(dtype)
        x._mutable_bitrust = MutableBitRust.from_zeros(0)
        x.extend(iterable)
        return x

    def info(self) -> str:
        """Return a descriptive string with information about the Array.

        Note that the output is designed to be helpful to users and is not considered part of the API.
        You should not use the output programmatically as it may change even between point versions.
        """
        return f"Array of {self._dtype.info()} with {len(self)} items and {len(self._mutable_bitrust)} bits of data."

    @property
    def bits(self) -> MutableBits:
        """Property that provides access to the ``Array`` data as a ``MutableBits``.

        Note that this is the actual data of the ``Array`` and any changes made to it will affect the ``Array``.
        Use the ``to_bits()`` method if you need a copy of the data instead.
        """
        x = MutableBits()
        x._bitstore = self._mutable_bitrust
        return x

    @bits.setter
    def bits(self, value: BitsType) -> None:
        self._mutable_bitrust = create_mutable_bitrust_from_any(value)

    def _get_bit_slice(self, start: int, stop: int | None) -> MutableBits:
        x = MutableBits()
        x._bitstore = self._mutable_bitrust.getslice(start, stop)
        return x

    @property
    def item_size(self) -> int:
        """The length of a single item in bits. Read only."""
        return self._dtype.bit_length

    @property
    def trailing_bits(self) -> Bits:
        """The ``Bits`` at the end of the ``Array`` that don't fit into a whole number of elements."""
        bitstore_length = len(self._mutable_bitrust)
        trailing_bit_length = bitstore_length % self.item_size
        if trailing_bit_length == 0:
            return Bits()
        return self._get_bit_slice(bitstore_length - trailing_bit_length, bitstore_length).to_bits()

    @property
    def dtype(self) -> Dtype:
        """The data type of the elements in the Array."""
        return self._dtype

    @dtype.setter
    def dtype(self, new_dtype: str | Dtype) -> None:
        self._set_dtype(new_dtype)

    def _set_dtype(self, new_dtype: str | Dtype) -> None:
        if isinstance(new_dtype, Dtype):
            self._dtype = new_dtype
        else:
            try:
                dtype = Dtype.from_string(new_dtype)
            except ValueError as e:
                raise ValueError(f"Inappropriate Dtype for Array: '{new_dtype}': {e}")
            self._dtype = dtype
        if self.item_size == 0 or self.item_size is None:
            raise ValueError(f"A fixed length data type is needed for an Array, received '{new_dtype}'.")

    def _create_element(self, value: ElementType) -> BitRust:
        """Create Bits from value according to the token_name and token_length"""
        return self._dtype.pack(value)._bitstore

    def __len__(self) -> int:
        """The number of complete elements in the ``Array``."""
        return len(self._mutable_bitrust) // self.item_size

    @overload
    def __getitem__(self, key: slice, /) -> Array: ...

    @overload
    def __getitem__(self, key: int, /) -> ElementType: ...

    def __getitem__(self, key: slice | int, /) -> Array | ElementType:
        if isinstance(key, slice):
            start, stop, step = key.indices(len(self))
            if step != 1:
                d = []
                for s in range(start * self.item_size, stop * self.item_size, step * self.item_size):
                    d.append(self._mutable_bitrust.getslice(s, s + self.item_size).clone_as_immutable())
                a = self.__class__(self._dtype)
                a._mutable_bitrust = MutableBitRust.join(d)
                return a
            else:
                a = self.__class__(self._dtype)
                a._mutable_bitrust = self._mutable_bitrust.getslice(start * self.item_size, stop * self.item_size)
                return a
        else:
            if key < 0:
                key += len(self)
            if key < 0 or key >= len(self):
                raise IndexError(f"Index {key} out of range for Array of length {len(self)}.")
            return self._dtype.unpack(self._get_bit_slice(self.item_size * key, self.item_size * (key + 1)))

    @overload
    def __setitem__(self, key: slice, value: Iterable[ElementType], /) -> None: ...

    @overload
    def __setitem__(self, key: int, value: ElementType, /) -> None: ...

    def __setitem__(self, key: slice | int, value: Iterable[ElementType] | ElementType, /) -> None:
        if isinstance(key, slice):
            start, stop, step = key.indices(len(self))
            if not isinstance(value, Iterable):
                raise TypeError("Can only assign an iterable to a slice.")
            if step == 1:
                new_data = BitRust.join([self._create_element(x) for x in value])
                self._mutable_bitrust.set_slice(start * self.item_size, stop * self.item_size, new_data)
                return
            items_in_slice = len(range(start, stop, step))
            if not isinstance(value, Sized):
                value = list(value)
            if len(value) == items_in_slice:
                for s, v in zip(range(start, stop, step), value):
                    x = self._create_element(v)
                    self._mutable_bitrust.set_slice(s * self.item_size, s * self.item_size + len(x), x)
            else:
                raise ValueError(f"Can't assign {len(value)} values to an extended slice of length {items_in_slice}.")
        else:
            if key < 0:
                key += len(self)
            if key < 0 or key >= len(self):
                raise IndexError(f"Index {key} out of range for Array of length {len(self)}.")
            start = self.item_size * key
            x = self._create_element(value)
            self._mutable_bitrust.set_slice(start, start + self.item_size, x)
            return

    def __delitem__(self, key: slice | int, /) -> None:
        if isinstance(key, slice):
            start, stop, step = key.indices(len(self))
            if step == 1:
                self._mutable_bitrust = MutableBitRust.join([self._mutable_bitrust.getslice(0, start * self.item_size).clone_as_immutable(),
                                               self._mutable_bitrust.getslice(stop * self.item_size, None).clone_as_immutable()])
                return
            # We need to delete from the end or the earlier positions will change
            r = (
                reversed(range(start, stop, step))
                if step > 0
                else range(start, stop, step)
            )
            for s in r:
                self._mutable_bitrust = MutableBitRust.join([self._mutable_bitrust.getslice(0, s * self.item_size).clone_as_immutable(),
                                               self._mutable_bitrust.getslice((s + 1) * self.item_size, None).clone_as_immutable()])
        else:
            if key < 0:
                key += len(self)
            if key < 0 or key >= len(self):
                raise IndexError
            start = self.item_size * key
            self._mutable_bitrust = MutableBitRust.join([self._mutable_bitrust.getslice(0, start).clone_as_immutable(),
                                           self._mutable_bitrust.getslice(start + self.item_size, None).clone_as_immutable()])

    def __repr__(self) -> str:
        bitstore_length = len(self._mutable_bitrust)
        if bitstore_length % self.item_size == 0:
            list_str = f"{self.unpack()}"
            return f"Array('{self._dtype}', {list_str})"
        return f"Array.from_bits('{self._dtype}', {self.to_bits()!r})"

    def as_type(self, dtype: str | Dtype, /) -> Array:
        """
        Creates and returns a new ``Array`` instance with a specified data type, initialized with the current Array's elements.

        This method allows for the conversion of the Array's elements to a different data type, specified by the `dtype` parameter.
        The conversion process respects the original values of the elements, adapting them to the new data type format.
        This can be useful for changing the representation of data within the Array, for example, from integers to floating-point numbers or vice versa.

        :param dtype: The target data type for the new Array.
        :type dtype: str | Dtype
        :returns: A new `Array` instance with the specified `dtype`, containing the elements of the current Array converted to the new data type.
        :rtype: Array

        :raises ValueError: If the specified `dtype` is not supported or cannot be applied to the elements of the current Array.

        .. code-block:: pycon

            >>> original_array = Array('i5', [1, 2, 3])
            >>> float_array = original_array.as_type('f16')
            >>> print(float_array)
            Array('f16', [1.0, 2.0, 3.0])

        """
        new_array = self.__class__(dtype, self.unpack())
        return new_array

    def unpack(self, dtype: str | Dtype | None = None) -> list[ElementType]:
        """Interpret the Array as a list of elements of a given dtype, defaulting to the Array's current dtype.

        .. code-block:: pycon

            >>> a = Array('i3', [2, 1, -2, 0])
            >>> a.unpack()
            [2, 1, -2, 0]
            >>> a.unpack('bin3')
            ['010', '001', '110', '000']
            >>> a.unpack('u5, bool')
            [(8, True), (24, False)]

        """
        if dtype is None:
            dtype = self._dtype
        elif isinstance(dtype, str):
            dtype = Dtype.from_string(dtype)
        if dtype.bit_length is None:
            if not isinstance(dtype, DtypeSingle):
                raise ValueError(f"Can't unpack using an array Dtype with unknown size: '{dtype}'.")
            else:
                # No length supplied - use the current length instead
                dtype = DtypeSingle.from_params(dtype.kind, self.dtype.size)
        l = []
        for start in range(0, len(self._mutable_bitrust) - dtype.bit_length + 1, dtype.bit_length):
            b = Bits()
            b._bitstore = self._mutable_bitrust.getslice(start, start + dtype.bit_length)
            l.append(dtype.unpack(b))
        return l

    def append(self, x: ElementType, /) -> Array:
        """
        Append a single item to the end of the Array.

        :param x: The item to append.
        :type x: ElementType
        :return: The modified Array.
        :rtype: Array
        """
        if len(self._mutable_bitrust) % self.item_size != 0:
            raise ValueError("Cannot append to Array as its length is not a multiple of the format length.")
        self._mutable_bitrust.append(self._create_element(x))
        return self

    def extend(self, iterable: Array | bytes | bytearray | Bits | Iterable[Any], /) -> Array:
        """
        Append new items to the end of the Array from an iterable.

        This method allows you to extend the Array by appending elements from another iterable.
        The iterable can be another Array, bytes, bytearray, Bits, or any other iterable containing elements of a compatible type.

        :param iterable: The iterable containing elements to append to the Array.
        :type iterable: Array, bytes, bytearray, Bits, or any iterable of compatible elements
        :return: The extended Array.
        :rtype: Array
        """
        if isinstance(iterable, (bytes, bytearray)):
            # extend the bit data by appending on the end
            self._mutable_bitrust.append(Bits.from_bytes(iterable)._bitstore)
            return self
        if len(self._mutable_bitrust) % self.item_size != 0:
            raise ValueError(f"Cannot extend Array as its data length ({len(self._mutable_bitrust)} bits) "
                             f"is not a multiple of the format length ({self.item_size} bits).")
        if isinstance(iterable, Array):
            if self._dtype != iterable._dtype:
                raise TypeError(f"Cannot extend an Array with format '{self._dtype}' "
                                f"from an Array of format '{iterable._dtype}'.")
            # No need to iterate over the elements, we can just append the data
            self._mutable_bitrust.append(iterable._mutable_bitrust.clone_as_immutable())
        else:
            if isinstance(iterable, str):
                raise TypeError("Can't extend an Array with a str.")
            to_join = [self._create_element(item) for item in iterable]
            self._mutable_bitrust.append(BitRust.join(to_join))
        return self

    def insert(self, pos: int, x: ElementType, /) -> Array:
        """
        Insert a new element into the Array at position pos.

        :param pos: The position to insert the item.
        :type pos: int
        :param x: The item to insert.
        :type x: ElementType
        :return: The modified Array.
        :rtype: Array
        """
        if pos < 0:
            pos += len(self)
        pos = min(pos, len(self))  # Inserting beyond len of Array inserts at the end (copying standard behaviour)
        v = self._create_element(x)
        self._mutable_bitrust = MutableBitRust.join([self._mutable_bitrust.getslice(0, pos * self.item_size).clone_as_immutable(),
                                       v,
                                       self._mutable_bitrust.getslice(pos * self.item_size, None).clone_as_immutable()])
        return self

    def pop(self, pos: int = -1, /) -> ElementType:
        """
        Return and remove an element of the Array.

        Default is to return and remove the final element.

        :param pos: The position of the item to remove. Default is -1 (last item).
        :type pos: int
        :return: The removed item.
        :rtype: ElementType
        """
        if len(self) == 0:
            raise IndexError("Can't pop from an empty Array.")
        x = self[pos]
        del self[pos]
        return x

    def byte_swap(self) -> Array:
        """
        Change the endianness in-place of all items in the Array.

        If the Array format is not a whole number of bytes a ValueError will be raised.

        :return: The modified Array.
        :rtype: Array
        """
        if self.item_size % 8 != 0:
            raise ValueError("byte_swap can only be used for whole-byte elements. "
                             f"The '{self._dtype}' format is {self.item_size} bits long.")
        b = MutableBits()
        b._bitstore = self._mutable_bitrust.clone()
        b.byte_swap(self.item_size // 8)
        self._mutable_bitrust = b._bitstore
        return self

    def count(self, value: ElementType, /) -> int:
        """Return count of Array items that equal value.

        value -- The quantity to compare each Array element to. Type should be appropriate for the Array format.

        For floating point types using a value of ``float('nan')`` will count the number of elements that are NaN.

        """
        if math.isnan(value):
            return sum(math.isnan(i) for i in self)
        else:
            return sum(i == value for i in self)

    def to_bytes(self) -> bytes:
        """Return the Array data as a bytes object, padding with zero bits if needed.

        Up to seven zero bits will be added at the end to byte align.

        """
        return self._mutable_bitrust.to_bytes()

    def to_bits(self) -> Bits:
        """Return as a Bits object. This is an immutable copy of the current Array data."""
        x = Bits()
        x._bitstore = self._mutable_bitrust.clone_as_immutable()
        return x

    def reverse(self) -> Array:
        """
        Reverse the order of all items in the Array in place.

        :raises ValueError: If the Array's data length is not a multiple of the item size in bits.
        :return: The Array object with its items reversed.
        :rtype: Array

        .. code-block:: pycon

            >>> a = Array('i14', [-3, 0, 100])
            >>> a.reverse()
            Array('i14', [100, 0, -3])


        """
        trailing_bit_length = len(self._mutable_bitrust) % self.item_size
        if trailing_bit_length != 0:
            raise ValueError(f"Cannot reverse the items in the Array as its data length ({len(self._mutable_bitrust)} bits) "
                             f"is not a multiple of the format length ({self.item_size} bits).")
        self._mutable_bitrust = MutableBits.from_joined([self._get_bit_slice(s - self.item_size, s)
                                           for s in range(len(self._mutable_bitrust), 0, -self.item_size)])._bitstore
        return self

    def pp(self, dtype1: str | Dtype | None = None, dtype2: str | Dtype | None = None, groups: int | None = None,
           width: int = 80, show_offset: bool = True, stream: TextIO = sys.stdout) -> None:
        """
        Pretty-print the Array contents.

        This method provides a formatted output of the Array's contents, allowing for easy inspection of the data.
        The output can be customized with various parameters to control the format, width, and display options.

        :param dtype1: Data type to display. Defaults to the current Array dtype.
        :type dtype1: str or Dtype or None
        :param dtype2: Data type for addition display data.
        :type dtype2: str or Dtype or None
        :param groups: How many groups of bits to display on each line. This overrides any value given for width.
        :type groups: int or None
        :param width: Maximum width of printed lines in characters. Defaults to 80, but ignored if groups parameter is set.
            A single group will always be printed per line even if it exceeds the max width.
        :type width: int
        :param show_offset: If True, shows the element offset in the first column of each line.
        :type show_offset: bool
        :param stream: A TextIO object with a write() method. Defaults to sys.stdout.
        :type stream: TextIO
        :return: None
        """
        colour = Colour(not Options().no_color)
        sep = " "
        if dtype1 is None and dtype2 is not None:
            dtype1, dtype2 = dtype2, dtype1
        if dtype1 is None:
            dtype1 = self.dtype
        if isinstance(dtype1, str):
            dtype1 = Dtype.from_string(dtype1)
        if isinstance(dtype2, str):
            dtype2 = Dtype.from_string(dtype2)

        token_length = dtype1.bit_length if dtype1.bit_length is not None else 0
        if dtype2 is not None:
            if dtype1.bit_length != 0 and dtype2.bit_length != 0 and dtype1.bit_length != dtype2.bit_length:
                raise ValueError(f"If two Dtypes are given to pp() they must have the same length,"
                                 f" but '{dtype1}' has a length of {dtype1.bit_length} and '{dtype2}' has a "
                                 f"length of {dtype2.bit_length}.")
            if token_length == 0:
                token_length = dtype2.bit_length if dtype2.bit_length is not None else 0
        if token_length == 0:
            token_length = self.item_size

        if not isinstance(dtype1, DtypeSingle) or (dtype2 is not None and not isinstance(dtype2, DtypeSingle)):
            raise ValueError("Array.pp() only supports simple Dtypes, not ones which represent arrays.")

        trailing_bit_length = len(self._mutable_bitrust) % token_length
        format_sep = " : "  # String to insert on each line between multiple formats
        dtype1_str = str(dtype1)
        dtype2_str = ""
        if dtype2 is not None:
            dtype2_str = f", dtype2='{dtype2}'"
        data = self._get_bit_slice(0, len(self._mutable_bitrust) - trailing_bit_length)
        length = len(self._mutable_bitrust) // token_length
        len_str = colour.green + str(length) + colour.off
        stream.write(
            f"<{self.__class__.__name__} dtype1='{dtype1_str}'{dtype2_str}, length={len_str}, item_size={token_length} bits, total data size={(len(self._mutable_bitrust) + 7) // 8} bytes> [\n"
        )
        data._pp(dtype1, dtype2, token_length, width, sep, format_sep, show_offset, stream, token_length, groups)
        stream.write("]")
        if trailing_bit_length != 0:
            stream.write(" + trailing_bits = 0b" + self._get_bit_slice(len(self._mutable_bitrust) - trailing_bit_length, None).unpack("bin"))
        stream.write("\n")

    def equals(self, other: Any, /) -> bool:
        """
        Return True if the data type and all Array items are equal to another Array.

        This method should be used to test the equality of two Arrays. Normally types will provide
        an ``==`` operator to do this task, but for Arrays the ``==`` operator is instead
        used for element-wise comparison and will return a new Array of bools.

        :param other: The other Array to compare with.
        :type other: Any
        :return: ``True`` if the Arrays are equal, ``False`` otherwise.
        :rtype: bool
        """
        if isinstance(other, Array):
            if self._dtype != other._dtype:
                return False
            if self._mutable_bitrust != other._mutable_bitrust:
                return False
            return True
        return False

    def __iter__(self) -> Iterable[ElementType]:
        start = 0
        for _ in range(len(self)):
            b = MutableBits()
            b._bitstore = self._mutable_bitrust.getslice(start, start + self.item_size)
            yield self._dtype.unpack(b)
            start += self.item_size

    def __copy__(self) -> Array:
        a_copy = self.__class__.from_bits(self._dtype, self.to_bits())
        return a_copy

    def _apply_op_to_all_elements(self, op, value: int | float | None, is_comparison: bool = False) -> Array:
        """Apply op with value to each element of the Array and return a new Array"""
        if isinstance(self._dtype, DtypeTuple):
            raise ValueError(f"Cannot apply operators such as '{op.__name__}' to an Array with a DtypeTuple dtype.")
        new_array = self.__class__("bool" if is_comparison else self._dtype)
        new_data = MutableBits()
        failures = index = 0
        msg = ""
        if value is not None:
            def partial_op(a):
                return op(a, value)
        else:
            def partial_op(a):
                return op(a)

        for i in range(len(self)):
            b = MutableBits()
            b._bitstore = self._mutable_bitrust.getslice(self.item_size * i, self.item_size * (i + 1))
            v = self._dtype.unpack(b)
            try:
                new_data += new_array._dtype.pack(partial_op(v))
            except (ZeroDivisionError, ValueError) as e:
                if failures == 0:
                    msg = str(e)
                    index = i
                failures += 1
        if failures != 0:
            raise ValueError(f"Applying operator '{op.__name__}' to Array caused {failures} errors. "
                             f'First error at index {index} was: "{msg}"')
        new_array._mutable_bitrust = new_data._bitstore
        return new_array

    def _apply_op_to_all_elements_inplace(self, op, value: int | float) -> Array:
        """Apply op with value to each element of the Array in place."""
        # This isn't really being done in-place, but it's simpler and faster for now?
        if isinstance(self._dtype, DtypeTuple):
            raise ValueError(f"Cannot apply operators such as '{op.__name__}' to an Array with a DtypeTuple dtype.")
        new_data = MutableBits()
        failures = index = 0
        msg = ""
        for i in range(len(self)):
            b = MutableBits()
            b._bitstore = self._mutable_bitrust.getslice(self.item_size * i, self.item_size * (i + 1))
            v = self._dtype.unpack(b)
            try:
                new_data += self._dtype.pack(op(v, value))
            except (ZeroDivisionError, ValueError) as e:
                if failures == 0:
                    msg = str(e)
                    index = i
                failures += 1
        if failures != 0:
            raise ValueError(f"Applying operator '{op.__name__}' to Array caused {failures} errors. "
                             f'First error at index {index} was: "{msg}"')
        self._mutable_bitrust = new_data._bitstore.clone()
        return self

    def _apply_bitwise_op_to_all_elements(self, op, value: BitsType) -> Array:
        """Apply op with value to each element of the Array as an unsigned integer and return a new Array"""
        a_copy = Array(self.dtype)
        a_copy._mutable_bitrust = self._mutable_bitrust.clone()
        a_copy._apply_bitwise_op_to_all_elements_inplace(op, value)
        return a_copy

    def _apply_bitwise_op_to_all_elements_inplace(self, op, value: BitsType) -> Array:
        """Apply op with value to each element of the Array as an unsigned integer in place."""
        value = create_mutable_bitrust_from_any(value)
        if len(value) != self.item_size:
            raise ValueError(f"Bitwise op {op} needs a Bits of length {self.item_size} to match "
                             f"format {self._dtype}, but received '{value}' which has a length of {len(value)} bits.")
        for start in range(0, len(self) * self.item_size, self.item_size):
            mutablebitrust_slice = self._mutable_bitrust.getslice(start, start + self.item_size)
            if op == operator.ixor:
                mutablebitrust_slice.ixor(value)
            elif op == operator.iand:
                mutablebitrust_slice.iand(value)
            elif op == operator.ior:
                mutablebitrust_slice.ior(value)
            self._mutable_bitrust.set_slice(start, start + self.item_size, mutablebitrust_slice.as_immutable())
        return self

    def _apply_op_between_arrays(self, op, other: Array, is_comparison: bool = False) -> Array:
        if len(self) != len(other):
            msg = f"Cannot operate element-wise on Arrays with different lengths ({len(self)} and {len(other)})."
            if op in [operator.add, operator.iadd]:
                msg += " Use extend() method to concatenate Arrays."
            if op in [operator.eq, operator.ne]:
                msg += " Use equals() method to compare Arrays for a single boolean result."
            raise ValueError(msg)
        if is_comparison:
            new_type = Register().get_single_dtype(DtypeKind.BOOL, 1)
        else:
            new_type = self._promote_type(self._dtype, other._dtype)
        new_array = self.__class__(new_type)
        new_data = MutableBits()
        failures = index = 0
        msg = ""
        for i in range(len(self)):
            a_bits = MutableBits()
            a_bits._bitstore = self._mutable_bitrust.getslice(self.item_size * i, self.item_size * (i + 1))
            b_bits = MutableBits()
            b_bits._bitstore = other._mutable_bitrust.getslice(other.item_size * i, other.item_size * (i + 1))
            a = self._dtype.unpack(a_bits)
            b = other._dtype.unpack(b_bits)
            try:
                new_data += new_array._dtype.pack(op(a, b))
            except (ValueError, ZeroDivisionError) as e:
                if failures == 0:
                    msg = str(e)
                    index = i
                failures += 1
        if failures != 0:
            raise ValueError(f"Applying operator '{op.__name__}' between Arrays caused {failures} errors. "
                             f'First error at index {index} was: "{msg}"')
        new_array._mutable_bitrust = new_data._bitstore
        return new_array

    @classmethod
    def _promote_type(cls, type1: DtypeSingle, type2: DtypeSingle) -> DtypeSingle:
        """When combining types which one wins?

        1. We only deal with types representing floats or integers.
        2. One of the two types gets used. We never create a new one.
        3. Floating point types always win against integer types.
        4. Signed integer types always win against unsigned integer types.
        5. Longer types win against shorter types.
        6. In a tie the first type wins against the second type.

        """

        def is_float(x):
            return x._definition.return_type is float

        def is_int(x):
            return x._definition.return_type is int or x._definition.return_type is bool

        if is_float(type1) + is_int(type1) + is_float(type2) + is_int(type2) != 2:
            raise ValueError(f"Only integer and floating point types can be combined - not '{type1}' and '{type2}'.")
        # If same type choose the widest
        if type1.kind == type2.kind:
            return type1 if type1.bit_length > type2.bit_length else type2
        # We choose floats above integers, irrespective of the widths
        if is_float(type1) and is_int(type2):
            return type1
        if is_int(type1) and is_float(type2):
            return type2
        if is_float(type1) and is_float(type2):
            return type2 if type2.bit_length > type1.bit_length else type1
        assert is_int(type1) and is_int(type2)
        if type1._definition.is_signed and not type2._definition.is_signed:
            return type1
        if type2._definition.is_signed and not type1._definition.is_signed:
            return type2
        return type2 if type2.bit_length > type1.bit_length else type1

    # Operators between Arrays or an Array and scalar value

    def __add__(self, other: int | float | Array) -> Array:
        """Add int or float to all elements."""
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.add, other)
        return self._apply_op_to_all_elements(operator.add, other)

    def __iadd__(self, other: int | float | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.add, other)
        return self._apply_op_to_all_elements_inplace(operator.add, other)

    def __isub__(self, other: int | float | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.sub, other)
        return self._apply_op_to_all_elements_inplace(operator.sub, other)

    def __sub__(self, other: int | float | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.sub, other)
        return self._apply_op_to_all_elements(operator.sub, other)

    def __mul__(self, other: int | float | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.mul, other)
        return self._apply_op_to_all_elements(operator.mul, other)

    def __imul__(self, other: int | float | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.mul, other)
        return self._apply_op_to_all_elements_inplace(operator.mul, other)

    def __floordiv__(self, other: int | float | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.floordiv, other)
        return self._apply_op_to_all_elements(operator.floordiv, other)

    def __ifloordiv__(self, other: int | float | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.floordiv, other)
        return self._apply_op_to_all_elements_inplace(operator.floordiv, other)

    def __truediv__(self, other: int | float | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.truediv, other)
        return self._apply_op_to_all_elements(operator.truediv, other)

    def __itruediv__(self, other: int | float | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.truediv, other)
        return self._apply_op_to_all_elements_inplace(operator.truediv, other)

    def __rshift__(self, other: int | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.rshift, other)
        return self._apply_op_to_all_elements(operator.rshift, other)

    def __lshift__(self, other: int | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.lshift, other)
        return self._apply_op_to_all_elements(operator.lshift, other)

    def __irshift__(self, other: int | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.rshift, other)
        return self._apply_op_to_all_elements_inplace(operator.rshift, other)

    def __ilshift__(self, other: int | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.lshift, other)
        return self._apply_op_to_all_elements_inplace(operator.lshift, other)

    def __mod__(self, other: int | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.mod, other)
        return self._apply_op_to_all_elements(operator.mod, other)

    def __imod__(self, other: int | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.mod, other)
        return self._apply_op_to_all_elements_inplace(operator.mod, other)

    # Bitwise operators

    def __and__(self, other: BitsType) -> Array:
        return self._apply_bitwise_op_to_all_elements(operator.iand, other)

    def __iand__(self, other: BitsType) -> Array:
        return self._apply_bitwise_op_to_all_elements_inplace(operator.iand, other)

    def __or__(self, other: BitsType) -> Array:
        return self._apply_bitwise_op_to_all_elements(operator.ior, other)

    def __ior__(self, other: BitsType) -> Array:
        return self._apply_bitwise_op_to_all_elements_inplace(operator.ior, other)

    def __xor__(self, other: BitsType) -> Array:
        return self._apply_bitwise_op_to_all_elements(operator.ixor, other)

    def __ixor__(self, other: BitsType) -> Array:
        return self._apply_bitwise_op_to_all_elements_inplace(operator.ixor, other)

    # Reverse operators between a scalar value and an Array

    def __rmul__(self, other: int | float) -> Array:
        return self._apply_op_to_all_elements(operator.mul, other)

    def __radd__(self, other: int | float) -> Array:
        return self._apply_op_to_all_elements(operator.add, other)

    def __rsub__(self, other: int | float) -> Array:
        # i - A == (-A) + i
        neg = self._apply_op_to_all_elements(operator.neg, None)
        return neg._apply_op_to_all_elements(operator.add, other)

    # Reverse operators between a scalar and something that can be a Bits.

    def __rand__(self, other: BitsType) -> Array:
        return self._apply_bitwise_op_to_all_elements(operator.iand, other)

    def __ror__(self, other: BitsType) -> Array:
        return self._apply_bitwise_op_to_all_elements(operator.ior, other)

    def __rxor__(self, other: BitsType) -> Array:
        return self._apply_bitwise_op_to_all_elements(operator.ixor, other)

    # Comparison operators

    def __lt__(self, other: int | float | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.lt, other, is_comparison=True)
        return self._apply_op_to_all_elements(operator.lt, other, is_comparison=True)

    def __gt__(self, other: int | float | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.gt, other, is_comparison=True)
        return self._apply_op_to_all_elements(operator.gt, other, is_comparison=True)

    def __ge__(self, other: int | float | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.ge, other, is_comparison=True)
        return self._apply_op_to_all_elements(operator.ge, other, is_comparison=True)

    def __le__(self, other: int | float | Array) -> Array:
        if isinstance(other, Array):
            return self._apply_op_between_arrays(operator.le, other, is_comparison=True)
        return self._apply_op_to_all_elements(operator.le, other, is_comparison=True)

    def _eq_ne(self, op, other: Any) -> Array:
        if isinstance(other, (int, float, str, Bits, MutableBits)):
            return self._apply_op_to_all_elements(op, other, is_comparison=True)
        other = self.__class__(self.dtype, other)
        return self._apply_op_between_arrays(op, other, is_comparison=True)

    def __eq__(self, other: Any) -> Array:
        return self._eq_ne(operator.eq, other)

    def __ne__(self, other: Any) -> Array:
        return self._eq_ne(operator.ne, other)

    # Unary operators

    def __neg__(self):
        return self._apply_op_to_all_elements(operator.neg, None)

    def __abs__(self):
        return self._apply_op_to_all_elements(operator.abs, None)


Sequence.register(Array)