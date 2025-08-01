use crate::bitrust::{bits, helpers, str_to_bits_rust};
use crate::bitrust::{bits_from_any, Bits};
use bits::BitCollection;
use pyo3::exceptions::{PyIndexError, PyTypeError, PyValueError};
use pyo3::prelude::{PyAnyMethods, PyTypeMethods};
use pyo3::types::{PyBool, PySlice};
use pyo3::types::{PySliceMethods, PyType};
use pyo3::{pyclass, pymethods, PyObject, PyRef, PyResult, Python};
use pyo3::{pyfunction, PyRefMut};
use pyo3::{Bound, IntoPyObject, Py, PyAny};
use std::ops::Not;

#[pyfunction]
pub fn mutable_bits_from_any(any: PyObject, py: Python) -> PyResult<MutableBits> {
    let any_bound = any.bind(py);

    if let Ok(any_bits) = any_bound.extract::<PyRef<Bits>>() {
        return Ok(any_bits.to_mutable_bits());
    }

    if let Ok(any_mutable_bits) = any_bound.extract::<PyRef<MutableBits>>() {
        return Ok(any_mutable_bits.__copy__());
    }

    if let Ok(any_string) = any_bound.extract::<String>() {
        let bits = str_to_bits_rust(any_string)?;
        return Ok(bits.to_mutable_bits());
    }
    if let Ok(any_bytes) = any_bound.extract::<Vec<u8>>() {
        let bits = <Bits as BitCollection>::from_bytes(any_bytes);
        return Ok(bits.to_mutable_bits());
    }
    let type_name = match any_bound.get_type().name() {
        Ok(name) => name.to_string(),
        Err(_) => "<unknown>".to_string(),
    };
    Err(PyTypeError::new_err(format!(
        "Cannot convert object of type {} to a MutableBits object.",
        type_name
    )))
}

///     A mutable container of binary data.
///
///     To construct, use a builder 'from' method:
///
///     * ``MutableBits.from_bytes(b)`` - Create directly from a ``bytes`` object.
///     * ``MutableBits.from_string(s)`` - Use a formatted string.
///     * ``MutableBits.from_bools(i)`` - Convert each element in ``i`` to a bool.
///     * ``MutableBits.from_zeros(n)`` - Initialise with ``n`` zero bits.
///     * ``MutableBits.from_ones(n)`` - Initialise with ``n`` one bits.
///     * ``MutableBits.from_random(n, [seed])`` - Initialise with ``n`` pseudo-randomly set bits.
///     * ``MutableBits.from_dtype(dtype, value)`` - Combine a data type with a value.
///     * ``MutableBits.from_joined(iterable)`` - Concatenate an iterable of objects.
///
///     Using the constructor ``MutableBits(s)`` is an alias for ``MutableBits.from_string(s)``.
///
#[pyclass(freelist = 8, module = "bitformat")]
pub struct MutableBits {
    pub(crate) inner: Bits,
}

impl BitCollection for MutableBits {
    fn len(&self) -> usize {
        self.inner.len()
    }
    fn from_zeros(length: usize) -> Self {
        Self {
            inner: <Bits as BitCollection>::from_zeros(length),
        }
    }
    fn from_ones(length: usize) -> Self {
        Self {
            inner: <Bits as BitCollection>::from_ones(length),
        }
    }
    fn from_bytes(data: Vec<u8>) -> Self {
        Self {
            inner: <Bits as BitCollection>::from_bytes(data),
        }
    }
    fn from_bin(binary_string: &str) -> Result<Self, String> {
        Ok(Self {
            inner: <Bits as BitCollection>::from_bin(binary_string)?,
        })
    }
    fn from_oct(oct: &str) -> Result<Self, String> {
        Ok(Self {
            inner: <Bits as BitCollection>::from_oct(oct)?,
        })
    }
    fn from_hex(hex: &str) -> Result<Self, String> {
        Ok(Self {
            inner: <Bits as BitCollection>::from_hex(hex)?,
        })
    }
    fn from_u64(value: u64, length: usize) -> Self {
        Self {
            inner: <Bits as BitCollection>::from_u64(value, length),
        }
    }
    fn from_i64(value: i64, length: usize) -> Self {
        Self {
            inner: <Bits as BitCollection>::from_i64(value, length),
        }
    }
    fn logical_or(&self, other: &Bits) -> Self {
        Self {
            inner: self.inner.logical_or(other),
        }
    }
    fn logical_and(&self, other: &Bits) -> Self {
        Self {
            inner: self.inner.logical_and(other),
        }
    }
    fn logical_xor(&self, other: &Bits) -> Self {
        Self {
            inner: self.inner.logical_xor(other),
        }
    }
}

impl PartialEq for MutableBits {
    fn eq(&self, other: &Self) -> bool {
        self.inner.data == other.inner.data
    }
}

impl PartialEq<Bits> for MutableBits {
    fn eq(&self, other: &Bits) -> bool {
        self.inner.data == other.data
    }
}

impl MutableBits {
    pub fn new(bv: helpers::BV) -> Self {
        Self {
            inner: Bits::new(bv),
        }
    }
    pub fn to_bin(&self) -> String {
        self.inner.to_bin()
    }
    pub fn to_hex(&self) -> String {
        self.inner.to_hex()
    }
}

#[pymethods]
impl MutableBits {
    /// Return True if two MutableBits have the same binary representation.
    ///
    /// The right hand side will be promoted to a MutableBits if needed and possible.
    ///
    /// >>> MutableBits('0xf2') == '0b11110010'
    /// True
    ///
    pub fn __eq__(&self, other: PyObject, py: Python) -> PyResult<bool> {
        let other_bits = bits_from_any(other, py)?;
        Ok(self.inner.data == other_bits.data)
    }

    /// Return string representations for printing.
    pub fn __str__(&self) -> String {
        self.inner.__str__()
    }

    /// Return representation that could be used to recreate the instance.
    pub fn __repr__(&self, py: Python) -> String {
        let class_name = py.get_type::<Self>().name().unwrap();
        format!("{}('{}')", class_name, self.__str__())
    }

    pub fn _byte_swap(&mut self) -> PyResult<()> {
        if self.inner.data.len() % 8 != 0 {
            return Err(PyValueError::new_err(format!(
                "Cannot use byte_swap as not a whole number of bytes ({} bits long).",
                self.inner.data.len()
            )));
        }
        let mut bytes = self.inner._slice_to_bytes(0, self.len())?;
        bytes.reverse();
        self.inner.data = helpers::BV::from_vec(bytes);
        Ok(())
    }

    pub fn _overwrite(&mut self, start: usize, value: &Bits) -> PyResult<()> {
        if start + value.len() > self.len() {
            return Err(PyIndexError::new_err("Slice out of bounds"));
        }
        self.inner.data[start..start + value.len()].copy_from_bitslice(&value.data);
        Ok(())
    }

    pub fn _set_slice(&mut self, start: usize, end: usize, value: &Bits) -> PyResult<()> {
        if end - start == value.len() {
            // This is an overwrite, so no need to move data around.
            return self._overwrite(start, value);
        }
        let data = std::mem::take(&mut self.inner.data);
        let start_slice = data[..start].to_bitvec();
        let end_slice = data[end..].to_bitvec();

        let mut new_data = start_slice;
        new_data.extend(&value.data);
        new_data.extend(end_slice);

        self.inner.data = new_data;
        Ok(())
    }

    pub fn _ixor(&mut self, other: &MutableBits) -> PyResult<()> {
        if self.len() != other.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }

        self.inner.data ^= &other.inner.data;
        Ok(())
    }

    pub fn _ior(&mut self, other: &MutableBits) -> PyResult<()> {
        if self.len() != other.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }

        self.inner.data |= &other.inner.data;
        Ok(())
    }

    pub fn _iand(&mut self, other: &MutableBits) -> PyResult<()> {
        if self.len() != other.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }

        self.inner.data &= &other.inner.data;
        Ok(())
    }

    pub fn _or(&self, other: &Bits) -> PyResult<Self> {
        if self.len() != other.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }
        Ok(MutableBits::logical_or(self, other))
    }

    pub fn _and(&self, other: &Bits) -> PyResult<Self> {
        if self.len() != other.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }
        Ok(MutableBits::logical_and(self, other))
    }

    pub fn _xor(&self, other: &Bits) -> PyResult<Self> {
        if self.len() != other.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }
        Ok(MutableBits::logical_xor(self, other))
    }

    #[staticmethod]
    pub fn _from_u64(value: u64, length: usize) -> Self {
        BitCollection::from_u64(value, length)
    }

    #[staticmethod]
    pub fn _from_i64(value: i64, length: usize) -> Self {
        BitCollection::from_i64(value, length)
    }

    /// Create a new instance with all bits set to zero.
    ///
    /// :param n: The number of bits.
    /// :return: A MutableBits object with all bits set to zero.
    ///
    /// .. code-block:: python
    ///
    ///     a = MutableBits.from_zeros(500)  # 500 zero bits
    ///
    #[classmethod]
    pub fn from_zeros(_cls: &Bound<'_, PyType>, length: i64) -> PyResult<Self> {
        if length < 0 {
            return Err(PyValueError::new_err(format!(
                "Negative bit length given: {}.",
                length
            )));
        }
        Ok(BitCollection::from_zeros(length as usize))
    }

    /// Create a new instance with all bits set to one.
    ///
    /// :param n: The number of bits.
    ///
    /// .. code-block:: pycon
    ///
    ///     >>> MutableBits.from_ones(5)
    ///     MutableBits('0b11111')
    ///
    #[classmethod]
    pub fn from_ones(_cls: &Bound<'_, PyType>, length: i64) -> PyResult<Self> {
        if length < 0 {
            return Err(PyValueError::new_err(format!(
                "Negative bit length given: {}.",
                length
            )));
        }
        Ok(BitCollection::from_ones(length as usize))
    }

    #[staticmethod]
    pub fn _from_bools(values: Vec<PyObject>, py: Python) -> PyResult<Self> {
        let mut bv = helpers::BV::with_capacity(values.len());

        for value in values {
            let b: bool = value.extract(py)?;
            bv.push(b);
        }
        Ok(Self {
            inner: Bits::new(bv),
        })
    }

    /// Create a new instance from a bytes object.
    ///
    /// :param b: The bytes object to convert to a :class:`MutableBits`.
    ///
    /// .. code-block:: python
    ///
    ///     a = MutableBits.from_bytes(b"some_bytes_maybe_from_a_file")
    ///
    #[classmethod]
    pub fn from_bytes(_cls: &Bound<'_, PyType>, data: Vec<u8>) -> Self {
        BitCollection::from_bytes(data)
    }

    #[staticmethod]
    pub fn _from_bytes_with_offset(data: Vec<u8>, offset: usize) -> Self {
        Self {
            inner: Bits::_from_bytes_with_offset(data, offset),
        }
    }

    // TODO: Are these used?
    #[staticmethod]
    pub fn _from_bin_checked(binary_string: &str) -> PyResult<Self> {
        match BitCollection::from_bin(binary_string) {
            Ok(bits) => Ok(bits),
            Err(e) => Err(PyValueError::new_err(e)),
        }
    }

    #[staticmethod]
    pub fn _from_hex_checked(hex: &str) -> PyResult<Self> {
        match BitCollection::from_hex(hex) {
            Ok(bits) => Ok(bits),
            Err(e) => Err(PyValueError::new_err(e)),
        }
    }

    #[staticmethod]
    pub fn _from_oct_checked(oct: &str) -> PyResult<Self> {
        match BitCollection::from_oct(oct) {
            Ok(bits) => Ok(bits),
            Err(e) => Err(PyValueError::new_err(e)),
        }
    }

    #[staticmethod]
    pub fn _from_joined(py_bits_vec: Vec<PyRef<Bits>>) -> Self {
        let bits_vec: Vec<&Bits> = py_bits_vec.iter().map(|x| &**x).collect();
        let total_len: usize = bits_vec.iter().map(|b| b.len()).sum();
        let mut bv = helpers::BV::with_capacity(total_len);
        for bits in bits_vec {
            bv.extend_from_bitslice(&bits.data);
        }
        MutableBits::new(bv)
    }

    pub fn _to_u64(&self, start: usize, length: usize) -> u64 {
        self.inner._to_u64(start, length)
    }

    pub fn _to_i64(&self, start: usize, length: usize) -> i64 {
        self.inner._to_i64(start, length)
    }

    pub fn __len__(&self) -> usize {
        self.inner.len()
    }

    pub fn _getindex(&self, bit_index: i64) -> PyResult<bool> {
        self.inner._getindex(bit_index)
    }

    pub fn _getslice(&self, start_bit: usize, end_bit: usize) -> PyResult<Self> {
        self.inner
            ._getslice(start_bit, end_bit)
            .map(|bits| MutableBits { inner: bits })
    }

    pub fn _get_slice_unchecked(&self, start_bit: usize, length: usize) -> Self {
        MutableBits {
            inner: self.inner._get_slice_unchecked(start_bit, length),
        }
    }

    pub fn _getslice_with_step(&self, start_bit: i64, end_bit: i64, step: i64) -> PyResult<Self> {
        self.inner
            ._getslice_with_step(start_bit, end_bit, step)
            .map(|bits| MutableBits { inner: bits })
    }

    pub fn __getitem__(&self, key: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let py = key.py();
        // Handle integer indexing
        if let Ok(index) = key.extract::<i64>() {
            let value: bool = self._getindex(index)?;
            let py_value = PyBool::new(py, value);
            return Ok(py_value.to_owned().into());
        }

        // Handle slice indexing
        if let Ok(slice) = key.downcast::<PySlice>() {
            let indices = slice.indices(self.len() as isize)?;
            let start: i64 = indices.start.try_into().unwrap();
            let stop: i64 = indices.stop.try_into().unwrap();
            let step: i64 = indices.step.try_into().unwrap();

            let result = if step == 1 {
                self._getslice(start as usize, stop as usize)?
            } else {
                self._getslice_with_step(start, stop, step)?
            };
            let py_obj = Py::new(py, result)?.into_pyobject(py)?;
            return Ok(py_obj.into());
        }

        Err(pyo3::exceptions::PyTypeError::new_err(
            "Index must be an integer or a slice.",
        ))
    }

    /// Return the MutableBits as bytes, padding with zero bits if needed.
    ///
    /// Up to seven zero bits will be added at the end to byte align.
    ///
    /// :return: The MutableBits as bytes.
    ///
    pub fn to_bytes(&self) -> Vec<u8> {
        self.inner.to_bytes()
    }

    pub fn _slice_to_bin(&self, start: usize, end: usize) -> String {
        self.inner._slice_to_bin(start, end)
    }

    pub fn _slice_to_oct(&self, start: usize, end: usize) -> PyResult<String> {
        self.inner._slice_to_oct(start, end)
    }

    pub fn _slice_to_hex(&self, start: usize, end: usize) -> PyResult<String> {
        self.inner._slice_to_hex(start, end)
    }

    pub fn _slice_to_bytes(&self, start: usize, end: usize) -> PyResult<Vec<u8>> {
        self.inner._slice_to_bytes(start, end)
    }

    pub fn _to_int_byte_data(&self, signed: bool) -> Vec<u8> {
        self.inner._to_int_byte_data(signed)
    }

    /// Return count of total number of either zero or one bits.
    ///
    ///     :param value: If `bool(value)` is True, bits set to 1 are counted; otherwise, bits set to 0 are counted.
    ///     :return: The count of bits set to 1 or 0.
    ///
    ///     .. code-block:: pycon
    ///
    ///         >>> MutableBits('0xef').count(1)
    ///         7
    ///
    pub fn count(&self, value: PyObject, py: Python) -> PyResult<usize> {
        self.inner.count(value, py)
    }

    /// Return True if all bits are equal to 1, otherwise return False.
    ///
    /// :return: ``True`` if all bits are 1, otherwise ``False``.
    ///
    /// .. code-block:: pycon
    ///
    ///     >>> MutableBits('0b1111').all()
    ///     True
    ///     >>> MutableBits('0b1011').all()
    ///     False
    ///
    pub fn all(&self) -> bool {
        self.inner.all()
    }

    /// Return True if any bits are equal to 1, otherwise return False.
    ///
    /// :return: ``True`` if any bits are 1, otherwise ``False``.
    ///
    /// .. code-block:: pycon
    ///
    ///     >>> MutableBits('0b0000').any()
    ///     False
    ///     >>> MutableBits('0b1000').any()
    ///     True
    ///
    pub fn any(&self) -> bool {
        self.inner.any()
    }

    pub fn _find(&self, b: &Bits, start: usize, bytealigned: bool) -> Option<usize> {
        self.inner._find(b, start, bytealigned)
    }

    pub fn _rfind(&self, b: &Bits, start: usize, bytealigned: bool) -> Option<usize> {
        self.inner._rfind(b, start, bytealigned)
    }

    /// Return the MutableBits with one or many bits inverted between 0 and 1.
    ///
    /// :param pos: Either a single bit position or an iterable of bit positions.
    /// :return: self
    ///
    /// Raises IndexError if pos < -len(self) or pos >= len(self).
    ///
    /// .. code-block:: pycon
    ///
    ///     >>> a = MutableBits('0b10111')
    ///     >>> a.invert(1)
    ///     MutableBits('0b11111')
    ///     >>> a.invert([0, 2])
    ///     MutableBits('0b01011')
    ///     >>> a.invert()
    ///     MutableBits('0b10100')
    ///
    #[pyo3(signature = (pos = None))]
    pub fn invert<'a>(
        mut slf: PyRefMut<'a, Self>,
        pos: Option<&Bound<'a, PyAny>>,
    ) -> PyResult<PyRefMut<'a, Self>> {
        match pos {
            None => {
                slf.inner.data = std::mem::take(&mut slf.inner.data).not();
            }
            Some(p) => {
                if let Ok(pos) = p.extract::<i64>() {
                    let pos: usize = helpers::validate_index(pos, slf.len())?;
                    let value = slf.inner.data[pos];
                    slf.inner.data.set(pos, !value);
                } else if let Ok(pos_list) = p.extract::<Vec<i64>>() {
                    for pos in pos_list {
                        let pos: usize = helpers::validate_index(pos, slf.len())?;
                        let value = slf.inner.data[pos];
                        slf.inner.data.set(pos, !value);
                    }
                } else {
                    return Err(PyTypeError::new_err(
                        "invert() argument must be an integer, an iterable of ints, or None",
                    ));
                }
            }
        }
        Ok(slf)
    }

    /// Reverse bits in-place.
    ///
    /// :return: self
    ///
    /// .. code-block:: pycon
    ///
    ///     >>> a = MutableBits('0b1011')
    ///     >>> a.reverse()
    ///     MutableBits('0b1101')
    ///
    pub fn reverse(mut slf: PyRefMut<'_, Self>) -> PyRefMut<'_, Self> {
        slf.inner.data.reverse();
        slf
    }

    /// Return the instance with every bit inverted.
    ///
    /// Raises ValueError if the MutableBits is empty.
    ///
    pub fn __invert__(&self) -> PyResult<Self> {
        if self.inner.data.is_empty() {
            return Err(PyValueError::new_err("Cannot invert empty MutableBits."));
        }
        Ok(MutableBits::new(self.inner.data.clone().not()))
    }

    /// Return new MutableBits shifted by n to the left.
    ///
    /// n -- the number of bits to shift. Must be >= 0.
    ///
    pub fn __lshift__(&self, n: i64) -> PyResult<Self> {
        Ok(MutableBits::new(self.inner.__lshift__(n)?.data))
    }

    /// Return new MutableBits shifted by n to the right.
    ///
    /// n -- the number of bits to shift. Must be >= 0.
    ///
    pub fn __rshift__(&self, n: i64) -> PyResult<Self> {
        Ok(MutableBits::new(self.inner.__rshift__(n)?.data))
    }

    pub fn _set_from_sequence(&mut self, value: bool, indices: Vec<i64>) -> PyResult<()> {
        for idx in indices {
            let pos: usize = helpers::validate_index(idx, self.inner.len())?;
            self.inner.data.set(pos, value);
        }
        Ok(())
    }

    pub fn _set_index(&mut self, value: bool, index: i64) -> PyResult<()> {
        self._set_from_sequence(value, vec![index])
    }

    pub fn _set_from_slice(
        &mut self,
        value: bool,
        start: i64,
        stop: i64,
        step: i64,
    ) -> PyResult<()> {
        let len = self.inner.len() as i64;
        let mut positive_start = if start < 0 { start + len } else { start };
        let mut positive_stop = if stop < 0 { stop + len } else { stop };

        if positive_start < 0 || positive_start >= len {
            return Err(PyIndexError::new_err("Start of slice out of bounds."));
        }
        if positive_stop < 0 || positive_stop > len {
            return Err(PyIndexError::new_err("End of slice out of bounds."));
        }
        if step == 0 {
            return Err(PyValueError::new_err("Step cannot be zero."));
        }
        if step < 0 {
            positive_stop = positive_start - 1;
            positive_start = positive_stop - (positive_stop - positive_start) / step;
        }
        let positive_step = if step > 0 {
            step as usize
        } else {
            -step as usize
        };

        let mut index = positive_start as usize;
        let stop = positive_stop as usize;

        while index < stop {
            unsafe {
                self.inner.data.set_unchecked(index, value);
            }
            index += positive_step;
        }

        Ok(())
    }

    /// Return a new copy of the MutableBits for the copy module.
    pub fn __copy__(&self) -> Self {
        MutableBits::new(self.inner.data.clone())
    }

    /// Create and return an immutable copy of the MutableBits as Bits instance.
    pub fn to_bits(&self) -> Bits {
        Bits::new(self.inner.data.clone())
    }

    // TODO: Should this be part of the API? Is it useful in Python?
    /// Convert to immutable Bits - without cloning the data.
    pub fn _as_immutable(&mut self) -> Bits {
        let data = std::mem::take(&mut self.inner.data);
        Bits::new(data)
    }

    /// Append bits to the end of the current MutableBits in-place.
    ///
    /// :param bs: The bits to append.
    /// :return: self
    ///
    /// .. code-block:: pycon
    ///
    ///     >>> a = MutableBits('0x0f')
    ///     >>> a.append('0x0a')
    ///     MutableBits('0x0f0a')
    ///
    pub fn append<'a>(
        mut slf: PyRefMut<'a, Self>,
        bs: PyObject,
        py: Python<'_>,
    ) -> PyResult<PyRefMut<'a, Self>> {
        // Check if bs is the same object as slf
        // let pointless = slf.clone();
        // let slf_obj = pointless.into_pyobject(py)?;
        // if bs.is(&slf_obj) {
        //     // If bs is slf, clone inner bits first then append
        //     let bits_clone = slf.inner.clone();
        //     slf.inner.data.extend(bits_clone.data);
        // } else {
        // Normal case - convert bs to Bits and append
        let bs = bits_from_any(bs, py)?;
        slf.inner.data.extend(bs.data);
        // }
        Ok(slf)
    }

    // TODO: append and prepend don't work if used with themselves. They need a 'if bs is self' check.

    ///Prepend bits to the beginning of the current MutableBits in-place.
    ///
    /// :param bs: The bits to prepend.
    /// :return: self
    ///
    /// .. code-block:: pycon
    ///
    ///     >>> a = MutableBits('0x0f')
    ///     >>> a.prepend('0x0a')
    ///     MutableBits('0x0a0f')
    ///
    pub fn prepend<'a>(
        mut slf: PyRefMut<'a, Self>,
        bs: PyObject,
        py: Python<'_>,
    ) -> PyResult<PyRefMut<'a, Self>> {
        let self_data = std::mem::take(&mut slf.inner.data);
        let mut new_data = mutable_bits_from_any(bs, py)?;
        new_data.inner.data.extend(self_data);
        slf.inner.data = new_data.inner.data;
        Ok(slf)
    }

    /// In-place left shift
    pub fn _lshift_inplace(&mut self, n: i64) -> PyResult<()> {
        let shift = self.inner._validate_shift(n)?;
        self.inner.data.shift_left(shift);
        Ok(())
    }

    /// In-place right shift
    pub fn _rshift_inplace(&mut self, n: i64) -> PyResult<()> {
        let shift = self.inner._validate_shift(n)?;
        self.inner.data.shift_right(shift);
        Ok(())
    }
}
