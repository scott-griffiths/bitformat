from __future__ import annotations

import math
import numbers
from collections.abc import Sized
from typing import Union, Iterable, Any, overload, TextIO

from bitformat._bits import Bits, BitsType
from bitformat._dtypes import Dtype, Register
from bitformat import _utils
from bitformat._options import Options
from bitformat._common import Colour
import operator
import sys


if Options()._use_pure_python:
    from ._bitstore_pure import BitStore
else:
    from ._bitstore import BitStore

__all__ = ['Array', 'BitsProxy']

# The possible types stored in each element of the Array
ElementType = Union[float, str, int, bytes, bool, Bits]


class BitsProxy:
    """A Proxy object to access the data in an ``Array`` as if it were a ``Bits`` object.

    This allows the mutable data in the ``Array`` to be accessed using the ``Bits`` methods without a copy being made,
    facilitating operations like slicing, bitwise manipulation, and other Bits methods on the ``Array``'s data.
    Usage is almost exactly the same as for ``Bits``, but some special methods such as ``__copy__`` and ``__hash__``
    behave differently.

    Note that a ``BitsProxy`` is mutable, and its value will change as the ``Array`` changes. To copy to an immutable
    ``Bits`` object use the ``to_bits()`` method on the ``Array``.

    See the ``Bits`` class for more information on the available methods.

    """
    def __init__(self, array: Array) -> None:
        """Initialise the with an ``Array`` object to make a proxy to its bit data."""
        self._array = array

    def __len__(self) -> int:
        return len(self._array._bitstore)

    def __getattr__(self, name):
        """Delegate attribute access to the internal bit storage."""
        x = Bits()
        x._bitstore = self._array._bitstore
        return getattr(x, name)

    def __copy__(self):
        """Creates a copy of the ``BitsProxy`` object as a real immutable ``Bits`` object."""
        x = Bits()
        x._bitstore = self._array._bitstore
        return x[:]

    __hash__ = None
    """The hash method is disabled for a ``BitsProxy`` object as it is mutable."""


# List of special methods to delegate
special_methods = [
    '__add__',
    '__and__',
    '__bool__',
    '__contains__',
    '__eq__',
    '__ge__',
    '__getitem__',
    '__gt__',
    '__invert__',
    '__iter__',
    '__le__',
    '__lshift__',
    '__lt__',
    '__mul__',
    '__ne__',
    '__or__',
    '__radd__',
    '__rand__',
    '__repr__',
    '__rmul__',
    '__ror__',
    '__rshift__',
    '__rxor__',
    '__str__',
    '__xor__'
]


def method_factory(name):
    def method(self, *args, **kwargs):
        x = Bits()
        x._bitstore = self._array._bitstore
        return getattr(x, name)(*args, **kwargs)
    return method

# Dynamically create special methods on BitsProxy
for method_name in special_methods:
    setattr(BitsProxy, method_name, method_factory(method_name))


class Array:
    """
    An Array whose elements are all a single data type.

    The ``Array`` data is stored compactly as a ``Bits`` object and the ``Array`` behaves very like
    a list of items of the given format.

    If the data length is not a multiple of the dtype length then the ``Array`` will have ``trailing_bits``
    which will prevent some methods from appending to the ``Array``.

    **Methods:**

    - ``append(item)``: Append a single item to the end of the Array.
    - ``byteswap()``: Change byte endianness of all items.
    - ``count(value)``: Count the number of occurrences of a value.
    - ``extend(iterable)``: Append new items to the end of the Array from an iterable.
    - ``insert(index, item)``: Insert an item at a given position.
    - ``pop([index])``: Remove and return an item. Default is the last item.
    - ``pp([fmt, width, show_offset, stream])``: Pretty print the Array.
    - ``reverse()``: Reverse the order of all items.
    - ``to_bits()``: Return the Array data as a Bits object.
    - ``to_bytes()``: Return Array data as bytes object, padding with zero bits at the end if needed.
    - ``unpack()``: Return Array items as a list of values.

    **Special methods:**

    Also available are the operators ``[]``, ``==``, ``!=``, ``+``, ``*``, ``<<``, ``>>``, ``&``, ``|``, ``^``,
    plus the mutating operators ``[]=``, ``+=``, ``*=``, ``<<=``, ``>>=``, ``&=``, ``|=``, ``^=``.

    **Properties:**

    - ``data``: The binary data of the ``Array`` as a ``BitsProxy`` object.
    - ``dtype``: The data type of the elements in the ``Array``.
    - ``item_size``: The length *in bits* of a single item. Read only.
    - ``trailing_bits``: If the data length is not a multiple of the dtype length, this ``Bits``
      gives the leftovers at the end of the data.
    """

    def __init__(self, dtype: str | Dtype, initializer: int | Array | Iterable | Bits | bytes | bytearray| memoryview | None = None,
                 trailing_bits: BitsType | None = None) -> None:
        self._proxy = BitsProxy(self)
        self._set_dtype(dtype)

        if isinstance(initializer, numbers.Integral):
            self._bitstore = BitStore.from_zeros(initializer * self._dtype.bits_per_item)
        elif isinstance(initializer, Bits):
            # We may change the internal BitStore, so need to make a copy here.
            self._bitstore = initializer._bitstore.copy()
        elif isinstance(initializer, (bytes, bytearray, memoryview)):
            self._bitstore = BitStore.from_bytes(initializer)
        elif initializer is not None:
            self._bitstore = BitStore.from_zeros(0)
            self.extend(initializer)
        else:
            self._bitstore = BitStore.from_zeros(0)
        if trailing_bits is not None:
            x = Bits.from_auto(trailing_bits)
            self._bitstore = BitStore.join([self._bitstore, x._bitstore])

    @property
    def data(self) -> BitsProxy:
        """Property that provides access to the ``Array`` data through a ``BitsProxy``."""
        return self._proxy

    @data.setter
    def data(self, value: BitsType) -> None:
        self._bitstore = Bits.from_auto(value)._bitstore

    def _getbitslice(self, start: int | None, stop: int | None) -> Bits:
        x = Bits()
        x._bitstore = self._bitstore.getslice(start, stop)
        return x

    @property
    def item_size(self) -> int:
        """The length of a single item in bits. Read only."""
        return self._dtype.bits_per_item

    @property
    def trailing_bits(self) -> Bits:
        """The ``Bits`` at the end of the ``Array`` that don't fit into a whole number of elements."""
        trailing_bit_length = len(self._bitstore) % self._dtype.bits_per_item
        return Bits() if trailing_bit_length == 0 else self._getbitslice(-trailing_bit_length, None)

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
        if self._dtype.bits_per_item <= 0:
            raise ValueError(f"A fixed length format is needed for an Array, received '{new_dtype}'.")


    def _create_element(self, value: ElementType) -> Bits:
        """Create Bits from value according to the token_name and token_length"""
        b = self._dtype.pack(value)
        if len(b) != self._dtype.bitlength:
            raise ValueError(f"The value {value!r} has the wrong length for the format '{self._dtype}'.")
        return b

    def __len__(self) -> int:
        """The number of complete elements in the ``Array``."""
        return len(self._bitstore) // self._dtype.bitlength

    @overload
    def __getitem__(self, key: slice, /) -> Array:
        ...

    @overload
    def __getitem__(self, key: int, /) -> ElementType:
        ...

    def __getitem__(self, key: slice | int, /) -> Array | ElementType:
        if isinstance(key, slice):
            start, stop, step = key.indices(len(self))
            if step != 1:
                d = Bits()
                for s in range(start * self._dtype.bitlength, stop * self._dtype.bitlength, step * self._dtype.bitlength):
                    d += self._bitstore.getslice(s, s + self._dtype.bitlength)
                a = self.__class__(self._dtype)
                a._bitstore = d._bitstore
                return a
            else:
                a = self.__class__(self._dtype)
                a._bitstore = self._bitstore.getslice(start * self._dtype.bitlength, stop * self._dtype.bitlength)
                return a
        else:
            if key < 0:
                key += len(self)
            if key < 0 or key >= len(self):
                raise IndexError(f"Index {key} out of range for Array of length {len(self)}.")
            return self._dtype.unpack(self._getbitslice(self._dtype.bitlength * key, self._dtype.bitlength * (key + 1)))

    @overload
    def __setitem__(self, key: slice, value: Iterable[ElementType], /) -> None:
        ...

    @overload
    def __setitem__(self, key: int, value: ElementType, /) -> None:
        ...

    def __setitem__(self, key: slice | int, value: Iterable[ElementType] | ElementType, /) -> None:
        if isinstance(key, slice):
            start, stop, step = key.indices(len(self))
            if not isinstance(value, Iterable):
                raise TypeError("Can only assign an iterable to a slice.")
            if step == 1:
                new_data = Bits()
                for x in value:
                    new_data += self._create_element(x)
                self._bitstore.setitem(slice(start * self._dtype.bitlength, stop * self._dtype.bitlength), new_data._bitstore)
                return
            items_in_slice = len(range(start, stop, step))
            if not isinstance(value, Sized):
                value = list(value)
            if len(value) == items_in_slice:
                for s, v in zip(range(start, stop, step), value):
                    x = self._create_element(v)
                    self._bitstore.setitem(slice(s * self._dtype.bitlength, s * self._dtype.bitlength + len(x)), x._bitstore)
            else:
                raise ValueError(f"Can't assign {len(value)} values to an extended slice of length {items_in_slice}.")
        else:
            if key < 0:
                key += len(self)
            if key < 0 or key >= len(self):
                raise IndexError(f"Index {key} out of range for Array of length {len(self)}.")
            start = self._dtype.bitlength * key
            x = self._create_element(value)
            self._bitstore.setitem(slice(start, start + len(x)), x._bitstore)
            return

    def __delitem__(self, key: slice | int, /) -> None:
        if isinstance(key, slice):
            start, stop, step = key.indices(len(self))
            if step == 1:
                self._bitstore = BitStore.join([self._bitstore.getslice(0, start * self._dtype.bitlength),
                                                self._bitstore.getslice(stop * self._dtype.bitlength, None)])
                return
            # We need to delete from the end or the earlier positions will change
            r = reversed(range(start, stop, step)) if step > 0 else range(start, stop, step)
            for s in r:
                self._bitstore = BitStore.join([self._bitstore.getslice(0, s * self._dtype.bitlength),
                                                self._bitstore.getslice((s + 1) * self._dtype.bitlength, None)])
        else:
            if key < 0:
                key += len(self)
            if key < 0 or key >= len(self):
                raise IndexError
            start = self._dtype.bitlength * key
            self._bitstore = BitStore.join([self._bitstore.getslice(0, start),
                                            self._bitstore.getslice(start + self._dtype.bitlength, None)])

    def __repr__(self) -> str:
        list_str = f"{self.unpack()}"
        trailing_bit_length = len(self._bitstore) % self._dtype.bitlength
        final_str = "" if trailing_bit_length == 0 else ", trailing_bits=" + repr(
            self._getbitslice(-trailing_bit_length, None)).splitlines()[0]
        return f"Array('{self._dtype}', {list_str}{final_str})"

    def astype(self, dtype: str | Dtype, /) -> Array:
        """
        Creates and returns a new ``Array`` instance with a specified data type, initialized with the current Array's elements.

        This method allows for the conversion of the Array's elements to a different data type, specified by the `dtype` parameter.
        The conversion process respects the original values of the elements, adapting them to the new data type format.
        This can be useful for changing the representation of data within the Array, for example, from integers to floating-point numbers or vice versa.

        Parameters:
        - `dtype` (Union[str, Dtype]): The target data type for the new Array. This can be specified as a string or as a `Dtype` instance. The string format should match one of the predefined data type codes in the library.

        Returns:
        - `Array`: A new `Array` instance with the specified `dtype`, containing the elements of the current Array converted to the new data type.

        Raises:
        - `ValueError`: If the specified `dtype` is not supported or cannot be applied to the elements of the current Array.

        Example:
        ```python
        original_array = Array('int', [1, 2, 3])
        float_array = original_array.astype('float')
        print(float_array.dtype)  # Output: Dtype('float')
        ```
        """
        new_array = self.__class__(dtype, self.unpack())
        return new_array

    def unpack(self) -> list[ElementType]:
        return [self._dtype.unpack(self._proxy[start:start + self._dtype.bitlength])
                for start in range(0, len(self._proxy) - self._dtype.bitlength + 1, self._dtype.bitlength)]

    def append(self, x: ElementType, /) -> None:
        """
        Append a single item to the end of the Array.

        :param x: The item to append.
        :type x: ElementType
        :return: None
        """
        if len(self._proxy) % self._dtype.bitlength != 0:
            raise ValueError("Cannot append to Array as its length is not a multiple of the format length.")
        self._bitstore = BitStore.join([self._bitstore, self._create_element(x)._bitstore])

    def extend(self, iterable: Array | bytes | bytearray | Bits | Iterable[Any], /) -> None:
        """
        Append new items to the end of the Array from an iterable.

        This method allows you to extend the Array by appending elements from another iterable.
        The iterable can be another Array, bytes, bytearray, Bits, or any other iterable containing elements of a compatible type.

        :param iterable: The iterable containing elements to append to the Array.
        :type iterable: Array, bytes, bytearray, Bits, or any iterable of compatible elements
        :return: None
        """
        if isinstance(iterable, (bytes, bytearray)):
            # extend the bit data by appending on the end
            self._bitstore = BitStore.join([self._bitstore, Bits.from_bytes(iterable)._bitstore])
            return
        if isinstance(iterable, Bits):
            self._bitstore = BitStore.join([self._bitstore, iterable._bitstore])
            return
        if len(self._proxy) % self._dtype.bitlength != 0:
            raise ValueError(f"Cannot extend Array as its data length ({len(self._proxy)} bits) is not a multiple of the format length ({self._dtype.bitlength} bits).")
        if isinstance(iterable, Array):
            if self._dtype != iterable._dtype:
                raise TypeError(
                    f"Cannot extend an Array with format '{self._dtype}' from an Array of format '{iterable._dtype}'.")
            # No need to iterate over the elements, we can just append the data
            self._bitstore = BitStore.join([self._bitstore, iterable._bitstore])
        else:
            if isinstance(iterable, str):
                raise TypeError("Can't extend an Array with a str.")
            self._bitstore = BitStore.join([self._bitstore] + [self._create_element(item)._bitstore for item in iterable])

    def insert(self, pos: int, x: ElementType, /) -> None:
        """
        Insert a new element into the Array at position pos.

        :param pos: The position to insert the item.
        :type pos: int
        :param x: The item to insert.
        :type x: ElementType
        :return: None
        """
        pos = min(pos, len(self))  # Inserting beyond len of Array inserts at the end (copying standard behaviour)
        v = self._create_element(x)
        self._bitstore = BitStore.join([self._bitstore.getslice(0, pos * self._dtype.bitlength), v._bitstore,
                                        self._bitstore.getslice(pos * self._dtype.bitlength, None)])

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

    def byteswap(self) -> None:
        """
        Change the endianness in-place of all items in the Array.

        If the Array format is not a whole number of bytes a ValueError will be raised.

        :return: None
        """
        if self.item_size % 8 != 0:
            raise ValueError(
                f"byteswap can only be used for whole-byte elements. The '{self._dtype}' format is {self._dtype.bitlength} bits long.")
        self.data = self._proxy.byteswap(self.item_size // 8)

    def count(self, value: ElementType, /) -> int:
        """Return count of Array items that equal value.

        value -- The quantity to compare each Array element to. Type should be appropriate for the Array format.

        For floating point types using a value of float('nan') will count the number of elements that are NaN.

        """
        if math.isnan(value):
            return sum(math.isnan(i) for i in self)
        else:
            return sum(i == value for i in self)

    def to_bytes(self) -> bytes:
        """Return the Array data as a bytes object, padding with zero bits if needed.

        Up to seven zero bits will be added at the end to byte align.

        """
        return self._proxy.to_bytes()

    def to_bits(self) -> Bits:
        x = Bits()
        x._bitstore = self._bitstore.copy()
        return x

    def reverse(self) -> None:
        trailing_bit_length = len(self._proxy) % self._dtype.bitlength
        if trailing_bit_length != 0:
            raise ValueError(f"Cannot reverse the items in the Array as its data length ({len(self._proxy)} bits) "
                             f"is not a multiple of the format length ({self._dtype.bitlength} bits).")
        self._bitstore = Bits.join([self._getbitslice(s - self._dtype.bitlength, s) for s in range(len(self._proxy), 0, -self._dtype.bitlength)])._bitstore

    def pp(self, fmt: str | None = None, width: int = 120,
           show_offset: bool = True, stream: TextIO = sys.stdout) -> None:
        """
        Pretty-print the Array contents.

        This method provides a formatted output of the Array's contents, allowing for easy inspection of the data.
        The output can be customized with various parameters to control the format, width, and display options.

        :param fmt: Data format string. Defaults to the current Array dtype.
        :type fmt: str or None
        :param width: Maximum width of printed lines in characters. Defaults to 120. A single group will always be printed per line even if it exceeds the max width.
        :type width: int
        :param show_offset: If True, shows the element offset in the first column of each line.
        :type show_offset: bool
        :param stream: A TextIO object with a write() method. Defaults to sys.stdout.
        :type stream: TextIO
        :return: None
        """
        colour = Colour(not Options().no_color)
        sep = ' '
        dtype2 = None
        tidy_fmt = None
        if fmt is None:
            fmt = self.dtype
            dtype1 = self.dtype
            tidy_fmt = "dtype='" + colour.purple + str(self.dtype) + "'" + colour.off
        else:
            token_list = [token.strip() for token in fmt.split(',')]
            if len(token_list) not in [1, 2]:
                raise ValueError(f"Only one or two tokens can be used in an Array.pp() format - '{fmt}' has {len(token_list)} tokens.")
            name1, length1 = _utils.parse_name_size_token(token_list[0])
            dtype1 = Dtype.from_params(name1, length1)
            if len(token_list) == 2:
                name2, length2 = _utils.parse_name_size_token(token_list[1])
                dtype2 = Dtype.from_params(name2, length2)

        token_length = dtype1.bits_per_item
        if dtype2 is not None:
            # For two types we're OK as long as they don't have different lengths given.
            if dtype1.bits_per_item is not None and dtype2.bits_per_item is not None and dtype1.bits_per_item != dtype2.bits_per_item:
                raise ValueError(f"Two different format lengths specified ('{fmt}'). Either specify just one, or two the same length.")
            if token_length == 0:
                token_length = dtype2.bits_per_item
        if token_length == 0:
            token_length = self.item_size

        if dtype1.is_array or (dtype2 is not None and dtype2.is_array):
            raise ValueError(f"Array.pp() only supports simple Dtypes, not ones which represent arrays.")

        trailing_bit_length = len(self._proxy) % token_length
        format_sep = " : "  # String to insert on each line between multiple formats
        if tidy_fmt is None:
            tidy_fmt = colour.purple + str(dtype1) + colour.off
            if dtype2 is not None:
                tidy_fmt += ', ' + colour.blue + str(dtype2) + colour.off
            tidy_fmt = "fmt='" + tidy_fmt + "'"
        data = self._proxy if trailing_bit_length == 0 else self._getbitslice(0, -trailing_bit_length)
        length = len(self._proxy) // token_length
        len_str = colour.green + str(length) + colour.off
        stream.write(f"<{self.__class__.__name__} {tidy_fmt}, length={len_str}, item_size={token_length} bits, total data size={(len(self._proxy) + 7) // 8} bytes> [\n")
        data._pp(dtype1, dtype2, token_length, width, sep, format_sep, show_offset, stream, token_length)
        stream.write("]")
        if trailing_bit_length != 0:
            stream.write(" + trailing_bits = 0b" + self._getbitslice(-trailing_bit_length, None).unpack('bin'))
        stream.write("\n")

    def equals(self, other: Any, /) -> bool:
        """
        Return True if the format and all Array items are equal to another Array.

        :param other: The other Array to compare with.
        :type other: Any
        :return: True if the Arrays are equal, False otherwise.
        :rtype: bool
        """
        if isinstance(other, Array):
            if self._dtype != other._dtype:
                return False
            if self.data != other.data:
                return False
            return True
        return False

    def __iter__(self) -> Iterable[ElementType]:
        start = 0
        for _ in range(len(self)):
            yield self._dtype.unpack(self._proxy[start:start + self._dtype.bitlength])
            start += self._dtype.bitlength

    def __copy__(self) -> Array:
        a_copy = self.__class__(self._dtype, self.to_bits())
        return a_copy

    def _apply_op_to_all_elements(self, op, value: int | float | None, is_comparison: bool = False) -> Array:
        """Apply op with value to each element of the Array and return a new Array"""
        new_array = self.__class__('bool' if is_comparison else self._dtype)
        new_data = Bits()
        failures = index = 0
        msg = ''
        if value is not None:
            def partial_op(a):
                return op(a, value)
        else:
            def partial_op(a):
                return op(a)
        for i in range(len(self)):
            v = self._dtype.unpack(self._proxy[self._dtype.bitlength * i: self._dtype.bitlength * (i + 1)])
            try:
                new_data += new_array._create_element(partial_op(v))
            except (ZeroDivisionError, ValueError) as e:
                if failures == 0:
                    msg = str(e)
                    index = i
                failures += 1
        if failures != 0:
            raise ValueError(f"Applying operator '{op.__name__}' to Array caused {failures} errors. "
                             f'First error at index {index} was: "{msg}"')
        new_array._bitstore = new_data._bitstore
        return new_array

    def _apply_op_to_all_elements_inplace(self, op, value: int | float) -> Array:
        """Apply op with value to each element of the Array in place."""
        # This isn't really being done in-place, but it's simpler and faster for now?
        new_data = Bits()
        failures = index = 0
        msg = ''
        for i in range(len(self)):
            v = self._dtype.unpack(self._proxy[self._dtype.bitlength * i: self._dtype.bitlength * (i + 1)])
            try:
                new_data += self._create_element(op(v, value))
            except (ZeroDivisionError, ValueError) as e:
                if failures == 0:
                    msg = str(e)
                    index = i
                failures += 1
        if failures != 0:
            raise ValueError(f"Applying operator '{op.__name__}' to Array caused {failures} errors. "
                             f'First error at index {index} was: "{msg}"')
        self._bitstore = new_data._bitstore
        return self

    def _apply_bitwise_op_to_all_elements(self, op, value: BitsType) -> Array:
        """Apply op with value to each element of the Array as an unsigned integer and return a new Array"""
        a_copy = self[:]
        a_copy._apply_bitwise_op_to_all_elements_inplace(op, value)
        return a_copy

    def _apply_bitwise_op_to_all_elements_inplace(self, op, value: BitsType) -> Array:
        """Apply op with value to each element of the Array as an unsigned integer in place."""
        value = Bits.from_auto(value)
        if len(value) != self._dtype.bitlength:
            raise ValueError(f"Bitwise op {op} needs a Bits of length {self._dtype.bitlength} to match format {self._dtype}, but received '{value}' which has a length of {len(value)} bits.")
        for start in range(0, len(self) * self._dtype.bitlength, self._dtype.bitlength):
            self._bitstore.setitem(slice(start, start + self._dtype.bitlength), op(self._bitstore.getslice(start, start + self._dtype.bitlength), value._bitstore))
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
            new_type = Register().get_single_dtype('bool', 1)
        else:
            new_type = self._promotetype(self._dtype, other._dtype)
        new_array = self.__class__(new_type)
        new_data = Bits()
        failures = index = 0
        msg = ''
        for i in range(len(self)):
            a = self._dtype.unpack(self._proxy[self._dtype.bitlength * i: self._dtype.bitlength * (i + 1)])
            b = other._dtype.unpack(other._proxy[other._dtype.bitlength * i: other._dtype.bitlength * (i + 1)])
            try:
                new_data += new_array._create_element(op(a, b))
            except (ValueError, ZeroDivisionError) as e:
                if failures == 0:
                    msg = str(e)
                    index = i
                failures += 1
        if failures != 0:
            raise ValueError(f"Applying operator '{op.__name__}' between Arrays caused {failures} errors. "
                             f'First error at index {index} was: "{msg}"')
        new_array._bitstore = new_data._bitstore
        return new_array

    @classmethod
    def _promotetype(cls, type1: Dtype, type2: Dtype) -> Dtype:  # TODO: How does this work for array dtypes?
        """When combining types which one wins?

        1. We only deal with types representing floats or integers.
        2. One of the two types gets used. We never create a new one.
        3. Floating point types always win against integer types.
        4. Signed integer types always win against unsigned integer types.
        5. Longer types win against shorter types.
        6. In a tie the first type wins against the second type.

        """
        def is_float(x): return x.return_type is float
        def is_int(x): return x.return_type is int or x.return_type is bool
        if is_float(type1) + is_int(type1) + is_float(type2) + is_int(type2) != 2:
            raise ValueError(f"Only integer and floating point types can be combined - not '{type1}' and '{type2}'.")
        # If same type choose the widest
        if type1.name == type2.name:
            return type1 if type1.bits_per_item > type2.bits_per_item else type2
        # We choose floats above integers, irrespective of the widths
        if is_float(type1) and is_int(type2):
            return type1
        if is_int(type1) and is_float(type2):
            return type2
        if is_float(type1) and is_float(type2):
            return type2 if type2.bits_per_item > type1.bits_per_item else type1
        assert is_int(type1) and is_int(type2)
        if type1.is_signed and not type2.is_signed:
            return type1
        if type2.is_signed and not type1.is_signed:
            return type2
        return type2 if type2.bits_per_item > type1.bits_per_item else type1

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
        if isinstance(other, (int, float, str, Bits)):
            return self._apply_op_to_all_elements(op, other, is_comparison=True)
        try:
            other = self.__class__(self.dtype, other)
        except:
            return NotImplemented
        finally:
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