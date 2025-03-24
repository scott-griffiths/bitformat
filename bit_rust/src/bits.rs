use std::borrow::Cow;
use std::fmt;
use std::ops::Not;
use pyo3::{pyclass, pymethods, PyRef, PyRefMut, PyResult};
use pyo3::exceptions::{PyIndexError, PyValueError};
use bitvec::prelude::*;
use lazy_static::lazy_static;
use std::sync::Arc;
use pyo3::prelude::*;

lazy_static!(
    pub static ref ZERO_BIT: BitRust = BitRust::from_zeros(1);
);

lazy_static!(
    pub static ref ONE_BIT: BitRust = BitRust::from_ones(1);
);

type BV = BitVec<u8, Msb0>;
type BS = BitSlice<u8, Msb0>;

// An implementation of the KMP algorithm for bit slices.
fn compute_lps(pattern: &BS) -> Vec<usize> {
    let len = pattern.len();
    let mut lps = vec![0; len];
    let mut i = 1;
    let mut len_prev = 0;

    while i < len {
        match pattern[i] == pattern[len_prev] {
            true => {
                len_prev += 1;
                lps[i] = len_prev;
                i += 1;
            }
            false if len_prev != 0 => len_prev = lps[len_prev - 1],
            false => {
                lps[i] = 0;
                i += 1;
            }
        }
    }
    lps
}

pub fn find_bitvec(haystack: &BitRust, needle: &BitRust, start: usize) -> Option<usize> {
    // Early return if needle is empty or longer than haystack
    if needle.length == 0 {
        return Some(start);
    }
    if needle.length > haystack.length - start {
        return None;
    }

    let lps = compute_lps(&needle.owned_data[needle.offset..needle.offset + needle.length]);
    let mut i = start; // index for haystack
    let mut j = 0;     // index for needle

    while i < haystack.length {
        if needle.owned_data[needle.offset + j] == haystack.owned_data[haystack.offset + i] {
            i += 1;
            j += 1;
        }
        if j == needle.length {
            let match_position = i - j;
            return Some(match_position);
        }
        if i < haystack.length && needle.owned_data[needle.offset + j] != haystack.owned_data[haystack.offset + i] {
            if j != 0 {
                j = lps[j - 1];
            } else {
                i += 1;
            }
        }
    }
    None
}

// The same as find_bitvec but only returns matches that are a multiple of 8.
pub fn find_bitvec_bytealigned(haystack: &BitRust, needle: &BitRust, start: usize) -> Option<usize> {
    // Early return if needle is empty or longer than haystack
    if needle.length == 0 {
        return Some(start);
    }
    if needle.length > haystack.length - start {
        return None;
    }

    let lps = compute_lps(&needle.owned_data[needle.offset..needle.offset + needle.length]);
    let mut i = start; // index for haystack
    let mut j = 0;     // index for needle

    while i < haystack.length {
        if needle.owned_data[needle.offset + j] == haystack.owned_data[haystack.offset + i] {
            i += 1;
            j += 1;
        }
        if j == needle.length {
            let match_position = i - j;
            if match_position % 8 == 0 {
                return Some(match_position);
            } else {
                j = lps[j - 1];
            }
        }
        if i < haystack.length && needle.owned_data[needle.offset + j] != haystack.owned_data[haystack.offset + i] {
            if j != 0 {
                j = lps[j - 1];
            } else {
                i += 1;
            }
        }
    }
    None
}

fn convert_bitrust_to_bytes(bits: &BitRust) -> Vec<u8> {
    // If we're byte-aligned and have a whole number of bytes, we can copy directly
    if bits.offset % 8 == 0 && bits.length % 8 == 0 {
        return bits.owned_data.as_raw_slice()[bits.offset/8..(bits.offset + bits.length)/8].to_vec();
    }

    // Otherwise, we need to create a new byte array with the correct bits
    let num_bytes = (bits.length + 7) / 8;  // Round up to nearest byte
    let mut result = Vec::with_capacity(num_bytes);

    // Process 8 bits at a time
    let mut current_byte: u8 = 0;
    let mut bits_in_byte: usize = 0;

    for i in 0..bits.length {
        current_byte = (current_byte << 1) | (bits.owned_data[bits.offset + i] as u8);
        bits_in_byte += 1;

        if bits_in_byte == 8 {
            result.push(current_byte);
            current_byte = 0;
            bits_in_byte = 0;
        }
    }

    // Handle any remaining bits in the last partial byte
    if bits_in_byte > 0 {
        current_byte <<= 8 - bits_in_byte;  // Left align the remaining bits
        result.push(current_byte);
    }

    result
}

/// BitRust is a struct that holds an arbitrary amount of binary data.
/// Currently it's just wrapping a BitVec from the bitvec crate.
#[pyclass]
pub struct BitRust {
    owned_data: Arc<BV>,
    offset: usize,
    length: usize,
}


impl fmt::Debug for BitRust {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.len() > 100 {
            return f.debug_struct("Bits")
                .field("hex", &self.slice(0, 100).to_hex().unwrap())
                .field("length", &self.len())
                .finish();
        }
        if self.len() % 4 == 0 {
            return f.debug_struct("Bits")
                .field("hex", &self.to_hex().unwrap())
                .field("length", &self.len())
                .finish();
        }
        f.debug_struct("Bits")
            .field("bin", &self.to_bin())
            .field("length", &self.len())
            .finish()
    }
}

impl PartialEq for BitRust {

    fn eq(&self, other: &Self) -> bool {
        // First check if they have the same length
        if self.length != other.length {
            return false;
        }

        // If they're views into the same data and have the same offset and length, they're equal
        if Arc::ptr_eq(&self.owned_data, &other.owned_data) &&
            self.offset == other.offset &&
            self.length == other.length {
            return true;
        }

        // Otherwise compare bit by bit
        // TODO: Must be a faster way!
        for i in 0..self.length {
            if self.owned_data[self.offset + i] != other.owned_data[other.offset + i] {
                return false;
            }
        }
        true
    }
}

// Things not part of the Python interface.
impl BitRust {

    fn new(bv: BV) -> Self {
        let length = bv.len();
        BitRust {
            owned_data: Arc::new(bv),
            offset: 0,
            length,
        }
    }

    // Helper method to get a clone of the underlying BV when needed
    fn get_bv_clone(&self) -> BV {
        (*self.owned_data).clone()
    }

    fn bits(&self) -> Cow<BS> {
        Cow::Borrowed(&self.owned_data[self.offset..self.offset + self.length])
    }

    fn len(&self) -> usize {
        self.length
    }

    fn join_internal(bits_vec: &[&BitRust]) -> Self {
        match bits_vec.len() {
            0 => BitRust::from_zeros(0),
            1 => {
                // For a single BitRust, create a view into it
                let bits = bits_vec[0];
                BitRust {
                    owned_data: Arc::clone(&bits.owned_data),
                    offset: bits.offset,
                    length: bits.length,
                }
            }
            _ => {
                // Calculate total length first
                let total_len: usize = bits_vec.iter().map(|b| b.length).sum();

                // Create new BitVec with exact capacity needed
                let mut bv = BV::with_capacity(total_len);

                // Extend with each view's bits
                for bits in bits_vec {
                    bv.extend(&bits.owned_data[bits.offset..bits.offset + bits.length]);
                }

                // Create new BitRust with the combined data
                BitRust {
                    owned_data: Arc::new(bv),
                    offset: 0,
                    length: total_len,
                }
            }
        }
    }


    /// Slice used internally without bounds checking.
    fn slice(&self, start_bit: usize, end_bit: usize) -> Self {
        debug_assert!(start_bit <= end_bit);
        debug_assert!(end_bit <= self.length);
        BitRust {
            owned_data: Arc::clone(&self.owned_data),
            offset: self.offset + start_bit,
            length: end_bit - start_bit,
        }
    }

    fn bitwise_op<F>(&self, other: &BitRust, op: F) -> PyResult<BitRust>
    where
        F: Fn(bool, bool) -> bool,
    {
        // Check lengths match
        if self.length != other.length {
            return Err(PyValueError::new_err("Lengths do not match."));
        }

        // Create new BitVec with exact capacity needed
        let mut bv = BV::with_capacity(self.length);

        // Apply operation bit by bit, using offsets to access correct bits
        for i in 0..self.length {
            let self_bit = self.owned_data[self.offset + i];
            let other_bit = other.owned_data[other.offset + i];
            bv.push(op(self_bit, other_bit));
        }

        // Return new BitRust with no offset
        Ok(BitRust {
            owned_data: Arc::new(bv),
            offset: 0,
            length: self.length,
        })
    }

    // This works as a Rust version. Not sure how to make a proper Python interface.
    fn find_all_rust<'a>(&'a self, b: &'a BitRust, bytealigned: bool) -> impl Iterator<Item = usize> + 'a {
        // Use the find fn to find all instances of b in self and return as an iterator
        let mut start: usize = 0;
        std::iter::from_fn(move || {
            let found = self.find(b, start, bytealigned);
            match found {
                Some(x) => {
                    start = if bytealigned { x + 8 } else { x + 1 };
                    Some(x)
                }
                None => None,
            }
        })
    }
}

#[pyclass]
pub struct BitRustIterator {
    positions: Vec<usize>,
    index: usize,
}

#[pymethods]
impl BitRustIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<'_, Self>) -> Option<usize> {
        if slf.index < slf.positions.len() {
            let pos = slf.positions[slf.index];
            slf.index += 1;
            Some(pos)
        } else {
            None
        }
    }
}

#[pyclass]
struct BitRustBoolIterator {
    bits: Py<BitRust>,
    index: usize,
    length: usize,
}

#[pymethods]
impl BitRustBoolIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(&mut self, py: Python<'_>) -> PyResult<Option<bool>> {
        if self.index < self.length {
            let bits = self.bits.borrow(py);
            let result = bits.getindex(self.index as i64);
            self.index += 1;
            result.map(Some)
        } else {
            Ok(None)
        }
    }
}


#[pymethods]
impl BitRust {

    fn __iter__(slf: PyRef<'_, Self>) -> PyResult<Py<BitRustBoolIterator>> {
        let py = slf.py();
        let length = slf.len();
        Py::new(py, BitRustBoolIterator {
            bits: slf.into(),
            index: 0,
            length,
        })
    }

    #[pyo3(signature = (bs, byte_aligned=false))]
    pub fn findall(&self, bs: &BitRust, byte_aligned: bool) -> PyResult<BitRustIterator> {
        // TODO: Cheating here by making the whole list first, then making an iterator from it.
        Ok(BitRustIterator {
            positions: self.find_all_rust(bs, byte_aligned).collect(),
            index: 0,
        })
    }

    pub fn __len__(&self) -> usize {
        self.len()
    }

    pub fn __eq__(&self, rhs: &BitRust) -> bool {
        self == rhs
    }

    #[staticmethod]
    pub fn from_zeros(length: usize) -> Self {
        BitRust::new(BV::repeat(false, length))
    }

    #[staticmethod]
    pub fn from_ones(length: usize) -> Self {
        BitRust::new(BV::repeat(true, length))
    }

    #[staticmethod]
    pub fn from_bytes(data: Vec<u8>) -> Self {
        let bits = data.as_slice().view_bits::<Msb0>();
        let mut bv = BV::new();
        bv.extend_from_bitslice(bits);
        BitRust::new(bv)
    }

    #[staticmethod]
    pub fn from_bytes_with_offset(data: Vec<u8>, offset: usize) -> Self {
        assert!(offset < 8);
        let mut bv = (*BitRust::from_bytes(data).owned_data).clone();
        bv.drain(..offset);
        BitRust::new(bv)
    }

    #[staticmethod]
    pub fn from_bin_checked(binary_string: &str) -> PyResult<Self> {
        // Ignore any leading '0b'
        let skip = if binary_string.starts_with("0b") { 2 } else { 0 };
        let mut b: BV = BV::with_capacity(binary_string.len());
        for c in binary_string.chars().skip(skip) {
            match c {
                '0' => b.push(false),
                '1' => b.push(true),
                '_' => continue,
                c if c.is_whitespace() => continue,
                _ => return Err(PyValueError::new_err(format!("Cannot convert from bin '{binary_string}: Invalid character '{c}'."))),
            }
        }
        b.set_uninitialized(false);
        Ok(BitRust::new(b))
    }

    // An unchecked version of from_bin. Used when you're sure the input is valid.
    #[staticmethod]
    pub fn from_bin(binary_str: &str) -> Self {
        let len = binary_str.len();
        let mut b: BV = BV::with_capacity(len);

        // Process bytes at a time when possible
        let bytes = binary_str.as_bytes();
        let chunks = bytes.chunks_exact(8);
        let remainder = chunks.remainder();

        for chunk in chunks {
            let mut byte = 0u8;
            // Unroll the loop for better performance
            byte = (byte << 1) | ((chunk[0] == b'1') as u8);
            byte = (byte << 1) | ((chunk[1] == b'1') as u8);
            byte = (byte << 1) | ((chunk[2] == b'1') as u8);
            byte = (byte << 1) | ((chunk[3] == b'1') as u8);
            byte = (byte << 1) | ((chunk[4] == b'1') as u8);
            byte = (byte << 1) | ((chunk[5] == b'1') as u8);
            byte = (byte << 1) | ((chunk[6] == b'1') as u8);
            byte = (byte << 1) | ((chunk[7] == b'1') as u8);
            b.extend_from_raw_slice(&[byte]);
        }

        // Handle remaining bits
        for &bit in remainder {
            b.push(bit == b'1');
        }

        BitRust::new(b)
    }

    #[staticmethod]
    pub fn from_hex_checked(hex: &str) -> PyResult<Self> {
        // Ignore any leading '0x'
        let mut new_hex = if hex.starts_with("0x") {
            hex[2..].to_string()
        } else {
            hex.to_string()
        };
        // Remove any underscores or whitespace characters
        new_hex.retain(|c| c != '_' && !c.is_whitespace());
        let is_odd_length: bool = new_hex.len() % 2 != 0;
        if is_odd_length {
            new_hex.push('0');
        }
        let data = match hex::decode(new_hex) {
            Ok(d) => d,
            Err(e) => return Err(PyValueError::new_err(format!("Cannot convert from hex '{hex}': {}", e))),
        };
        let mut bv = (*BitRust::from_bytes(data).owned_data).clone();
        if is_odd_length {
            bv.drain(bv.len() - 4..bv.len());
        }
        Ok(BitRust::new(bv))
    }

    // An unchecked version of from_hex. Used internally when you're sure the input is valid.
    #[staticmethod]
    pub fn from_hex(hex: &str) -> Self {
        let mut new_hex = hex.to_string();
        let is_odd_length: bool = hex.len() % 2 != 0;
        if is_odd_length {
            new_hex.push('0');
        }
        let data = match hex::decode(new_hex) {
            Ok(d) => d,
            Err(_) => panic!("Invalid character"),
        };
        let mut bv = (*BitRust::from_bytes(data).owned_data).clone();
        if is_odd_length {
            bv.drain(bv.len() - 4..bv.len());
        }
        BitRust::new(bv)
    }

    #[staticmethod]
    pub fn from_oct_checked(oct: &str) -> PyResult<Self> {
        let mut bin_str = String::new();
        let skip = if oct.starts_with("0o") { 2 } else { 0 };
        for ch in oct.chars().skip(skip) {
            match ch {
                '0' => bin_str.push_str("000"),
                '1' => bin_str.push_str("001"),
                '2' => bin_str.push_str("010"),
                '3' => bin_str.push_str("011"),
                '4' => bin_str.push_str("100"),
                '5' => bin_str.push_str("101"),
                '6' => bin_str.push_str("110"),
                '7' => bin_str.push_str("111"),
                '_' => continue,
                c if c.is_whitespace() => continue,
                _ => return Err(PyValueError::new_err(format!("Cannot convert from oct '{oct}': Invalid character '{ch}'."))),
            }
        }
        Ok(BitRust::from_bin(&bin_str))
    }

    #[staticmethod]
    pub fn from_oct(oct: &str) -> Self {
        let mut bin_str = String::new();
        for ch in oct.chars() {
            // Convert each ch to an integer
            let digit = match ch.to_digit(8) {
                Some(d) => d,
                None => panic!("Invalid character"),
            };
            bin_str.push_str(&format!("{:03b}", digit)); // Format as 3-bit binary
        }
        BitRust::from_bin(&bin_str)
    }

    #[staticmethod]
    pub fn join(bits_vec: Vec<PyRef<BitRust>>) -> Self {
        let my_vec: Vec<&BitRust> = bits_vec.iter().map(|x| &**x).collect();
        BitRust::join_internal(&my_vec)
    }

    /// Convert to bytes, padding with zero bits if needed.
    pub fn to_bytes(&self) -> Vec<u8> {
        convert_bitrust_to_bytes(&self)
    }

    // Return bytes that can easily be converted to an int in Python
    pub fn to_int_byte_data(&self, signed: bool) -> Vec<u8> {
        // If empty, return empty vector
        if self.length == 0 {
            return Vec::new();
        }

        // Calculate padding needed to make the length a multiple of 8
        let padding_bits = (8 - self.length % 8) % 8;
        let total_bytes = (self.length + padding_bits) / 8;

        // Create result vector with exact capacity needed
        let mut result = Vec::with_capacity(total_bytes);

        // Handle sign extension for signed numbers
        let pad_with_ones = signed && self.owned_data[self.offset];

        // Process a byte at a time
        let mut current_byte: u8 = 0;
        let mut bits_in_byte: usize = 0;

        // Add padding bits first (if needed)
        for _ in 0..padding_bits {
            current_byte = (current_byte << 1) | (pad_with_ones as u8);
            bits_in_byte += 1;
        }

        // Process actual bits from the view
        for i in 0..self.length {
            if bits_in_byte == 8 {
                result.push(current_byte);
                current_byte = 0;
                bits_in_byte = 0;
            }
            current_byte = (current_byte << 1) | (self.owned_data[self.offset + i] as u8);
            bits_in_byte += 1;
        }

        // Push final byte if there are any remaining bits
        if bits_in_byte > 0 {
            result.push(current_byte);
        }

        debug_assert_eq!(result.len(), total_bytes);
        debug_assert_eq!(result.len(), (self.length + 7) / 8);

        result
    }

    pub fn to_hex(&self) -> PyResult<String> {
        if self.len() % 4 != 0 {
            return Err(PyValueError::new_err("Not a multiple of 4 bits long."));
        }
        let bytes = self.to_bytes();
        let hex_string = bytes.iter().map(|byte| format!("{:02x}", byte)).collect::<String>();
        if self.len() % 8 == 0 {
            return Ok(hex_string);
        }
        // If the length is not a multiple of 8, we need to trim the padding bits
        Ok(hex_string[0..hex_string.len() - 1].to_string())
    }

    pub fn to_bin(&self) -> String {
        let mut result = String::with_capacity(self.len());
        for bit in self.bits().iter() {
            result.push(if *bit { '1' } else { '0' });
        }
        result
    }

    pub fn to_oct(&self) -> PyResult<String> {
        if self.len() % 3 != 0 {
            return Err(PyValueError::new_err("Not a multiple of 3 bits long."));
        }
        let bin_str = self.to_bin();
        let mut oct_str: String = String::new();

        for chunk in bin_str.as_bytes().chunks(3) {
            let binary_chunk = std::str::from_utf8(chunk).unwrap();
            let value = u8::from_str_radix(binary_chunk, 2).unwrap();
            oct_str.push(std::char::from_digit(value as u32, 8).unwrap());
        }
        Ok(oct_str)
    }

    pub fn __and__(&self, other: &BitRust) -> PyResult<BitRust> {
        self.bitwise_op(other, |a, b| a.clone() & b.clone())
    }

    pub fn __or__(&self, other: &BitRust) -> PyResult<BitRust> {
        self.bitwise_op(other, |a, b| a.clone() | b.clone())
    }

    pub fn __xor__(&self, other: &BitRust) -> PyResult<BitRust> {
        self.bitwise_op(other, |a, b| a.clone() ^ b.clone())
    }

    pub fn find(&self, b: &BitRust, start: usize, bytealigned: bool) -> Option<usize> {
        if bytealigned {
            find_bitvec_bytealigned(&self, &b, start)
        } else {
            find_bitvec(&self, &b, start)
        }
    }
    
    pub fn rfind(&self, b: &BitRust, start: usize, bytealigned: bool) -> Option<usize> {
        if b.len() + start > self.len() {
            return None;
        }
        let step = if bytealigned { 8 } else { 1 };
        let mut pos = self.len() - b.len();
        if bytealigned {
            pos = pos / 8 * 8;
        }
        while pos >= start + step {
            if self.slice(pos, pos + b.len()) == *b {
                return Some(pos - start);
            }
            pos -= step;
        }
        None
    }

    pub fn count(&self) -> usize {
        if self.length == 0 {
            return 0;
        }

        let start_bit = self.offset;
        let end_bit = start_bit + self.length;

        // Find complete bytes we can process
        let first_complete_byte = (start_bit + 7) / 8;
        let last_complete_byte = end_bit / 8;

        let mut count = 0;

        // Handle any bits before the first complete byte
        if first_complete_byte * 8 > start_bit {
            for i in start_bit..(first_complete_byte * 8).min(end_bit) {
                if self.owned_data[i] {
                    count += 1;
                }
            }
        }

        // Use hamming::weight for complete bytes
        if last_complete_byte > first_complete_byte {
            let raw_slice = &self.owned_data.as_raw_slice()[first_complete_byte..last_complete_byte];
            count += hamming::weight(raw_slice) as usize;
        }

        // Handle any remaining bits
        if end_bit > last_complete_byte * 8 {
            for i in (last_complete_byte * 8)..end_bit {
                if self.owned_data[i] {
                    count += 1;
                }
            }
        }

        count
    }

    /// Returns a new BitRust with all bits reversed.
    pub fn reverse(&self) -> BitRust {
        if self.length <= 1 {
            return BitRust {
                owned_data: Arc::clone(&self.owned_data),
                offset: self.offset,
                length: self.length,
            };
        }

        // Create new BitVec with exact capacity needed
        let mut bv = BV::with_capacity(self.length);

        // Copy bits in reverse order
        for i in (0..self.length).rev() {
            bv.push(self.owned_data[self.offset + i]);
        }

        BitRust {
            owned_data: Arc::new(bv),
            offset: 0,
            length: self.length,
        }
    }

    /// Returns the bool value at a given bit index.
    pub fn getindex(&self, mut bit_index: i64) -> PyResult<bool> {
        let length = self.len();
        if bit_index >= length as i64 || bit_index < -(length as i64) {
            return Err(PyIndexError::new_err("Out of range."));
        }
        if bit_index < 0 {
            bit_index += length as i64;
        }
        debug_assert!(bit_index >= 0);
        let p = bit_index as usize;
        Ok(self.bits()[p])
    }

    /// Returns the length of the Bits object in bits.
    pub fn length(&self) -> usize {
        self.len()
    }

    /// Returns a reference to the raw data in the Bits object.
    /// Note that the offset and length values govern which part of this raw buffer is the actual
    /// binary data.
    // pub fn data(&self) -> &Vec<u8> {
    //     &self.bv.clone().into_vec()
    // }

    /// Return a slice of the current BitRust. Uses a view on the current byte data.
    #[pyo3(signature = (start_bit, end_bit=None))]
    pub fn getslice(&self, start_bit: usize, end_bit: Option<usize>) -> PyResult<Self> {
        let end_bit = end_bit.unwrap_or(self.len());
        if start_bit >= end_bit {
            return Ok(BitRust::from_zeros(0));
        }
        assert!(start_bit < end_bit);
        if end_bit > self.len() {
            return Err(PyValueError::new_err("end bit goes past the end"));
        }
        Ok(self.slice(start_bit, end_bit))
        // Ok(BitRust::new(self.bits()[start_bit..end_bit].to_owned()))
    }

    pub fn getslice_with_step(&self, start_bit: i64, end_bit: i64, step: i64) -> PyResult<Self> {
        if step == 0 {
            return Err(PyValueError::new_err("Step cannot be zero."));
        }
        // Note that a start_bit or end_bit of -1 means to stop at the beginning when using a negative step.
        // Otherwise they should both be positive indices.
        debug_assert!(start_bit >= -1);
        debug_assert!(end_bit >= -1);
        debug_assert!(step != 0);
        if start_bit < -1 || end_bit < -1 {
            return Err(PyValueError::new_err("Indices less than -1 are not valid values."));
        }
        if step > 0 {
            if start_bit >= end_bit {
                return Ok(BitRust::from_zeros(0));
            }
            if end_bit as usize > self.len() {
                return Err(PyValueError::new_err("end bit goes past the end"));
            }
            Ok(BitRust::new(self.bits()[start_bit as usize..end_bit as usize].iter().step_by(step as usize).collect()))  // TODO: Do I need .to_owned() here?
        } else {
            if start_bit <= end_bit || start_bit == -1 {
                return Ok(BitRust::from_zeros(0));
            }
            if start_bit as usize > self.len() {
                return Err(PyValueError::new_err("start bit goes past the end"));
            }
            // For negative step, the end_bit is inclusive, but the start_bit is exclusive.
            debug_assert!(step < 0);
            let adjusted_end_bit = (end_bit + 1) as usize;
            Ok(BitRust::new(self.bits()[adjusted_end_bit..=start_bit as usize].iter().rev().step_by(-step as usize).collect()))
        }
    }

    // Return new BitRust with single bit flipped. If pos is None then flip all the bits.
    #[pyo3(signature = (pos=None))]
    pub fn invert(&self, pos: Option<usize>) -> Self {
        let mut bv = self.get_bv_clone();
        match pos {
            None => {
                // Invert every bit
                bv = bv.not();
            }
            Some(pos) => {
                // Just invert the bit at pos
                let value = bv[pos]; // TODO handle error ?
                bv.set(pos, !value);
            }
        }
        BitRust::new(bv)
    }

    pub fn invert_bit_list(&self, pos_list: Vec<i64>) -> PyResult<Self> {
        let mut bv = self.get_bv_clone();
        for pos in pos_list {
            if pos < -(self.len() as i64) || pos >= self.len() as i64 {
                return Err(PyIndexError::new_err("Index out of range."));
            }
            let pos = if pos < 0 {
                (pos + self.len() as i64) as usize
            } else {
                pos as usize
            };
            let value = bv[pos];
            bv.set(pos, !value);
        }
        Ok(BitRust::new(bv))
    }

    pub fn invert_single_bit(&self, pos: i64) -> PyResult<Self> {
        if pos < -(self.len() as i64) || pos >= self.len() as i64 {
            return Err(PyIndexError::new_err("Index out of range."));
        }
        let pos = if pos < 0 {
            (pos + self.len() as i64) as usize
        } else {
            pos as usize
        };
        let mut bv = self.get_bv_clone();
        let value = bv[pos];
        bv.set(pos, !value);
        Ok(BitRust::new(bv))
    }

    pub fn invert_all(&self) -> Self {
        let bv = self.get_bv_clone().not();
        BitRust::new(bv)
    }


    /// Returns true if all of the bits are set to 1.
    pub fn all_set(&self) -> bool {
        self.count() == self.len()
    }

    /// Returns true if any of the bits are set to 1.
    pub fn any_set(&self) -> bool {
        self.count() != 0
    }

    // Return new BitRust with bit at index set to value.
    pub fn set_index(&self, value: bool, index: i64) -> PyResult<Self> {
        self.set_from_sequence(value, vec![index])
    }

    // Return new BitRust with bits at indices set to value.
    pub fn set_from_sequence(&self, value: bool, indices: Vec<i64>) -> PyResult<BitRust> {
        // Create new BitVec with content from current view
        let mut bv = BV::with_capacity(self.length);
        bv.extend(&self.owned_data[self.offset..self.offset + self.length]);

        // Update the specified indices
        for idx in indices {
            let pos = if idx < 0 {
                // Handle negative indices
                if -idx as usize > self.length {
                    return Err(PyIndexError::new_err("Index out of range"));
                }
                self.length - (-idx as usize)
            } else {
                // Handle positive indices
                if idx as usize >= self.length {
                    return Err(PyIndexError::new_err("Index out of range"));
                }
                idx as usize
            };
            bv.set(pos, value);
        }

        // Return new BitRust with modified data
        Ok(BitRust {
            owned_data: Arc::new(bv),
            offset: 0,
            length: self.length,
        })
    }

    pub fn set_from_slice(&self, value: bool, start: i64, stop: i64, step: i64) -> PyResult<Self> {
        let mut bv: BV = self.get_bv_clone();
        let len = self.len() as i64;
        let positive_start = if start < 0 { start + len } else { start };
        let positive_stop = if stop < 0 { stop + len } else { stop };

        if positive_start < 0 || positive_start >= len {
            return Err(PyIndexError::new_err("Start of slice out of bounds."));
        }
        if positive_stop < 0 || positive_stop > len {
            return Err(PyIndexError::new_err("End of slice out of bounds."));
        }
        if step == 0 {
            return Err(PyValueError::new_err("Step cannot be zero."));
        }

        let mut index = positive_start;
        if step > 0 {
            while index < positive_stop {
                bv.set(index as usize, value);
                index += step;
            }
        } else {
            while index > positive_stop {
                bv.set(index as usize, value);
                index += step;
            }
        }

        Ok(BitRust::new(bv))
    }

    /// Return a copy with a real copy of the data.
    pub fn get_mutable_copy(&self) -> Self {
        BitRust {
            owned_data: Arc::new((*self.owned_data).clone()),
            offset: self.offset,
            length: self.length
        }
    }

    pub fn set_mutable_slice(&mut self, start: usize, end: usize, value: &BitRust) -> PyResult<()> {
        let start_slice = self.getslice(0, Some(start))?;
        let end_slice = self.getslice(end, Some(self.len()))?;
        let joined = BitRust::join_internal(&vec![&start_slice, value, &end_slice]);
        *self = joined;
        Ok(())
    }

    pub fn data(&self) -> Vec<u8> {
        convert_bitrust_to_bytes(&self)
    }
}

#[test]
fn from_bytes() {
    let data: Vec<u8> = vec![10, 20, 30];
    let bits = BitRust::from_bytes(data);
    assert_eq!(*bits.data(), vec![10, 20, 30]);
    assert_eq!(bits.length(), 24);
}

#[test]
fn from_hex() {
    let bits = BitRust::from_hex_checked("0x0a_14  _1e").unwrap();
    assert_eq!(*bits.data(), vec![10, 20, 30]);
    assert_eq!(bits.length(), 24);
    let bits = BitRust::from_hex("");
    assert_eq!(bits.length(), 0);
    let bits = BitRust::from_hex_checked("hello");
    assert!(bits.is_err());
    let bits = BitRust::from_hex("1");
    assert_eq!(*bits.data(), vec![16]);
    assert_eq!(bits.length(), 4);
}

#[test]
fn from_bin() {
    let bits = BitRust::from_bin("00001010");
    assert_eq!(*bits.data(), vec![10]);
    assert_eq!(bits.length(), 8);
    let bits = BitRust::from_bin_checked("").unwrap();
    assert_eq!(bits.length(), 0);
    let bits = BitRust::from_bin_checked("hello");
    assert!(bits.is_err());
    let bits = BitRust::from_bin_checked("1").unwrap();
    assert_eq!(*bits.data(), vec![128]);
    assert_eq!(bits.length(), 1);
}

#[test]
fn from_zeros() {
    let bits = BitRust::from_zeros(8);
    assert_eq!(*bits.data(), vec![0]);
    assert_eq!(bits.length(), 8);
    assert_eq!(bits.to_hex().unwrap(), "00");
    let bits = BitRust::from_zeros(9);
    assert_eq!(*bits.data(), vec![0, 0]);
    assert_eq!(bits.length(), 9);
    let bits = BitRust::from_zeros(0);
    assert_eq!(bits.length(), 0);
}

#[test]
fn from_ones() {
    let bits = BitRust::from_ones(8);
    assert_eq!(*bits.data(), vec![255]);
    assert_eq!(bits.length(), 8);
    assert_eq!(bits.to_hex().unwrap(), "ff");
    let bits = BitRust::from_ones(9);
    assert_eq!(bits.to_bin(), "111111111");
    assert!(bits.to_hex().is_err());
    assert_eq!((*bits.data())[0], 0xff);
    assert_eq!((*bits.data())[1] & 0x80, 0x80);
    assert_eq!(bits.length(), 9);
    let bits = BitRust::from_ones(0);
    assert_eq!(bits.length(), 0);
}

#[test]
fn get_index() {
    let bits = BitRust::from_bin("001100");
    assert_eq!(bits.getindex(0).unwrap(), false);
    assert_eq!(bits.getindex(1).unwrap(), false);
    assert_eq!(bits.getindex(2).unwrap(), true);
    assert_eq!(bits.getindex(3).unwrap(), true);
    assert_eq!(bits.getindex(4).unwrap(), false);
    assert_eq!(bits.getindex(5).unwrap(), false);
    assert!(bits.getindex(6).is_err());
    assert!(bits.getindex(60).is_err());
}

#[test]
fn hex_edge_cases() {
    let b1 = BitRust::from_hex("0123456789abcdef");
    let b2 = b1.getslice(12, Some(b1.length())).unwrap();
    assert_eq!(b2.to_hex().unwrap(), "3456789abcdef");
    assert_eq!(b2.length(), 52);
    let t = BitRust::from_hex("123");
    assert_eq!(t.to_hex().unwrap(), "123");
}

#[test]
fn test_count() {
    let x = vec![1, 2, 3];
    let b = BitRust::from_bytes(x);
    assert_eq!(b.count(), 4);
}

#[test]
fn test_reverse() {
    let b = BitRust::from_bin("11110000");
    let bp = b.reverse();
    assert_eq!(bp.to_bin(), "00001111");
    let b = BitRust::from_bin("1");
    let bp = b.reverse();
    assert_eq!(bp.to_bin(), "1");
    let empty = BitRust::from_bin("");
    let empty_p = empty.reverse();
    assert_eq!(empty_p.to_bin(), "");
    let b = BitRust::from_bin("11001");
    let bp = b.reverse();
    assert_eq!(bp.to_bin(), "10011");
    let hex_str = "98798379287592836521000cbdbeff";
    let long = BitRust::from_hex(hex_str);
    let rev = long.reverse();
    assert_eq!(rev.reverse(), long);
}

#[test]
fn test_invert() {
    let b = BitRust::from_bin("0");
    assert_eq!(b.invert(None).to_bin(), "1");
    let b = BitRust::from_bin("01110");
    assert_eq!(b.invert(None).to_bin(), "10001");
    let hex_str = "abcdef8716258765162548716258176253172635712654714";
    let long = BitRust::from_hex(hex_str);
    let temp = long.invert(None);
    assert_eq!(long.length(), temp.length());
    assert_eq!(temp.invert(None), long);
}

#[test]
fn test_find() {
    let b1 = BitRust::from_zeros(10);
    let b2 = BitRust::from_ones(2);
    assert_eq!(b1.find(&b2, 0,false), None);
    let b3 = BitRust::from_bin("00001110");
    let b4 = BitRust::from_bin("01");
    assert_eq!(b3.find(&b4, 0, false), Some(3));
    assert_eq!(b3.find(&b4, 2,false), Some(3));

    let s = BitRust::from_bin("0000110110000");
    let f = BitRust::from_bin("11011");
    let p = s.find(&f, 0, false).unwrap();
    assert_eq!(p, 4);

    let s = BitRust::from_hex("010203040102ff");
    // assert s.find("0x05", bytealigned=True) is None
    let f = BitRust::from_hex("02");
    let p = s.find(&f, 0, true);
    assert_eq!(p, Some(8));

}

#[test]
fn test_rfind() {
    let b1 = BitRust::from_hex("00780f0");
    let b2 = BitRust::from_bin("1111");
    assert_eq!(b1.rfind(&b2, 0, false), Some(20));
    assert_eq!(b1.find(&b2, 0, false), Some(9));

}

#[test]
fn test_and() {
    let a1 = BitRust::from_hex("f0f");
    let a2 = BitRust::from_hex("123");
    let a3 = a1.__and__(&a2).unwrap();
    let b = BitRust::from_hex("103");
    assert_eq!(a3, b);
    let a4 = a1.slice(4, 12).__and__(&a2.slice(4, 12)).unwrap();
    assert_eq!(a4, BitRust::from_hex("03"));
}

#[test]
fn test_findall() {
    let b = BitRust::from_hex("00ff0ff0");
    let a = BitRust::from_hex("ff");
    let q: Vec<usize> = b.find_all_rust(&a, false).collect();
    assert_eq!(q, vec![8, 20]);

    let a = BitRust::from_hex("fffff4512345ff1234ff12ff");
    let b = BitRust::from_hex("ff");
    let q: Vec<usize> = a.find_all_rust(&b, true).collect();
    assert_eq!(q, vec![0, 8, 6*8, 9*8, 11*8]);
}


#[test]
fn test_set_mutable_slice() {
    let mut a = BitRust::from_hex("0011223344");
    let b = BitRust::from_hex("ff");
    a.set_mutable_slice(8, 16, &b).unwrap();
    assert_eq!(a.to_hex().unwrap(), "00ff223344");
}

#[test]
fn test_get_mutable_slice() {
    let a = BitRust::from_hex("01ffff");
    assert_eq!(a.len(), 24);
    let b = a.getslice(1, None).unwrap();
    assert_eq!(b.len(), 23);
    let c = b.get_mutable_copy();
    assert_eq!(c.len(), 23);
}


#[test]
fn test_getslice() {
    let a = BitRust::from_bin("00010001");
    assert_eq!(a.getslice(0, Some(4)).unwrap().to_bin(), "0001");
    assert_eq!(a.getslice(4, Some(8)).unwrap().to_bin(), "0001");
}

#[test]
fn test_all_set() {
    let b = BitRust::from_bin("111");
    assert!(b.all_set());
    let c = BitRust::from_oct("7777777777");
    assert!(c.all_set());
}

#[test]
fn test_set_index() {
    let b = BitRust::from_zeros(10);
    let b = b.set_index(true, 0).unwrap();
    assert_eq!(b.to_bin(), "1000000000");
    let b = b.set_index(true, -1).unwrap();
    assert_eq!(b.to_bin(), "1000000001");
    let b = b.set_index(false, 0).unwrap();
    assert_eq!(b.to_bin(), "0000000001");
}

#[test]
fn test_to_bytes_from_slice() {
    let a = BitRust::from_ones(16);
    assert_eq!(a.to_bytes(), vec![255, 255]);
    let b = a.getslice(7, None).unwrap();
    assert_eq!(b.to_bin(), "111111111");
    assert_eq!(b.to_bytes(), vec![255, 128]);
}

#[test]
fn test_to_int_byte_data() {
    let a = BitRust::from_bin("111111111");
    let b = a.to_int_byte_data(false);
    assert_eq!(b, vec![1, 255]);
    let c = a.to_int_byte_data(true);
    assert_eq!(c, vec![255, 255]);
    let s = a.slice(5, 8);
    assert_eq!(s.to_int_byte_data(false), vec![7]);
    assert_eq!(s.to_int_byte_data(true), vec![255]);
}

#[test]
fn test_from_oct() {
    let bits = BitRust::from_oct("123");
    assert_eq!(bits.to_bin(), "001010011");
    let bits = BitRust::from_oct("7");
    assert_eq!(bits.to_bin(), "111");
}

#[test]
fn test_from_oct_checked() {
    let bits = BitRust::from_oct_checked("123").unwrap();
    assert_eq!(bits.to_bin(), "001010011");
    let bits = BitRust::from_oct_checked("0o123").unwrap();
    assert_eq!(bits.to_bin(), "001010011");
    let bits = BitRust::from_oct_checked("7").unwrap();
    assert_eq!(bits.to_bin(), "111");
    let bits = BitRust::from_oct_checked("8");
    assert!(bits.is_err());
}

#[test]
fn test_to_oct() {
    let bits = BitRust::from_bin("001010011");
    assert_eq!(bits.to_oct().unwrap(), "123");
    let bits = BitRust::from_bin("111");
    assert_eq!(bits.to_oct().unwrap(), "7");
    let bits = BitRust::from_bin("000");
    assert_eq!(bits.to_oct().unwrap(), "0");
}

#[test]
fn test_invert_bit_list() {
    let bits = BitRust::from_bin("0000");
    let inverted = bits.invert_bit_list(vec![0, 2]).unwrap();
    assert_eq!(inverted.to_bin(), "1010");
    let inverted = bits.invert_bit_list(vec![-1, -3]).unwrap();
    assert_eq!(inverted.to_bin(), "0101");
    let inverted = bits.invert_bit_list(vec![0, 1, 2, 3]).unwrap();
    assert_eq!(inverted.to_bin(), "1111");
}

#[test]
fn test_set_from_slice() {
    let bits = BitRust::from_bin("00000000");
    let set_bits = bits.set_from_slice(true, 1, 7, 2).unwrap();
    assert_eq!(set_bits.to_bin(), "01010100");
    let set_bits = bits.set_from_slice(true, -7, -1, 2).unwrap();
    assert_eq!(set_bits.to_bin(), "01010100");
    let set_bits = bits.set_from_slice(false, 1, 7, 2).unwrap();
    assert_eq!(set_bits.to_bin(), "00000000");
}


#[test]
fn test_invert_all() {
    let bits = BitRust::from_bin("0000");
    let inverted = bits.invert_all();
    assert_eq!(inverted.to_bin(), "1111");
    let bits = BitRust::from_bin("1010");
    let inverted = bits.invert_all();
    assert_eq!(inverted.to_bin(), "0101");
}

#[test]
fn test_any_set() {
    let bits = BitRust::from_bin("0000");
    assert!(!bits.any_set());
    let bits = BitRust::from_bin("1000");
    assert!(bits.any_set());
}

#[test]
fn test_invert_single_bit() {
    let bits = BitRust::from_bin("0000");
    let inverted = bits.invert_single_bit(1).unwrap();
    assert_eq!(inverted.to_bin(), "0100");
    let inverted = bits.invert_single_bit(-1).unwrap();
    assert_eq!(inverted.to_bin(), "0001");
}

#[test]
fn test_xor() {
    let a = BitRust::from_bin("1100");
    let b = BitRust::from_bin("1010");
    let result = a.__xor__(&b).unwrap();
    assert_eq!(result.to_bin(), "0110");
}

#[test]
fn test_or() {
    let a = BitRust::from_bin("1100");
    let b = BitRust::from_bin("1010");
    let result = a.__or__(&b).unwrap();
    assert_eq!(result.to_bin(), "1110");
}

#[test]
fn test_and2() {
    let a = BitRust::from_bin("1100");
    let b = BitRust::from_bin("1010");
    let result = a.__and__(&b).unwrap();
    assert_eq!(result.to_bin(), "1000");
}

#[test]
fn test_from_bytes_with_offset() {
    let bits = BitRust::from_bytes_with_offset(vec![0b11110000], 4);
    assert_eq!(bits.to_bin(), "0000");
    let bits = BitRust::from_bytes_with_offset(vec![0b11110000, 0b00001111], 4);
    assert_eq!(bits.to_bin(), "000000001111");
}

#[test]
fn test_len() {
    let bits = BitRust::from_bin("1100");
    assert_eq!(bits.__len__(), 4);
    let bits = BitRust::from_bin("101010");
    assert_eq!(bits.__len__(), 6);
}

#[test]
fn test_eq() {
    let a = BitRust::from_bin("1100");
    let b = BitRust::from_bin("1100");
    assert!(a.__eq__(&b));
    let c = BitRust::from_bin("1010");
    assert!(!a.__eq__(&c));
}

#[test]
fn test_getslice_withstep() {
    let bits = BitRust::from_bin("11001100");
    let slice = bits.getslice_with_step(0, 8, 2).unwrap();
    assert_eq!(slice.to_bin(), "1010");
    let slice = bits.getslice_with_step(7, -1, -2).unwrap();
    assert_eq!(slice.to_bin(), "0101");
    let slice = bits.getslice_with_step(0, 8, 1).unwrap();
    assert_eq!(slice.to_bin(), "11001100");
    let slice = bits.getslice_with_step(7, -1, -1).unwrap();
    assert_eq!(slice.to_bin(), "00110011");
    let slice = bits.getslice_with_step(0, 8, 8).unwrap();
    assert_eq!(slice.to_bin(), "1");
    let slice = bits.getslice_with_step(0, 8, -8).unwrap();
    assert_eq!(slice.to_bin(), "");
    let slice = bits.getslice_with_step(0, 8, 3).unwrap();
    assert_eq!(slice.to_bin(), "100");
}
