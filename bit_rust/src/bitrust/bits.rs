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
use std::num::NonZeroUsize;
use std::ops::Not;

use lru::LruCache;
use once_cell::sync::Lazy;
use std::sync::Mutex;

// Trait used for commonality between the Bits and MutableBits structs.
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

    fn get_bit(&self, i: usize) -> bool;
    fn to_bin(&self) -> String;
    fn to_oct(&self) -> Result<String, String>;
    fn to_hex(&self) -> Result<String, String>;
}

// ---- Rust-only helper methods ----

// Define a static LRU cache.
const BITS_CACHE_SIZE: usize = 256;
static BITS_CACHE: Lazy<Mutex<LruCache<String, helpers::BV>>> =
    Lazy::new(|| Mutex::new(LruCache::new(NonZeroUsize::new(BITS_CACHE_SIZE).unwrap())));

static DTYPE_PARSER: Lazy<Mutex<Option<PyObject>>> = Lazy::new(|| Mutex::new(None));

fn split_tokens(s: String) -> Vec<String> {
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

fn string_literal_to_bits(s: &str) -> PyResult<Bits> {
    if s.starts_with("0x") {
        return Bits::_from_hex(s);
    } else if s.starts_with("0o") {
        return Bits::_from_oct(s);
    } else if s.starts_with("0b") {
        return Bits::_from_bin(s);
    }

    Err(PyValueError::new_err(format!(
        "Can't parse token '{s}'. Did you mean to prefix with '0x', '0b' or '0o'?"
    )))
}

// ---- Exported Python helper methods ----

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
        match string_literal_to_bits(&token) {
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
        "Cannot convert object of type {type_name} to a Bits object."
    )))
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

impl BitCollection for Bits {
    fn len(&self) -> usize {
        self.data.len()
    }

    fn get_bit(&self, i: usize) -> bool {
        self.data[i]
    }

    fn to_bin(&self) -> String {
        let mut result = String::with_capacity(self.len());
        for i in 0..self.len() {
            result.push(if self.get_bit(i) { '1' } else { '0' });
        }
        result
    }

    fn to_oct(&self) -> Result<String, String> {
        if self.len() % 3 != 0 {
            return Err(format!(
                "Cannot interpret as octal - length of {} is not a multiple of 3 bits.",
                self.len()
            ));
        }
        let mut result = String::with_capacity(self.len() / 3);
        for chunk in self.data.chunks(3) {
            let tribble = chunk.load_be::<u8>();
            let oct_char = std::char::from_digit(tribble as u32, 8).unwrap();
            result.push(oct_char);
        }
        Ok(result)
    }

    fn to_hex(&self) -> Result<String, String> {
        if self.len() % 4 != 0 {
            return Err(format!(
                "Cannot interpret as hex - length of {} is not a multiple of 4 bits.",
                self.len()
            ));
        }
        let mut result = String::with_capacity(self.len() / 4);
        for chunk in self.data.chunks(4) {
            let nibble = chunk.load_be::<u8>();
            let hex_char = std::char::from_digit(nibble as u32, 16).unwrap();
            result.push(hex_char);
        }
        Ok(result)
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
        debug_assert!(self.len() == other.len());
        let result = self.data.clone() | &other.data;
        Bits::new(result)
    }
    fn logical_and(&self, other: &Bits) -> Self {
        debug_assert!(self.len() == other.len());
        let result = self.data.clone() & &other.data;
        Bits::new(result)
    }
    fn logical_xor(&self, other: &Bits) -> Self {
        debug_assert!(self.len() == other.len());
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

// ---- Bits private helper methods. Not part of the Python interface. ----

impl Bits {
    pub(crate) fn new(bv: helpers::BV) -> Self {
        Bits { data: bv }
    }

    /// Slice used internally without bounds checking.
    pub(crate) fn slice(&self, start_bit: usize, length: usize) -> Self {
        Bits::new(BitVec::from_bitslice(
            &self.data[start_bit..start_bit + length],
        ))
    }
}

pub(crate) fn _validate_logical_op_lengths(a: usize, b: usize) -> PyResult<()> {
    if a != b {
        return Err(PyValueError::new_err(format!("For logical operations the lengths of both objects must match. Received lengths of {a} and {b} bits.")));
    }
    Ok(())
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
        match self.to_hex() {
            Ok(hex) => format!("0x{}", hex),
            Err(_) => format!("0b{}", self.to_bin()),
        }
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
        BitCollection::from_bin(binary_string).map_err(PyValueError::new_err)
    }

    #[staticmethod]
    pub fn _from_hex(hex: &str) -> PyResult<Self> {
        BitCollection::from_hex(hex).map_err(PyValueError::new_err)
    }

    #[staticmethod]
    pub fn _from_oct(oct: &str) -> PyResult<Self> {
        BitCollection::from_oct(oct).map_err(PyValueError::new_err)
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
                "Cannot interpret as bytes - length of {} is not a multiple of 8 bits. Use the to_bytes() method if you want to add zero padding bits.",
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
        self.slice(start, length).to_bin()
    }

    pub fn _slice_to_oct(&self, start: usize, length: usize) -> PyResult<String> {
        self.slice(start, length)
            .to_oct()
            .map_err(PyValueError::new_err)
    }

    pub fn _slice_to_hex(&self, start: usize, length: usize) -> PyResult<String> {
        self.slice(start, length)
            .to_hex()
            .map_err(PyValueError::new_err)
    }

    pub fn _and(&self, other: &Bits) -> PyResult<Self> {
        _validate_logical_op_lengths(self.len(), other.len())?;
        let result = self.data.clone() & &other.data;
        Ok(Bits::new(result))
    }

    pub fn _or(&self, other: &Bits) -> PyResult<Self> {
        _validate_logical_op_lengths(self.len(), other.len())?;
        let result = self.data.clone() | &other.data;
        Ok(Bits::new(result))
    }

    pub fn _xor(&self, other: &Bits) -> PyResult<Self> {
        _validate_logical_op_lengths(self.len(), other.len())?;
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
            return Err(PyValueError::new_err(
                "End bit of the slice goes past the end of the Bits.",
            ));
        }
        Ok(self.slice(start_bit, end_bit - start_bit))
    }

    pub fn _get_slice_unchecked(&self, start_bit: usize, length: usize) -> Self {
        self.slice(start_bit, length)
    }

    pub fn _getslice_with_step(&self, start_bit: i64, end_bit: i64, step: i64) -> PyResult<Self> {
        if step == 0 {
            return Err(PyValueError::new_err("Slice step cannot be zero."));
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
                return Err(PyValueError::new_err(
                    "Slice end goes past the end of the Bits.",
                ));
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
                return Err(PyValueError::new_err(
                    "Slice start bit is past the end of the Bits.",
                ));
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
