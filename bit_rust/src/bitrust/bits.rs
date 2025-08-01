use crate::bitrust::helpers;
use crate::bitrust::BitsBoolIterator;
use crate::bitrust::MutableBits;
use bitvec::prelude::*;
use bytemuck;
use pyo3::conversion::IntoPyObject;
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyBool;
use pyo3::types::PySlice;
use pyo3::types::PyType;
use pyo3::{pyclass, pymethods, PyRef, PyResult};
use std::fmt;
use std::fmt::Write;
use std::num::NonZeroUsize;
use std::ops::Not;

use lru::LruCache;
use once_cell::sync::Lazy;
use std::sync::Mutex;

// Define a static LRU cache with capacity of 256 items
static BITS_CACHE: Lazy<Mutex<LruCache<String, helpers::BV>>> =
    Lazy::new(|| Mutex::new(LruCache::new(NonZeroUsize::new(256).unwrap())));

static DTYPE_PARSER: Lazy<Mutex<Option<PyObject>>> = Lazy::new(|| Mutex::new(None));

pub fn split_tokens(s: String) -> Vec<String> {
    // Remove whitespace
    let s: String = s.chars().filter(|c| !c.is_whitespace()).collect();
    let mut tokens = Vec::new();
    let mut token_start = 0;
    let mut bracket_depth = 0;
    // Find all the commas, ignoring those in other structures.
    // This isn't a rigorous check - if brackets are mismatched it will be picked up later.

    for (i, c) in s.char_indices() {
        if c == ',' && bracket_depth == 0 {
            tokens.push(s[token_start..i].to_string());
            token_start = i + 1;
        } else if c == '(' || c == '[' {
            bracket_depth += 1;
        } else if c == ')' || c == ']' {
            bracket_depth -= 1;
        }
    }
    tokens.push(s[token_start..].to_string());
    tokens
}

pub fn string_literal_to_bits(s: String) -> PyResult<Bits> {
    if s.starts_with("0x") {
        return Bits::_from_hex(&s);
    } else if s.starts_with("0o") {
        return Bits::_from_oct(&s);
    } else if s.starts_with("0b") {
        return Bits::_from_bin(&s);
    }

    Err(PyValueError::new_err(format!(
        "Can't parse token '{}'. Did you mean to prefix with '0x', '0b' or '0o'?",
        s
    )))
}

#[pyfunction]
pub fn str_to_bits_rust(s: String) -> PyResult<Bits> {
    // Check cache first
    {
        let mut cache = BITS_CACHE.lock().unwrap();
        if let Some(cached_data) = cache.get(&s) {
            return Ok(Bits::new(cached_data.clone()));
        }
    }
    let tokens = split_tokens(s.clone());
    let mut bits_array = Vec::<Bits>::new();

    for token in tokens {
        if token.is_empty() {
            continue;
        }
        match string_literal_to_bits(token.clone()) {
            Ok(bits) => bits_array.push(bits),
            Err(_) => {
                // Call out to the Python dtype parser - see if it can handle it.
                Python::with_gil(|py| -> PyResult<()> {
                    // Only access the parser inside this scope
                    let parser_guard = DTYPE_PARSER.lock().unwrap();
                    let parser = match &*parser_guard {
                        Some(p) => p,
                        None => {
                            return Err(PyValueError::new_err(
                                "dtype_parser has not been set. Call set_dtype_parser first",
                            ));
                        }
                    };
                    let dtype_parser = parser.bind(py);
                    let result = dtype_parser.call1((token.clone(),))?;
                    // Convert result
                    let bits_ref = result.extract::<PyRef<Bits>>()?;
                    bits_array.push(Bits::new(bits_ref.data.clone()));
                    Ok(())
                })?; // Propagate any Python errors
            }
        }
    }
    // Combine all bits
    let result = if bits_array.is_empty() {
        Bits::new(helpers::BV::repeat(false, 0))
    } else if bits_array.len() == 1 {
        bits_array.remove(0)
    } else {
        //  (TODO: Use other method)
        let total_len: usize = bits_array.iter().map(|b| b.len()).sum();
        let mut result = helpers::BV::with_capacity(total_len);

        for bits in bits_array {
            result.extend_from_bitslice(&bits.data);
        }

        Bits::new(result)
    };
    // Update cache with new result
    {
        let mut cache = BITS_CACHE.lock().unwrap();
        cache.put(s, result.data.clone());
    }

    Ok(result)
}

#[pyfunction]
pub fn set_dtype_parser(dtype_parser: PyObject) -> PyResult<()> {
    // Store the Python object directly - no conversion needed
    let mut parser_guard = DTYPE_PARSER.lock().unwrap();
    *parser_guard = Some(dtype_parser);
    Ok(())
}

#[pyfunction]
pub fn bits_from_any(any: PyObject, py: Python) -> PyResult<Bits> {
    let any_bound = any.bind(py);

    if let Ok(any_bits) = any_bound.extract::<PyRef<Bits>>() {
        return Ok(any_bits._clone_as_immutable());
    }

    if let Ok(any_mutable_bits) = any_bound.extract::<PyRef<MutableBits>>() {
        return Ok(any_mutable_bits.to_bits());
    }

    if let Ok(any_string) = any_bound.extract::<String>() {
        return str_to_bits_rust(any_string);
    }
    if let Ok(any_bytes) = any_bound.extract::<Vec<u8>>() {
        return Ok(<Bits as BitCollection>::from_bytes(any_bytes));
    }
    let type_name = match any_bound.get_type().name() {
        Ok(name) => name.to_string(),
        Err(_) => "<unknown>".to_string(),
    };
    Err(PyTypeError::new_err(format!(
        "Cannot convert object of type {} to a Bits object.",
        type_name
    )))
}

pub trait BitCollection: Sized {
    fn len(&self) -> usize;
    fn from_zeros(length: usize) -> Self;
    fn from_ones(length: usize) -> Self;
    fn from_bytes(data: Vec<u8>) -> Self;
    fn from_bin(binary_string: &str) -> Result<Self, String>;
    fn from_oct(octal_string: &str) -> Result<Self, String>;
    fn from_hex(hex_string: &str) -> Result<Self, String>;
    fn from_u64(value: u64, length: usize) -> Self;
    fn from_i64(value: i64, length: usize) -> Self;
    fn logical_or(&self, other: &Bits) -> Self;
    fn logical_and(&self, other: &Bits) -> Self;
    fn logical_xor(&self, other: &Bits) -> Self;
}

///     An immutable container of binary data.
///
///     To construct, use a builder 'from' method:
///
///     * ``Bits.from_bytes(b)`` - Create directly from a ``bytes`` object.
///     * ``Bits.from_string(s)`` - Use a formatted string.
///     * ``Bits.from_bools(i)`` - Convert each element in ``i`` to a bool.
///     * ``Bits.from_zeros(n)`` - Initialise with ``n`` zero bits.
///     * ``Bits.from_ones(n)`` - Initialise with ``n`` one bits.
///     * ``Bits.from_random(n, [seed])`` - Initialise with ``n`` pseudo-randomly set bits.
///     * ``Bits.from_dtype(dtype, value)`` - Combine a data type with a value.
///     * ``Bits.from_joined(iterable)`` - Concatenate an iterable of objects.
///
///     Using the constructor ``Bits(s)`` is an alias for ``Bits.from_string(s)``.
///
#[derive(Clone)]
#[pyclass(frozen, freelist = 8, module = "bitformat")]
pub struct Bits {
    pub(crate) data: helpers::BV,
}

impl fmt::LowerHex for Bits {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.len() % 4 != 0 {
            return Err(std::fmt::Error);
        }
        for chunk in self.data.chunks(4) {
            let nibble = chunk.load_be::<u8>();
            let hex_char = std::char::from_digit(nibble as u32, 16).unwrap();
            f.write_char(hex_char)?;
        }
        Ok(())
    }
}

impl fmt::Octal for Bits {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.len() % 3 != 0 {
            return Err(std::fmt::Error);
        }
        for chunk in self.data.chunks(3) {
            let tribble = chunk.load_be::<u8>();
            let oct_char = std::char::from_digit(tribble as u32, 8).unwrap();
            f.write_char(oct_char)?;
        }
        Ok(())
    }
}

impl fmt::Binary for Bits {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        for bit in self.data.iter() {
            f.write_char(if *bit { '1' } else { '0' })?;
        }
        Ok(())
    }
}

impl BitCollection for Bits {
    fn len(&self) -> usize {
        self.data.len()
    }
    fn from_zeros(length: usize) -> Self {
        Bits::new(helpers::BV::repeat(false, length))
    }
    fn from_ones(length: usize) -> Self {
        Bits::new(helpers::BV::repeat(true, length))
    }
    fn from_bytes(data: Vec<u8>) -> Self {
        let bits = data.view_bits::<Msb0>();
        let bv = helpers::BV::from_bitslice(bits);
        Bits::new(bv)
    }

    fn from_bin(binary_string: &str) -> Result<Self, String> {
        // Ignore any leading '0b'
        let s = binary_string.strip_prefix("0b").unwrap_or(binary_string);
        let mut b: helpers::BV = helpers::BV::with_capacity(s.len());
        for c in s.chars() {
            match c {
                '0' => b.push(false),
                '1' => b.push(true),
                '_' => continue,
                c if c.is_whitespace() => continue,
                _ => {
                    return Err(format!(
                        "Cannot convert from bin '{binary_string}: Invalid character '{c}'."
                    ))
                }
            }
        }
        b.set_uninitialized(false);
        Ok(Bits::new(b))
    }
    fn from_oct(octal_string: &str) -> Result<Self, String> {
        // Ignore any leading '0o'
        let s = octal_string.strip_prefix("0o").unwrap_or(octal_string);
        let mut b: helpers::BV = helpers::BV::with_capacity(s.len() * 3);
        for c in s.chars() {
            match c {
                '0' => b.extend_from_bitslice(bits![0, 0, 0]),
                '1' => b.extend_from_bitslice(bits![0, 0, 1]),
                '2' => b.extend_from_bitslice(bits![0, 1, 0]),
                '3' => b.extend_from_bitslice(bits![0, 1, 1]),
                '4' => b.extend_from_bitslice(bits![1, 0, 0]),
                '5' => b.extend_from_bitslice(bits![1, 0, 1]),
                '6' => b.extend_from_bitslice(bits![1, 1, 0]),
                '7' => b.extend_from_bitslice(bits![1, 1, 1]),
                '_' => continue,
                c if c.is_whitespace() => continue,
                _ => {
                    return Err(format!(
                        "Cannot convert from oct '{octal_string}': Invalid character '{c}'."
                    ))
                }
            }
        }
        Ok(Bits::new(b))
    }

    fn from_hex(hex: &str) -> Result<Self, String> {
        // Ignore any leading '0x'
        let mut new_hex = hex.strip_prefix("0x").unwrap_or(hex).to_string();
        // Remove any underscores or whitespace characters
        new_hex.retain(|c| c != '_' && !c.is_whitespace());
        let is_odd_length: bool = new_hex.len() % 2 != 0;
        if is_odd_length {
            new_hex.push('0');
        }
        let data = match hex::decode(new_hex) {
            Ok(d) => d,
            Err(e) => return Err(format!("Cannot convert from hex '{hex}': {}", e)),
        };
        let mut bv = <Bits as BitCollection>::from_bytes(data).data;
        if is_odd_length {
            bv.drain(bv.len() - 4..bv.len());
        }
        Ok(Bits::new(bv))
    }
    fn from_u64(value: u64, length: usize) -> Self {
        let mut bv = helpers::BV::repeat(false, length);
        bv.store_be(value);
        Bits::new(bv)
    }
    fn from_i64(value: i64, length: usize) -> Self {
        let mut bv = helpers::BV::repeat(false, length);
        bv.store_be(value);
        Bits::new(bv)
    }
    fn logical_or(&self, other: &Bits) -> Self {
        if self.len() != other.len() {
            panic!("Cannot perform logical OR on Bits of different lengths.");
        }
        let result = self.data.clone() | &other.data;
        Bits::new(result)
    }
    fn logical_and(&self, other: &Bits) -> Self {
        if self.len() != other.len() {
            panic!("Cannot perform logical AND on Bits of different lengths.");
        }
        let result = self.data.clone() & &other.data;
        Bits::new(result)
    }
    fn logical_xor(&self, other: &Bits) -> Self {
        if self.len() != other.len() {
            panic!("Cannot perform logical XOR on Bits of different lengths.");
        }
        let result = self.data.clone() ^ &other.data;
        Bits::new(result)
    }
}

impl fmt::Debug for Bits {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.len() > 100 {
            return f
                .debug_struct("Bits")
                .field(
                    "hex",
                    &self.slice(0, 100)._slice_to_hex(0, self.len()).unwrap(),
                )
                .field("length", &self.len())
                .finish();
        }
        if self.len() % 4 == 0 {
            return f
                .debug_struct("Bits")
                .field("hex", &self._slice_to_hex(0, self.len()).unwrap())
                .field("length", &self.len())
                .finish();
        }
        f.debug_struct("Bits")
            .field("bin", &self.to_bin())
            .field("length", &self.len())
            .finish()
    }
}

impl PartialEq for Bits {
    fn eq(&self, other: &Self) -> bool {
        self.data == other.data
    }
}

impl PartialEq<MutableBits> for Bits {
    fn eq(&self, other: &MutableBits) -> bool {
        self.data == other.inner.data
    }
}

/// Private helper methods. Not part of the Python interface.
impl Bits {
    pub fn new(bv: helpers::BV) -> Self {
        Bits { data: bv }
    }

    /// Slice used internally without bounds checking.
    fn slice(&self, start_bit: usize, length: usize) -> Self {
        Bits::new(BitVec::from_bitslice(
            &self.data[start_bit..start_bit + length],
        ))
    }

    pub(crate) fn to_bin(&self) -> String {
        format!("{:b}", self)
    }

    pub(crate) fn to_hex(&self) -> String {
        if self.len() % 4 != 0 {
            panic!(
                "Cannot interpret as hex - length of {} is not a multiple of 4 bits.",
                self.len()
            );
        }
        format!("{:x}", self)
    }
}

#[pyclass(name = "BitsFindAllIterator")]
pub struct PyBitsFindAllIterator {
    pub haystack: Py<Bits>, // Py<T> keeps the Python object alive
    pub needle: Py<Bits>,
    pub current_pos: usize,
    pub byte_aligned: bool,
    pub step: usize,
}

#[pymethods]
impl PyBitsFindAllIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<'_, Self>) -> PyResult<Option<usize>> {
        let py = slf.py();

        // Read values from slf that are needed for the find logic
        // or for updating state *after* the find.
        let current_pos = slf.current_pos;
        let byte_aligned = slf.byte_aligned;
        let step = slf.step; // Needed to update slf.current_pos later

        // This block limits the scope of haystack_rs and needle_rs.
        // The immutable borrows of slf (to access slf.haystack and slf.needle)
        // will end when this block finishes.
        let find_result = {
            let haystack_rs = slf.haystack.borrow(py);
            let needle_rs = slf.needle.borrow(py);

            let needle_len = needle_rs.len();
            if needle_len == 0 {
                // If needle is empty, stop iteration.
                return Ok(None);
            }

            let haystack_len = haystack_rs.len();
            if current_pos >= haystack_len || haystack_len.saturating_sub(current_pos) < needle_len
            {
                return Ok(None); // No space left for the needle or already past the end
            }
            if byte_aligned {
                helpers::find_bitvec_bytealigned(&haystack_rs, &needle_rs, current_pos)
            } else {
                helpers::find_bitvec(&haystack_rs, &needle_rs, current_pos)
            }
        };

        // Now, `slf` can be mutably accessed without conflicting with the previous borrows.
        match find_result {
            Some(pos) => {
                slf.current_pos = pos + step;
                Ok(Some(pos))
            }
            None => Ok(None),
        }
    }
}

/// Public Python-facing methods.
#[pymethods]
impl Bits {
    #[new]
    #[pyo3(signature = (s = None))]
    pub fn py_new(s: Option<String>) -> PyResult<Self> {
        match s {
            None => Ok(BitCollection::from_zeros(0)),
            Some(s) => str_to_bits_rust(s),
        }
        // TODO: We previously had an interesting TypeError message if s wasn't a string
        // We should reinstate this:
        //  if not isinstance(s, str):
        //      err = f"Expected a str for Bits constructor, but received a {type(s)}. "
        //      if isinstance(s, MutableBits):
        //          err += "You can use the 'to_bits()' method on the `MutableBits` instance instead."
        //      elif isinstance(s, (bytes, bytearray, memoryview)):
        //          err += "You can use 'Bits.from_bytes()' instead."
        //      elif isinstance(s, int):
        //          err += "Perhaps you want to use 'Bits.from_zeros()', 'Bits.from_ones()' or 'Bits.from_random()'?"
        //      elif isinstance(s, (tuple, list)):
        //          err += "Perhaps you want to use 'Bits.from_joined()' instead?"
        //      else:
        //          err += "To create from other types use from_bytes(), from_bools(), from_joined(), "\
        //                 "from_ones(), from_zeros(), from_dtype() or from_random()."
        //      raise TypeError(err)
    }

    /// Return string representations for printing.
    pub fn __str__(&self) -> String {
        if self.len() == 0 {
            return "".to_string();
        }
        if self.len() % 4 == 0 {
            return format!("0x{}", self.to_hex());
        }
        return format!("0b{}", self.to_bin());
    }

    /// Return representation that could be used to recreate the instance.
    pub fn __repr__(&self, py: Python) -> String {
        let class_name = py.get_type::<Self>().name().unwrap();
        format!("{}('{}')", class_name, self.__str__())
    }

    fn __iter__(slf: PyRef<'_, Self>) -> PyResult<Py<BitsBoolIterator>> {
        let py = slf.py();
        let length = slf.len();
        Py::new(
            py,
            BitsBoolIterator {
                bits: slf.into(),
                index: 0,
                length,
            },
        )
    }

    /// Return True if two Bits have the same binary representation.
    ///
    /// The right hand side will be promoted to a Bits if needed and possible.
    ///
    /// >>> Bits('0b1110') == '0xe'
    /// True
    ///
    pub fn __eq__(&self, other: PyObject, py: Python) -> bool {
        // TODO: This risks creating copies of Bits or MutableBits when they're not needed.
        bits_from_any(other, py).map_or(false, |b| self.data == b.data)
    }

    #[staticmethod]
    pub fn _from_u64(value: u64, length: usize) -> Self {
        BitCollection::from_u64(value, length)
    }

    #[staticmethod]
    pub fn _from_i64(value: i64, length: usize) -> Self {
        BitCollection::from_i64(value, length)
    }

    pub fn _to_u64(&self, start: usize, length: usize) -> u64 {
        self.data[start..start + length].load_be::<u64>()
    }

    pub fn _to_i64(&self, start: usize, length: usize) -> i64 {
        self.data[start..start + length].load_be::<i64>()
    }

    #[pyo3(signature = (needle_obj, byte_aligned=false))]
    pub fn _findall(
        slf: PyRef<'_, Self>,
        needle_obj: Py<Bits>,
        byte_aligned: bool,
    ) -> PyResult<Py<PyBitsFindAllIterator>> {
        let py = slf.py();
        let haystack_obj: Py<Bits> = slf.into(); // Get a Py<Bits> for the haystack (self)

        let step = if byte_aligned { 8 } else { 1 };

        let iter_obj = PyBitsFindAllIterator {
            haystack: haystack_obj,
            needle: needle_obj,
            current_pos: 0,
            byte_aligned,
            step,
        };
        Py::new(py, iter_obj)
    }

    pub fn __len__(&self) -> usize {
        self.len()
    }

    /// Create a new instance with all bits set to zero.
    ///
    /// :param n: The number of bits.
    /// :return: A Bits object with all bits set to zero.
    ///
    /// .. code-block:: python
    ///
    ///     a = Bits.from_zeros(500)  # 500 zero bits
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
    ///     >>> Bits.from_ones(5)
    ///     Bits('0b11111')
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

    /// Create a new instance from a bytes object.
    ///
    /// :param b: The bytes object to convert to a :class:`Bits`.
    ///
    /// .. code-block:: python
    ///
    /// a = Bits.from_bytes(b"some_bytes_maybe_from_a_file")
    ///
    #[classmethod]
    pub fn from_bytes(_cls: &Bound<'_, PyType>, data: Vec<u8>) -> Self {
        BitCollection::from_bytes(data)
    }

    #[staticmethod]
    pub fn _from_bytes_with_offset(data: Vec<u8>, offset: usize) -> Self {
        debug_assert!(offset < 8);
        let mut bv: helpers::BV = <Bits as BitCollection>::from_bytes(data).data;
        bv.drain(..offset);
        Bits::new(bv)
    }

    #[staticmethod]
    pub fn _from_bools(values: Vec<PyObject>, py: Python) -> PyResult<Self> {
        let mut bv = helpers::BV::with_capacity(values.len());

        for value in values {
            let b: bool = value.extract(py)?;
            bv.push(b);
        }
        Ok(Bits::new(bv))
    }

    #[staticmethod]
    pub fn _from_bin(binary_string: &str) -> PyResult<Self> {
        match BitCollection::from_bin(binary_string) {
            Ok(result) => Ok(result),
            Err(e) => Err(PyValueError::new_err(e)),
        }
    }

    #[staticmethod]
    pub fn _from_hex(hex: &str) -> PyResult<Self> {
        match BitCollection::from_hex(hex) {
            Ok(result) => Ok(result),
            Err(e) => Err(PyValueError::new_err(e)),
        }
    }

    #[staticmethod]
    pub fn _from_oct(oct: &str) -> PyResult<Self> {
        match BitCollection::from_oct(oct) {
            Ok(x) => Ok(x),
            Err(e) => Err(PyValueError::new_err(e)),
        }
    }

    #[staticmethod]
    pub fn _from_joined(bits_vec: Vec<PyRef<Self>>) -> Self {
        let total_len: usize = bits_vec.iter().map(|x| x.len()).sum();
        let mut bv = helpers::BV::with_capacity(total_len);
        for bits_ref in bits_vec.iter() {
            bv.extend_from_bitslice(&bits_ref.data);
        }
        Bits::new(bv)
    }

    /// Return bytes that can easily be converted to an int in Python
    pub fn _to_int_byte_data(&self, signed: bool) -> Vec<u8> {
        if self.len() == 0 {
            return Vec::new();
        }

        // TODO: Is this next line right?
        let needed_bits = (self.len() + 7) & !7;
        let mut bv = helpers::BV::with_capacity(needed_bits);

        let sign_bit = signed && self.data[0];
        let padding = needed_bits - self.len();

        for _ in 0..padding {
            bv.push(sign_bit);
        }
        bv.extend_from_bitslice(&self.data);

        bv.into_vec()
    }

    /// Return the Bits as bytes, padding with zero bits if needed.
    ///
    /// Up to seven zero bits will be added at the end to byte align.
    ///
    /// :return: The Bits as bytes.
    ///
    pub fn to_bytes(&self) -> Vec<u8> {
        if self.data.is_empty() {
            return Vec::new();
        }

        let mut bv = BitVec::<u8, Msb0>::with_capacity(self.len());
        bv.extend_from_bitslice(&self.data);
        let new_len = (bv.len() + 7) & !7;
        bv.resize(new_len, false);
        bv.into_vec()
    }

    pub fn _slice_to_bytes(&self, start: usize, length: usize) -> PyResult<Vec<u8>> {
        if length % 8 != 0 {
            return Err(PyValueError::new_err(format!(
                "Cannot interpret as bytes - length of {} is not a multiple of 8 bits.",
                length
            )));
        }
        if length == 0 {
            return Ok(Vec::new());
        }
        let mut bv = BitVec::<u8, Msb0>::with_capacity(length);
        bv.extend_from_bitslice(&self.data[start..start + length]);
        Ok(bv.into_vec())
    }

    pub fn _slice_to_bin(&self, start: usize, length: usize) -> String {
        format!("{:b}", self.slice(start, length))
    }

    pub fn _slice_to_oct(&self, start: usize, length: usize) -> PyResult<String> {
        if length % 3 != 0 {
            return Err(PyValueError::new_err(format!(
                "Cannot interpret as octal - length of {} is not a multiple of 3 bits.",
                length
            )));
        }
        Ok(format!("{:o}", self.slice(start, length)))
    }

    pub fn _slice_to_hex(&self, start: usize, length: usize) -> PyResult<String> {
        if length % 4 != 0 {
            return Err(PyValueError::new_err(format!(
                "Cannot interpret as hex - length of {} is not a multiple of 4 bits.",
                length
            )));
        }
        Ok(format!("{:x}", self.slice(start, length)))
    }

    pub fn _and(&self, other: &Bits) -> PyResult<Self> {
        if self.len() != other.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }
        let result = self.data.clone() & &other.data;
        Ok(Bits::new(result))
    }

    pub fn _or(&self, other: &Bits) -> PyResult<Self> {
        if self.len() != other.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }
        let result = self.data.clone() | &other.data;
        Ok(Bits::new(result))
    }

    pub fn _xor(&self, other: &Bits) -> PyResult<Self> {
        if self.len() != other.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }
        let result = self.data.clone() ^ &other.data;
        Ok(Bits::new(result))
    }

    pub fn _find(&self, b: &Bits, start: usize, bytealigned: bool) -> Option<usize> {
        if bytealigned {
            helpers::find_bitvec_bytealigned(self, b, start)
        } else {
            helpers::find_bitvec(self, b, start)
        }
    }

    pub fn _rfind(&self, b: &Bits, start: usize, bytealigned: bool) -> Option<usize> {
        if b.len() + start > self.len() {
            return None;
        }
        let step = if bytealigned { 8 } else { 1 };
        let mut pos = self.len() - b.len();
        if bytealigned {
            pos = pos / 8 * 8;
        }
        while pos >= start {
            if &self.data[pos..pos + b.len()] == &b.data {
                return Some(pos);
            }
            if pos < step {
                break;
            }
            pos -= step;
        }
        None
    }

    /// Return count of total number of either zero or one bits.
    ///
    ///     :param value: If `bool(value)` is True, bits set to 1 are counted; otherwise, bits set to 0 are counted.
    ///     :return: The count of bits set to 1 or 0.
    ///
    ///     .. code-block:: pycon
    ///
    ///         >>> Bits('0xef').count(1)
    ///         7
    ///
    pub fn count(&self, value: PyObject, py: Python) -> PyResult<usize> {
        let value = value.is_truthy(py)?;
        // Note that using hamming::weight is about twice as fast as:
        // self.data.count_ones()
        // which is the way that bitvec suggests.
        let bytes: &[u8] = bytemuck::cast_slice(self.data.as_raw_slice());
        let count = hamming::weight(bytes) as usize;
        if value {
            Ok(count)
        } else {
            Ok(self.len() - count)
        }
    }

    /// Return a slice of the current Bits.
    pub fn _getslice(&self, start_bit: usize, end_bit: usize) -> PyResult<Self> {
        if start_bit >= end_bit {
            return Ok(BitCollection::from_zeros(0));
        }
        assert!(start_bit < end_bit);
        if end_bit > self.len() {
            return Err(PyValueError::new_err("end bit goes past the end"));
        }
        Ok(self.slice(start_bit, end_bit - start_bit))
    }

    pub fn _get_slice_unchecked(&self, start_bit: usize, length: usize) -> Self {
        self.slice(start_bit, length)
    }

    pub fn _getslice_with_step(&self, start_bit: i64, end_bit: i64, step: i64) -> PyResult<Self> {
        if step == 0 {
            return Err(PyValueError::new_err("Step cannot be zero."));
        }
        // Note that a start_bit or end_bit of -1 means to stop at the beginning when using a negative step.
        // Otherwise they should both be positive indices.
        debug_assert!(start_bit >= -1);
        debug_assert!(end_bit >= -1);
        debug_assert!(step != 0);
        if start_bit < -1 || end_bit < -1 {
            return Err(PyValueError::new_err(
                "Indices less than -1 are not valid values.",
            ));
        }
        if step > 0 {
            if start_bit >= end_bit {
                return Ok(BitCollection::from_zeros(0));
            }
            if end_bit as usize > self.len() {
                return Err(PyValueError::new_err("end bit goes past the end"));
            }
            Ok(Bits::new(
                self.data[start_bit as usize..end_bit as usize]
                    .iter()
                    .step_by(step as usize)
                    .collect(),
            ))
        } else {
            if start_bit <= end_bit || start_bit == -1 {
                return Ok(BitCollection::from_zeros(0));
            }
            if start_bit as usize > self.len() {
                return Err(PyValueError::new_err("start bit goes past the end"));
            }
            // For negative step, the end_bit is inclusive, but the start_bit is exclusive.
            debug_assert!(step < 0);
            let adjusted_end_bit = (end_bit + 1) as usize;
            Ok(Bits::new(
                self.data[adjusted_end_bit..=start_bit as usize]
                    .iter()
                    .rev()
                    .step_by(-step as usize)
                    .collect(),
            ))
        }
    }

    /// Return True if all bits are equal to 1, otherwise return False.
    ///
    /// :return: ``True`` if all bits are 1, otherwise ``False``.
    ///
    /// .. code-block:: pycon
    ///
    ///     >>> Bits('0b1111').all()
    ///     True
    ///     >>> Bits('0b1011').all()
    ///     False
    ///
    pub fn all(&self) -> bool {
        self.data.all()
    }

    /// Return True if any bits are equal to 1, otherwise return False.
    ///
    /// :return: ``True`` if any bits are 1, otherwise ``False``.
    ///
    /// .. code-block:: pycon
    ///
    ///     >>> Bits('0b0000').any()
    ///     False
    ///     >>> Bits('0b1000').any()
    ///     True
    ///
    pub fn any(&self) -> bool {
        self.data.any()
    }

    /// Create and return a mutable copy of the Bits as a MutableBits instance.
    pub fn to_mutable_bits(&self) -> MutableBits {
        MutableBits {
            inner: Bits::new(self.data.clone()),
        }
    }

    pub fn _clone_as_immutable(&self) -> Self {
        // TODO: The clone shouldn't have to copy the data. Use Rc internally?
        self.clone()
    }

    /// Returns the bool value at a given bit index.
    pub fn _getindex(&self, bit_index: i64) -> PyResult<bool> {
        let index = helpers::validate_index(bit_index, self.len())?;
        Ok(self.data[index])
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

    pub(crate) fn _validate_shift(&self, n: i64) -> PyResult<usize> {
        if self.len() == 0 {
            return Err(PyValueError::new_err("Cannot shift an empty Bits."));
        }
        if n < 0 {
            return Err(PyValueError::new_err("Cannot shift by a negative amount."));
        }
        Ok(n as usize)
    }

    /// Return new Bits shifted by n to the left.
    ///
    /// n -- the number of bits to shift. Must be >= 0.
    ///
    pub fn __lshift__(&self, n: i64) -> PyResult<Self> {
        let shift = self._validate_shift(n)?;
        if shift == 0 {
            return Ok(self._clone_as_immutable());
        }
        let len = self.len();
        if shift >= len {
            return Ok(BitCollection::from_zeros(len));
        }
        let mut result_data = helpers::BV::with_capacity(len);
        result_data.extend_from_bitslice(&self.data[shift..]);
        result_data.resize(len, false);
        Ok(Self::new(result_data))
    }

    /// Return new Bits shifted by n to the right.
    ///
    /// n -- the number of bits to shift. Must be >= 0.
    ///
    pub fn __rshift__(&self, n: i64) -> PyResult<Self> {
        let shift = self._validate_shift(n)?;
        if shift == 0 {
            return Ok(self._clone_as_immutable());
        }
        let len = self.len();
        if shift >= len {
            return Ok(BitCollection::from_zeros(len));
        }
        let mut result_data = helpers::BV::repeat(false, shift);
        result_data.extend_from_bitslice(&self.data[..len - shift]);
        Ok(Self::new(result_data))
    }

    /// Return the instance with every bit inverted.
    ///
    /// Raises ValueError if the Bits is empty.
    ///
    pub fn __invert__(&self) -> PyResult<Self> {
        if self.data.is_empty() {
            return Err(PyValueError::new_err("Cannot invert empty Bits."));
        }
        Ok(Bits {
            data: self.data.clone().not(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn from_bytes() {
        let data: Vec<u8> = vec![10, 20, 30];
        let bits = <Bits as BitCollection>::from_bytes(data);
        assert_eq!(*bits.to_bytes(), vec![10, 20, 30]);
        assert_eq!(bits.len(), 24);
    }

    #[test]
    fn from_hex() {
        let bits = Bits::from_hex("0x0a_14  _1e").unwrap();
        assert_eq!(*bits.to_bytes(), vec![10, 20, 30]);
        assert_eq!(bits.len(), 24);
        let bits = Bits::from_hex("").unwrap();
        assert_eq!(bits.len(), 0);
        let bits = Bits::from_hex("hello");
        assert!(bits.is_err());
        let bits = Bits::from_hex("1").unwrap();
        assert_eq!(*bits.to_bytes(), vec![16]);
        assert_eq!(bits.len(), 4);
    }

    #[test]
    fn from_bin() {
        let bits = Bits::from_bin("00001010").unwrap();
        assert_eq!(*bits.to_bytes(), vec![10]);
        assert_eq!(bits.len(), 8);
        let bits = Bits::from_bin("").unwrap();
        assert_eq!(bits.len(), 0);
        let bits = Bits::from_bin("hello");
        assert!(bits.is_err());
        let bits = Bits::from_bin("1").unwrap();
        assert_eq!(*bits.to_bytes(), vec![128]);
        assert_eq!(bits.len(), 1);
    }

    #[test]
    fn from_zeros() {
        let bits = <Bits as BitCollection>::from_zeros(8);
        assert_eq!(*bits.to_bytes(), vec![0]);
        assert_eq!(bits.len(), 8);
        assert_eq!(bits.to_hex(), "00");
        let bits = <Bits as BitCollection>::from_zeros(9);
        assert_eq!(*bits.to_bytes(), vec![0, 0]);
        assert_eq!(bits.len(), 9);
        let bits = <Bits as BitCollection>::from_zeros(0);
        assert_eq!(bits.len(), 0);
    }

    #[test]
    fn from_ones() {
        let bits = <Bits as BitCollection>::from_ones(8);
        assert_eq!(*bits.to_bytes(), vec![255]);
        assert_eq!(bits.len(), 8);
        assert_eq!(bits.to_hex(), "ff");
        let bits = <Bits as BitCollection>::from_ones(9);
        assert_eq!(bits.to_bin(), "111111111");
        assert_eq!((*bits.to_bytes())[0], 0xff);
        assert_eq!((*bits.to_bytes())[1] & 0x80, 0x80);
        assert_eq!(bits.len(), 9);
        let bits = <Bits as BitCollection>::from_ones(0);
        assert_eq!(bits.len(), 0);
    }

    #[test]
    fn get_index() {
        let bits = Bits::from_bin("001100").unwrap();
        assert_eq!(bits._getindex(0).unwrap(), false);
        assert_eq!(bits._getindex(1).unwrap(), false);
        assert_eq!(bits._getindex(2).unwrap(), true);
        assert_eq!(bits._getindex(3).unwrap(), true);
        assert_eq!(bits._getindex(4).unwrap(), false);
        assert_eq!(bits._getindex(5).unwrap(), false);
        assert!(bits._getindex(6).is_err());
        assert!(bits._getindex(60).is_err());
    }

    #[test]
    fn hex_edge_cases() {
        let b1 = Bits::from_hex("0123456789abcdef").unwrap();
        let b2 = b1._getslice(12, b1.len()).unwrap();
        assert_eq!(b2.to_hex(), "3456789abcdef");
        assert_eq!(b2.len(), 52);
        let t = Bits::from_hex("123").unwrap();
        assert_eq!(t.to_hex(), "123");
    }

    #[test]
    fn test_find() {
        let b1 = <Bits as BitCollection>::from_zeros(10);
        let b2 = <Bits as BitCollection>::from_ones(2);
        assert_eq!(b1._find(&b2, 0, false), None);
        let b3 = Bits::from_bin("00001110").unwrap();
        let b4 = Bits::from_bin("01").unwrap();
        assert_eq!(b3._find(&b4, 0, false), Some(3));
        assert_eq!(b3._find(&b4, 2, false), Some(3));

        let s = Bits::from_bin("0000110110000").unwrap();
        let f = Bits::from_bin("11011").unwrap();
        let p = s._find(&f, 0, false).unwrap();
        assert_eq!(p, 4);

        let s = Bits::from_hex("010203040102ff").unwrap();
        // assert s.find("0x05", bytealigned=True) is None
        let f = Bits::from_hex("02").unwrap();
        let p = s._find(&f, 0, true);
        assert_eq!(p, Some(8));
    }

    #[test]
    fn test_rfind() {
        let b1 = Bits::from_hex("00780f0").unwrap();
        let b2 = Bits::from_bin("1111").unwrap();
        assert_eq!(b1._rfind(&b2, 0, false), Some(20));
        assert_eq!(b1._find(&b2, 0, false), Some(9));
    }

    #[test]
    fn test_and() {
        let a1 = Bits::from_hex("f0f").unwrap();
        let a2 = Bits::from_hex("123").unwrap();
        let a3 = a1._and(&a2).unwrap();
        let b = Bits::from_hex("103").unwrap();
        assert_eq!(a3, b);
        let a4 = a1.slice(4, 8)._and(&a2.slice(4, 8)).unwrap();
        assert_eq!(a4, Bits::from_hex("03").unwrap());
    }

    #[test]
    fn test_set_mutable_slice() {
        let mut a = MutableBits::_from_hex_checked("0011223344").unwrap();
        let b = Bits::from_hex("ff").unwrap();
        a._set_slice(8, 16, &b).unwrap();
        assert_eq!(a.to_hex(), "00ff223344");
    }

    #[test]
    fn test_get_mutable_slice() {
        let a = Bits::from_hex("01ffff").unwrap();
        assert_eq!(a.len(), 24);
        let b = a._getslice(1, a.len()).unwrap();
        assert_eq!(b.len(), 23);
        let c = b.to_mutable_bits();
        assert_eq!(c.len(), 23);
    }

    #[test]
    fn test_getslice() {
        let a = Bits::from_bin("00010001").unwrap();
        assert_eq!(a._getslice(0, 4).unwrap().to_bin(), "0001");
        assert_eq!(a._getslice(4, 8).unwrap().to_bin(), "0001");
    }

    #[test]
    fn test_all_set() {
        let b = Bits::from_bin("111").unwrap();
        assert!(b.all());
        let c = Bits::from_oct("7777777777").unwrap();
        assert!(c.all());
    }

    #[test]
    fn test_set_index() {
        let mut b = <MutableBits as BitCollection>::from_zeros(10);
        b._set_index(true, 0).unwrap();
        assert_eq!(b.to_bin(), "1000000000");
        b._set_index(true, -1).unwrap();
        assert_eq!(b.to_bin(), "1000000001");
        b._set_index(false, 0).unwrap();
        assert_eq!(b.to_bin(), "0000000001");
    }

    #[test]
    fn test_to_bytes_from_slice() {
        let a = <Bits as BitCollection>::from_ones(16);
        assert_eq!(a.to_bytes(), vec![255, 255]);
        let b = a._getslice(7, a.len()).unwrap();
        assert_eq!(b.to_bin(), "111111111");
        assert_eq!(b.to_bytes(), vec![255, 128]);
    }

    #[test]
    fn test_to_int_byte_data() {
        let a = Bits::from_bin("111111111").unwrap();
        let b = a._to_int_byte_data(false);
        assert_eq!(b, vec![1, 255]);
        let c = a._to_int_byte_data(true);
        assert_eq!(c, vec![255, 255]);
        let s = a.slice(5, 3);
        assert_eq!(s._to_int_byte_data(false), vec![7]);
        assert_eq!(s._to_int_byte_data(true), vec![255]);
    }

    #[test]
    fn test_from_oct() {
        let bits = Bits::from_oct("123").unwrap();
        assert_eq!(bits.to_bin(), "001010011");
        let bits = Bits::from_oct("7").unwrap();
        assert_eq!(bits.to_bin(), "111");
    }

    #[test]
    fn test_from_oct_checked() {
        let bits = Bits::from_oct("123").unwrap();
        assert_eq!(bits.to_bin(), "001010011");
        let bits = Bits::from_oct("0o123").unwrap();
        assert_eq!(bits.to_bin(), "001010011");
        let bits = Bits::from_oct("7").unwrap();
        assert_eq!(bits.to_bin(), "111");
        let bits = Bits::from_oct("8");
        assert!(bits.is_err());
    }

    #[test]
    fn test_to_oct() {
        let bits = Bits::from_bin("001010011").unwrap();
        assert_eq!(bits._slice_to_oct(0, bits.len()).unwrap(), "123");
        let bits = Bits::from_bin("111").unwrap();
        assert_eq!(bits._slice_to_oct(0, 3).unwrap(), "7");
        let bits = Bits::from_bin("000").unwrap();
        assert_eq!(bits._slice_to_oct(0, 3).unwrap(), "0");
    }

    #[test]
    fn test_set_from_slice() {
        let mut bits = MutableBits::_from_bin_checked("00000000").unwrap();
        bits._set_from_slice(true, 1, 7, 2).unwrap();
        assert_eq!(bits.to_bin(), "01010100");
        bits._set_from_slice(true, -7, -1, 2).unwrap();
        assert_eq!(bits.to_bin(), "01010100");
        bits._set_from_slice(false, 1, 7, 2).unwrap();
        assert_eq!(bits.to_bin(), "00000000");
    }

    #[test]
    fn test_any_set() {
        let bits = Bits::from_bin("0000").unwrap();
        assert!(!bits.any());
        let bits = Bits::from_bin("1000").unwrap();
        assert!(bits.any());
    }

    #[test]
    fn test_xor() {
        let a = Bits::from_bin("1100").unwrap();
        let b = Bits::from_bin("1010").unwrap();
        let result = a._xor(&b).unwrap();
        assert_eq!(result.to_bin(), "0110");
    }

    #[test]
    fn test_or() {
        let a = Bits::from_bin("1100").unwrap();
        let b = Bits::from_bin("1010").unwrap();
        let result = a._or(&b).unwrap();
        assert_eq!(result.to_bin(), "1110");
    }

    #[test]
    fn test_and2() {
        let a = Bits::from_bin("1100").unwrap();
        let b = Bits::from_bin("1010").unwrap();
        let result = a._and(&b).unwrap();
        assert_eq!(result.to_bin(), "1000");
    }

    #[test]
    fn test_from_bytes_with_offset() {
        let bits = Bits::_from_bytes_with_offset(vec![0b11110000], 4);
        assert_eq!(bits.to_bin(), "0000");
        let bits = Bits::_from_bytes_with_offset(vec![0b11110000, 0b00001111], 4);
        assert_eq!(bits.to_bin(), "000000001111");
    }

    #[test]
    fn test_len() {
        let bits = Bits::from_bin("1100").unwrap();
        assert_eq!(bits.__len__(), 4);
        let bits = Bits::from_bin("101010").unwrap();
        assert_eq!(bits.__len__(), 6);
    }

    #[test]
    fn test_eq() {
        let a = Bits::from_bin("1100").unwrap();
        let b = Bits::from_bin("1100").unwrap();
        assert!(a == b);
        let c = Bits::from_bin("1010").unwrap();
        assert!(a != c);
    }

    #[test]
    fn test_getslice_withstep() {
        let bits = Bits::from_bin("11001100").unwrap();
        let slice = bits._getslice_with_step(0, 8, 2).unwrap();
        assert_eq!(slice.to_bin(), "1010");
        let slice = bits._getslice_with_step(7, -1, -2).unwrap();
        assert_eq!(slice.to_bin(), "0101");
        let slice = bits._getslice_with_step(0, 8, 1).unwrap();
        assert_eq!(slice.to_bin(), "11001100");
        let slice = bits._getslice_with_step(7, -1, -1).unwrap();
        assert_eq!(slice.to_bin(), "00110011");
        let slice = bits._getslice_with_step(0, 8, 8).unwrap();
        assert_eq!(slice.to_bin(), "1");
        let slice = bits._getslice_with_step(0, 8, -8).unwrap();
        assert_eq!(slice.to_bin(), "");
        let slice = bits._getslice_with_step(0, 8, 3).unwrap();
        assert_eq!(slice.to_bin(), "100");
    }

    #[test]
    fn mutable_from_immutable() {
        let immutable = Bits::from_bin("1010").unwrap();
        let mutable = MutableBits::new(immutable.data);
        assert_eq!(mutable.to_bin(), "1010");
    }

    #[test]
    fn freeze_preserves_data() {
        let mutable = MutableBits::_from_bin_checked("1100").unwrap();
        let immutable = mutable.to_bits();
        assert_eq!(immutable.to_bin(), "1100");
    }

    #[test]
    fn modify_then_freeze() {
        let mut mutable = MutableBits::_from_bin_checked("0000").unwrap();
        mutable._set_index(true, 1).unwrap();
        mutable._set_index(true, 2).unwrap();
        let immutable = mutable.to_bits();
        assert_eq!(immutable.to_bin(), "0110");
    }

    #[test]
    fn mutable_constructors() {
        let m1 = <MutableBits as BitCollection>::from_zeros(4);
        assert_eq!(m1.to_bin(), "0000");

        let m2 = <MutableBits as BitCollection>::from_ones(4);
        assert_eq!(m2.to_bin(), "1111");

        let m3 = MutableBits::_from_bin_checked("1010").unwrap();
        assert_eq!(m3.to_bin(), "1010");

        let m4 = MutableBits::_from_hex_checked("a").unwrap();
        assert_eq!(m4.to_bin(), "1010");

        let m5 = MutableBits::_from_oct_checked("12").unwrap();
        assert_eq!(m5.to_bin(), "001010");
    }

    #[test]
    fn mutable_equality() {
        let m1 = MutableBits::_from_bin_checked("1100").unwrap();
        let m2 = MutableBits::_from_bin_checked("1100").unwrap();
        let m3 = MutableBits::_from_bin_checked("0011").unwrap();

        assert!(m1 == m2);
        assert!(m1 != m3);
    }

    #[test]
    fn mutable_getslice() {
        let m = MutableBits::_from_bin_checked("11001010").unwrap();

        let slice1 = m._getslice(2, 6).unwrap();
        assert_eq!(slice1.to_bin(), "0010");

        let slice2 = m._getslice_with_step(0, 8, 2).unwrap();
        assert_eq!(slice2.to_bin(), "1011");
    }

    #[test]
    fn mutable_find_operations() {
        let haystack = MutableBits::_from_bin_checked("00110011").unwrap();
        let needle = Bits::from_bin("11").unwrap();

        assert_eq!(haystack._find(&needle, 0, false), Some(2));
        assert_eq!(haystack._find(&needle, 3, false), Some(6));
        assert_eq!(haystack._rfind(&needle, 0, false), Some(6));
    }

    #[test]
    fn mutable_set_operations() {
        let mut m = <MutableBits as BitCollection>::from_zeros(8);

        m._set_index(true, 0).unwrap();
        m._set_index(true, 7).unwrap();
        assert_eq!(m.to_bin(), "10000001");

        m._set_from_slice(true, 2, 6, 1).unwrap();
        assert_eq!(m.to_bin(), "10111101");

        m._set_from_sequence(false, vec![0, 3, 7]).unwrap();
        assert_eq!(m.to_bin(), "00101100");
    }

    #[test]
    fn mutable_immutable_interaction() {
        let pattern1 = MutableBits::_from_bin_checked("1100").unwrap();
        let pattern2 = Bits::from_bin("0011").unwrap();

        let mut m = MutableBits::new(pattern1.inner.data);

        m._set_slice(0, 2, &pattern2).unwrap();
        assert_eq!(m.to_bin(), "001100");
    }

    #[test]
    fn empty_data_operations() {
        let empty_mutable = <MutableBits as BitCollection>::from_zeros(0);
        let empty_immutable = <Bits as BitCollection>::from_zeros(0);

        assert_eq!(empty_mutable.len(), 0);
        assert!(!empty_mutable.any());

        assert_eq!(empty_mutable.to_bits().len(), 0);

        let mut another_empty = <MutableBits as BitCollection>::from_zeros(0);
    }

    #[test]
    fn mutable_edge_index_operations() {
        let mut m = MutableBits::_from_bin_checked("1010").unwrap();

        m._set_index(false, 0).unwrap();
        m._set_index(false, 3).unwrap();
        assert_eq!(m.to_bin(), "0010");

        m._set_index(true, -1).unwrap();
        m._set_index(true, -4).unwrap();
        assert_eq!(m.to_bin(), "1011");

        assert!(m._set_index(true, 4).is_err());
        assert!(m._set_index(true, -5).is_err());
    }

    #[test]
    fn set_mutable_slice_with_bits() {
        let mut m = MutableBits::_from_bin_checked("00000000").unwrap();
        let pattern = Bits::from_bin("1111").unwrap();

        m._set_slice(2, 6, &pattern).unwrap();
        assert_eq!(m.to_bin(), "00111100");

        m._set_slice(0, 2, &pattern).unwrap();
        assert_eq!(m.to_bin(), "1111111100");

        m._set_slice(6, 8, &pattern).unwrap();
        assert_eq!(m.to_bin(), "111111111100");
    }

    #[test]
    fn conversion_round_trip() {
        let original = Bits::from_bin("101010").unwrap();
        let mut mutable = MutableBits::new(original.data);
        mutable._set_index(false, 0).unwrap();
        mutable._set_index(true, 1).unwrap();
        let result = mutable._as_immutable();

        assert_eq!(result.to_bin(), "011010");
    }

    // This one causes a panic that stops the other tests.
    // #[test]
    // fn mutable_to_representations() {
    //     let m = MutableBitRust::from_bin_checked("11110000");
    //
    //     assert_eq!(m.to_bin(), "11110000");
    //     assert_eq!(m.to_hex().unwrap(), "f0");
    //     assert_eq!(m.to_oct().unwrap(), "360");
    //     assert_eq!(m.to_bytes(), vec![0xF0]);
    // }

    #[test]
    fn mutable_from_checked_constructors() {
        let bin = MutableBits::_from_bin_checked("1010").unwrap();
        assert_eq!(bin.to_bin(), "1010");

        let hex = MutableBits::_from_hex_checked("a").unwrap();
        assert_eq!(hex.to_bin(), "1010");

        let oct = MutableBits::_from_oct_checked("12").unwrap();
        assert_eq!(oct.to_bin(), "001010");

        assert!(MutableBits::_from_bin_checked("123").is_err());
        assert!(MutableBits::_from_hex_checked("xy").is_err());
        assert!(MutableBits::_from_oct_checked("89").is_err());
    }

    #[test]
    fn negative_indexing_in_mutable() {
        let m = MutableBits::_from_bin_checked("10101010").unwrap();

        assert_eq!(m._getindex(-3).unwrap(), false);
        assert_eq!(m._getindex(-8).unwrap(), true);
        assert!(m._getindex(-9).is_err());
    }

    #[test]
    fn mutable_getslice_edge_cases() {
        let m = MutableBits::_from_bin_checked("11001010").unwrap();

        let empty = m._getslice(4, 4).unwrap();
        assert_eq!(empty.to_bin(), "");

        let full = m._getslice(0, m.len()).unwrap();
        assert_eq!(full.to_bin(), "11001010");

        assert!(m._getslice(9, 10).is_err());
    }
}
