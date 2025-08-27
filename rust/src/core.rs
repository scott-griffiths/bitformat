use crate::bits::Bits;
use crate::helpers::{validate_index, BV};
use crate::mutable::MutableBits;
use bitvec::bits;
use bitvec::field::BitField;
use bitvec::order::Msb0;
use bitvec::prelude::Lsb0;
use bitvec::view::BitView;
use lru::LruCache;
use once_cell::sync::Lazy;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::fmt;
use std::num::NonZeroUsize;
use std::sync::Mutex;

// Trait used for commonality between the Bits and MutableBits structs.
pub(crate) trait BitCollection: Sized {
    fn len(&self) -> usize;
    fn is_empty(&self) -> bool;
    fn empty() -> Self;
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
const BITS_CACHE_SIZE: usize = 1024;
static BITS_CACHE: Lazy<Mutex<LruCache<String, BV>>> =
    Lazy::new(|| Mutex::new(LruCache::new(NonZeroUsize::new(BITS_CACHE_SIZE).unwrap())));

pub(crate) static DTYPE_PARSER: Lazy<Mutex<Option<Py<PyAny>>>> = Lazy::new(|| Mutex::new(None));

fn split_tokens(s: &String) -> Vec<String> {
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

pub(crate) fn str_to_bits(s: String) -> PyResult<Bits> {
    // Check cache first
    {
        let mut cache = BITS_CACHE.lock().unwrap();
        if let Some(cached_data) = cache.get(&s) {
            return Ok(Bits::new(cached_data.clone()));
        }
    }
    let tokens = split_tokens(&s);
    let mut bits_array = Vec::<Bits>::new();
    let mut total_bit_length = 0;

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
                    let new_bits = Bits::new(bits_ref.data.clone());
                    total_bit_length += new_bits.len();
                    bits_array.push(new_bits);
                    Ok(())
                })?; // Propagate any Python errors
            }
        }
    }
    if bits_array.is_empty() {
        return Ok(BitCollection::empty());
    }
    // Combine all bits
    let result = if bits_array.len() == 1 {
        bits_array.pop().unwrap()
    } else {
        let mut result = BV::with_capacity(total_bit_length);
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

impl BitCollection for Bits {
    fn len(&self) -> usize {
        self.data.len()
    }

    fn is_empty(&self) -> bool {
        self.data.is_empty()
    }

    fn empty() -> Self {
        Bits::new(BV::new())
    }

    fn from_zeros(length: usize) -> Self {
        Bits::new(BV::repeat(false, length))
    }

    fn from_ones(length: usize) -> Self {
        Bits::new(BV::repeat(true, length))
    }

    fn from_bytes(data: Vec<u8>) -> Self {
        let bits = data.view_bits::<Msb0>();
        let bv = BV::from_bitslice(bits);
        Bits::new(bv)
    }

    fn from_bin(binary_string: &str) -> Result<Self, String> {
        // Ignore any leading '0b'
        let s = binary_string.strip_prefix("0b").unwrap_or(binary_string);
        let mut b: BV = BV::with_capacity(s.len());
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
        let mut b: BV = BV::with_capacity(s.len() * 3);
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
        let mut bv = BV::repeat(false, length);
        bv.store_be(value);
        Bits::new(bv)
    }

    fn from_i64(value: i64, length: usize) -> Self {
        let mut bv = BV::repeat(false, length);
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
}

impl BitCollection for MutableBits {
    fn len(&self) -> usize {
        self.inner.len()
    }
    fn is_empty(&self) -> bool {
        self.inner.is_empty()
    }

    fn empty() -> Self {
        Self {
            inner: <Bits as BitCollection>::empty(),
        }
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
    fn get_bit(&self, i: usize) -> bool {
        self.inner.data[i]
    }
    fn to_bin(&self) -> String {
        self.inner.to_bin()
    }
    fn to_oct(&self) -> Result<String, String> {
        self.inner.to_oct()
    }
    fn to_hex(&self) -> Result<String, String> {
        self.inner.to_hex()
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

// ---- Bits private helper methods. Not part of the Python interface. ----

impl Bits {
    pub(crate) fn new(bv: BV) -> Self {
        Bits { data: bv }
    }

    /// Slice used internally without bounds checking.
    pub(crate) fn slice(&self, start_bit: usize, length: usize) -> Self {
        Bits::new(self.data[start_bit..start_bit + length].to_bitvec())
    }
}

pub(crate) fn validate_logical_op_lengths(a: usize, b: usize) -> PyResult<()> {
    if a != b {
        Err(PyValueError::new_err(format!("For logical operations the lengths of both objects must match. Received lengths of {a} and {b} bits.")))
    } else {
        Ok(())
    }
}

impl MutableBits {
    pub fn new(bv: BV) -> Self {
        Self {
            inner: Bits::new(bv),
        }
    }

    pub fn _set_from_sequence(&mut self, value: bool, indices: Vec<i64>) -> PyResult<()> {
        for idx in indices {
            let pos: usize = validate_index(idx, self.inner.len())?;
            self.inner.data.set(pos, value);
        }
        Ok(())
    }
}
