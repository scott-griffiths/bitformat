use std::fmt;
use std::sync::Arc;
use pyo3::{pyclass, pymethods, PyRef, PyResult};
use pyo3::exceptions::{PyIndexError, PyValueError};
use hamming;
use bitvec::prelude::*;

// An implementation of the KMP algorithm for bit slices.
fn compute_lps(pattern: &BitSlice<u8, Msb0>) -> Vec<usize> {
    let mut lps = vec![0; pattern.len()];
    let mut length = 0;
    let mut i = 1;

    while i < pattern.len() {
        if pattern[i] == pattern[length] {
            length += 1;
            lps[i] = length;
            i += 1;
        } else {
            if length != 0 {
                length = lps[length - 1];
            } else {
                lps[i] = 0;
                i += 1;
            }
        }
    }
    lps
}

pub fn find_bitvec(s: &BitVec<u8, Msb0>, pattern: &BitVec<u8, Msb0>, start: usize) -> Option<usize> {
    let lps = compute_lps(pattern);
    let mut i = start; // index for text
    let mut j = 0; // index for pattern

    while i < s.len() {
        if pattern[j] == s[i] {
            i += 1;
            j += 1;
        }
        if j == pattern.len() {
            let match_position = i - j;
            return Some(match_position);
        }
        if i < s.len() && pattern[j] != s[i] {
            if j != 0 {
                j = lps[j - 1];
            } else {
                i += 1;
            }
        }
    }
    None
}


/// BitRust is a struct that holds an arbitrary amount of binary data. The data is stored
/// in a Vec<u8> but does not need to be a multiple of 8 bits. A bit offset and a bit length
/// are stored.
/// 
#[pyclass]
pub struct BitRust {
    data: Arc<Vec<u8>>,
    offset: usize,
    length: usize,
}


impl fmt::Debug for BitRust {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.length > 100 {
            return f.debug_struct("Bits")
                .field("hex", &self.slice(0, 100).to_hex().unwrap())
                .field("length", &self.length)
                .finish();
        }
        if self.length % 4 == 0 {
            return f.debug_struct("Bits")
                .field("hex", &self.to_hex().unwrap())
                .field("length", &self.length)
                .finish();
        }
        f.debug_struct("Bits")
            .field("bin", &self.to_bin())
            .field("length", &self.length)
            .finish()
    }
}

impl Clone for BitRust {
    fn clone(&self) -> Self {
        BitRust {
            data: Arc::clone(&self.data),
            offset: self.offset,
            length: self.length,
        }
    }
}

impl PartialEq for BitRust {
    fn eq(&self, other: &Self) -> bool {
        if self.length != other.length {
            return false;
        }
        if self.offset % 8 == 0 && other.offset % 8 == 0 {
            if self.length % 8 == 0 {
                return self.data[self.start_byte()..self.end_byte()] == other.data[other.start_byte()..other.end_byte()];
            }
            if self.data[self.start_byte()..self.end_byte() - 1] != other.data[other.start_byte()..other.end_byte() - 1] {
                return false;
            }
        }
        self.to_bin() == other.to_bin()
    }
}

// Things not part of the Python interface.
impl BitRust {
    fn bitwise_op<F>(&self, other: &BitRust, op: F) -> Result<Self, ()>
    where F: Fn(u8, u8) -> u8 {
        if self.length != other.length {
            return Err(());
        }
        let a = BitRust::from_bin(&self.to_bin()).unwrap();
        let b = BitRust::from_bin(&other.to_bin()).unwrap();

        let mut data: Vec<u8> = Vec::new();
        for i in 0..a.data.len() {
            data.push(op(a.data[i], b.data[i]));
        }
        Ok(BitRust {
            data: Arc::new(data),
            length: self.length,
            offset: 0,
        })
    }

    fn join_internal(bits_vec: &Vec<&BitRust>) -> Self {
        if bits_vec.is_empty() {
            return BitRust::from_zeros(0);
        }
        if bits_vec.len() == 1 {
            return bits_vec[0].clone();
        }
        let mut data = bits_vec[0].data[bits_vec[0].start_byte()..bits_vec[0].end_byte()].to_vec();
        let new_offset = bits_vec[0].offset % 8;
        let mut new_length = bits_vec[0].length;
        // Go though the vec of Bits and set the offset of each to the number of bits in the final byte of the previous one
        for bits in &bits_vec[1..] {
            if bits.length == 0 {
                continue;
            }
            let extra_bits = (new_length + new_offset) % 8;
            let offset_bits = bits.copy_with_new_offset(extra_bits);
            if extra_bits == 0 {
                data.extend(offset_bits.data[offset_bits.start_byte()..offset_bits.end_byte()].to_vec());
            }
            else {
                // Combine last byte of data with first byte of offset_bits.data.
                // The first extra_bits come from the last byte of data, the rest from the first byte of offset_bits.data.
                let last_byte = data.pop().unwrap() & !(0xff >> extra_bits);
                let first_byte = offset_bits.data[0] & (0xff >> extra_bits);
                data.push(last_byte + first_byte);
                data.extend(&offset_bits.data[1..]);
            }
            new_length += bits.length;
        }
        BitRust {
            data: Arc::new(data),
            offset: new_offset,
            length: new_length,
        }
    }

    /// Returns the byte index of the start of the binary data.
    fn start_byte(&self) -> usize {
        self.offset / 8
    }

    /// Returns the byte index of one past the end of the binary data.
    fn end_byte(&self) -> usize {
        (self.offset + self.length + 7) / 8
    }

    pub(crate) fn active_data(&self) -> Vec<u8> {
        self.data[self.start_byte()..self.end_byte()].to_vec()
    }
    
    /// Return copy with a new offset (< 8). Any excess bytes will be trimmed.
    fn copy_with_new_offset(&self, new_offset: usize) -> Self {
        assert!(new_offset < 8);
        // Create a new Bits object with the same value but a different offset.
        // Each byte will in general have to be bit shifted to the left or right.
        if self.length == 0 {
            return BitRust {
                data: Arc::new(vec![]),
                offset: 0,
                length: 0,
            }
        }
        let byte_offset = self.offset / 8;
        let bit_offset = self.offset % 8;
        if new_offset == bit_offset {
            return BitRust {
                data: Arc::new(self.active_data()),
                offset: new_offset,
                length: self.length,
            }
        }
        let old_byte_length = self.end_byte() - self.start_byte();
        let new_byte_length = (self.length + new_offset + 7) / 8;
        let mut new_data: Vec<u8> = vec![0; new_byte_length];
        if new_offset < bit_offset {
            let left_shift = bit_offset - new_offset;
            debug_assert!(left_shift < 8);
            debug_assert!(new_byte_length == old_byte_length || new_byte_length == old_byte_length - 1);
            // Do everything up to the final byte
            for i in 0..new_byte_length - 1 {
                new_data[i] = (self.data[i + byte_offset] << left_shift) + (self.data[i + 1 + byte_offset] >> (8 - left_shift));
            }
            // The final byte
            if old_byte_length == new_byte_length {
                new_data[new_byte_length - 1] = self.data[byte_offset + new_byte_length - 1] << left_shift;
            } else {
                debug_assert!(old_byte_length - 1 == new_byte_length);
                new_data[new_byte_length - 1] = (self.data[byte_offset + new_byte_length - 1] << left_shift) +
                    (self.data[byte_offset + new_byte_length] >> (8 - left_shift));
            }
        }
        else {
            let right_shift = new_offset - bit_offset;
            debug_assert!(right_shift < 8);
            debug_assert!(new_byte_length == old_byte_length || new_byte_length == old_byte_length + 1);
            new_data[0] = self.data[byte_offset] >> right_shift;
            for i in 1..old_byte_length {
                new_data[i] = (self.data[i + byte_offset] >> right_shift) + (self.data[i + byte_offset - 1] << (8 - right_shift));
            }
            if new_byte_length > old_byte_length {
                new_data[new_byte_length - 1] = self.data[byte_offset + old_byte_length - 1] << (8 - right_shift);
            }
        }
        BitRust {
            data: Arc::new(new_data),
            offset: new_offset,
            length: self.length,
        }
    }
    
    /// Slice used internally without bounds checking.
    fn slice(&self, start_bit: usize, end_bit: usize) -> Self {
        assert!(start_bit <= end_bit);
        assert!(end_bit <= self.length);
        let new_length = end_bit - start_bit;
        BitRust {
            data: Arc::clone(&self.data),
            offset: start_bit + self.offset,
            length: new_length,
        }
    }

    // Return a new Bits with any excess stored bytes trimmed.
    pub fn trim(&self) -> Self {
        if self.offset < 8 && self.end_byte() == self.data.len() {
            return BitRust {
                data: Arc::clone(&self.data),
                offset: self.offset,
                length: self.length,
            }
        }
        BitRust {
            data: Arc::new(self.active_data()),
            offset: self.offset % 8,
            length: self.length,
        }
    }

    // This works as a Rust version. Not sure how to make a proper Python interface.
    pub fn find_all_rust<'a>(&'a self, b: &'a BitRust, bytealigned: bool) -> impl Iterator<Item = usize> + 'a {
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

    fn to_bitvec(&self) -> BitVec<u8, Msb0> {
        let mut b: BitVec<u8, Msb0> = BitVec::from_vec(self.active_data());
        // Remove the offset bits
        b.drain(..self.offset % 8);
        // And truncate to the proper length
        b.truncate(self.length);
        b
    }

}

#[pymethods]
impl BitRust {

    // A stop-gap. We really want to return an iterator of i64.
    pub fn findall_list(&self, b: &BitRust, bytealigned: bool) -> Vec<usize>  {
        let pos: Vec<usize> = self.find_all_rust(b, bytealigned).collect();
        pos
    }

    pub fn __len__(&self) -> usize {
        self.length
    }

    pub fn __eq__(&self, rhs: &BitRust) -> bool {
        self == rhs
    }

    #[staticmethod]
    pub fn from_zeros(length: usize) -> Self {
        BitRust {
            data: Arc::new(vec![0; (length + 7) / 8]),
            offset: 0,
            length,
        }
    }

    #[staticmethod]
    pub fn from_ones(length: usize) -> Self {
        BitRust {
            data: Arc::new(vec![0xff; (length + 7) / 8]),
            offset: 0,
            length,
        }
    }

    #[staticmethod]
    pub fn from_bytes(data: Vec<u8>) -> Self {
        let bitlength = data.len() * 8;
        BitRust {
            data: Arc::new(data),
            offset: 0,
            length: bitlength,
        }
    }

    #[staticmethod]
    pub fn from_bytes_with_offset(data: Vec<u8>, offset: usize) -> Self {
        assert!(offset < 8);
        let bitlength = data.len() * 8 - offset;
        BitRust {
            data: Arc::new(data),
            offset,
            length: bitlength,
        }
    }

    #[staticmethod]
    pub fn from_bin(binary_string: &str) -> PyResult<Self> {
        // Convert the binary string to a bitvec first
        let mut b: BitVec<u8, Msb0> = BitVec::with_capacity(binary_string.len());
        for c in binary_string.chars() {
            match c {
                '0' => b.push(false),
                '1' => b.push(true),
                _ => return Err(PyValueError::new_err("Invalid character")),
            }
        }
        // Convert to bytes
        b.set_uninitialized(false);
        let data = b.into_vec();
        Ok(BitRust {
            data: Arc::new(data),
            offset: 0,
            length: binary_string.len(),
        })
    }

    #[staticmethod]
    pub fn from_hex(hex: &str) -> PyResult<Self> {
        let mut new_hex = hex.to_string();
        let is_odd_length: bool = hex.len() % 2 != 0;
        if is_odd_length {
            new_hex.push('0');
        }
        let data = match hex::decode(new_hex) {
            Ok(d) => d,
            Err(_) => return Err(PyValueError::new_err("Invalid character")),
        };
        Ok(BitRust {
            data: Arc::new(data),
            offset: 0,
            length: hex.len() * 4,
        })
    }

    #[staticmethod]
    pub fn join(bits_vec: Vec<PyRef<BitRust>>) -> Self {
        let my_vec: Vec<&BitRust> = bits_vec.iter().map(|x| &**x).collect();
        BitRust::join_internal(&my_vec)
    }

    #[staticmethod]
    pub fn from_oct(oct: &str) -> PyResult<Self> {
        let mut bin_str = String::new();
        for ch in oct.chars() {
            // Convert each ch to an integer
            let digit = match ch.to_digit(8) {
                Some(d) => d,
                None => return Err(PyValueError::new_err("Invalid character")),
            };
            bin_str.push_str(&format!("{:03b}", digit)); // Format as 3-bit binary
        }
        Ok(BitRust::from_bin(&bin_str).unwrap())
    }

    /// Convert to bytes, padding with zero bits if needed.
    pub fn to_bytes(&self) -> Vec<u8> {
        if self.length == 0 {
            return Vec::new();
        }
        let no_offset: &BitRust = if self.offset == 0 {
            self
        } else {
            &self.copy_with_new_offset(0)
        };
        if no_offset.length % 8 == 0 {
            // No offset and whole-byte data
            return no_offset.active_data();
        }
        // Make sure final byte is padded with zeros
        let mut bytes = no_offset.active_data();
        let padding_mask: u8 = 0xff << (8 - (no_offset.length % 8));
        let bytes_len = bytes.len();
        bytes[bytes_len - 1] &= padding_mask;
        bytes
    }

    // Just the byte data without any shifting or padding.
    pub fn to_byte_data_with_offset(&self) -> (Vec<u8>, usize) {
        (self.active_data(), self.offset % 8)
    }

    // Return bytes that can easily be converted to an int in Python
    pub fn to_int_byte_data(&self, signed: bool) -> Vec<u8> {
        // Want the offset to make there be no padding.
        let new_offset = (self.offset + (8 - (self.length + self.offset) % 8)) % 8;
        debug_assert!((new_offset + self.length) % 8 == 0);
        let mut t = if self.offset == new_offset {
             self.active_data()
        } else {
            self.copy_with_new_offset(new_offset).data.to_vec()
        };
        if new_offset != 0 {
            // Set all the new offset bits to zero
            t[0] &= (1 << (8 - new_offset)) - 1;
            // For signed, if top bit is set, so need to set all the new offset bits too.
            if signed == true && (t[0] & (0x80 >> new_offset) != 0) {
                t[0] |= !(0xff >> new_offset);
            }
        }
        t
    }

    pub fn to_hex(&self) -> PyResult<String> {
        if self.length % 4 != 0 {
            return Err(PyValueError::new_err("Not a multiple of 4 bits long."));
        }
        let bit_offset = self.offset % 8;
        let nibble_offset_data: &Vec<u8> = if bit_offset == 0 || bit_offset == 4 {
            &self.active_data()
        } else {
            &self.copy_with_new_offset(0).data
        };
        let x = nibble_offset_data.iter()
            .map(|byte| format!("{:02x}", byte))
            .fold(String::new(), |mut acc, hex| {
                acc.push_str(&hex);
                acc
            });
        if bit_offset == 4 {
            if self.length % 8 == 0 {
                return Ok(x[1..x.len()-1].to_string());
            }
            return Ok(x[1..].to_string());
        }
        if self.length % 8 == 0 {
            return Ok(x);
        }
        debug_assert_eq!(self.length % 8, 4);
        Ok(x[..x.len()-1].to_string())
    }

    pub fn to_bin(&self) -> String {
        self.to_bitvec().iter().map(|x| if *x { '1' } else { '0' }).collect::<String>()
    }

    pub fn to_oct(&self) -> PyResult<String> {
        if self.length % 3 != 0 {
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
        match self.bitwise_op(other, |a, b| a & b) {
            Ok(b) => Ok(b),
            Err(_) => Err(PyValueError::new_err("Lengths do not match.")),
        }
    }
    pub fn __or__(&self, other: &BitRust) -> PyResult<BitRust> {
        match self.bitwise_op(other, |a, b| a | b) {
            Ok(b) => Ok(b),
            Err(_) => Err(PyValueError::new_err("Lengths do not match.")),
        }
    }
    pub fn __xor__(&self, other: &BitRust) -> PyResult<BitRust> {
        match self.bitwise_op(other, |a, b| a ^ b) {
            Ok(b) => Ok(b),
            Err(_) => Err(PyValueError::new_err("Lengths do not match.")),
        }
    }

    pub fn find(&self, b: &BitRust, start: usize, bytealigned: bool) -> Option<usize> {
        let s = self.to_bitvec();
        let pattern = b.to_bitvec();
        let mut pos = find_bitvec(&s , &pattern, start);
        if !bytealigned {
            return pos;
        }
        while let Some(p) = pos {
            if p % 8 == 0 {
                return pos;
            }
            pos = find_bitvec(&s, &pattern,  p + 1);
        }
        None
    }
    
    pub fn rfind(&self, b: &BitRust, start: usize, bytealigned: bool) -> Option<usize> {
        if b.length + start > self.length {
            return None;
        }
        let step = if bytealigned { 8 } else { 1 };
        let mut pos = self.length - b.length;
        if bytealigned {
            pos = pos / 8 * 8;
        }
        while pos >= start + step {
            if self.slice(pos, pos + b.length) == *b {
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
        let offset = self.offset % 8;
        let padding = if (self.length + offset) % 8 == 0 { 0 } else { 8 - (self.length + offset) % 8 };
        // Case where there's only one byte of used data.
        if self.start_byte() + 1 == self.end_byte() {
            return ((self.data[self.start_byte()] << offset) >> (offset + padding)).count_ones() as usize;
        }
        let mut c = hamming::weight(&self.data[self.start_byte()..self.end_byte()]) as usize;
        // Subtract any bits in the offset or padding.
        if offset != 0 {
            c -= (self.data[self.start_byte()] >> (8 - offset)).count_ones() as usize;
        }
        if padding != 0 {
            c -= (self.data[self.end_byte() - 1] << (8 -padding)).count_ones() as usize;
        }
        c
    }

    /// Returns a new BitRust with all bits reversed.
    pub fn reverse(&self) -> Self {
        let mut data: Vec<u8> = Vec::new();
        for byte in self.data[self.start_byte()..self.end_byte()].iter().rev() {
            data.push(byte.reverse_bits());
        }
        let final_bits = (self.offset + self.length) % 8;
        let new_offset = if final_bits == 0 { 0 } else { 8 - final_bits };
        BitRust {
            data: Arc::new(data),
            offset: new_offset,
            length: self.length,
        }
    }

    /// Returns the bool value at a given bit index.
    pub fn getindex(&self, mut bit_index: i64) -> PyResult<bool> {
        let length = self.length;
        if bit_index >= length as i64 || bit_index < -(length as i64) {
            return Err(PyIndexError::new_err("Out of range."));
        }
        if bit_index < 0 {
            bit_index += length as i64;
        }
        debug_assert!(bit_index >= 0);
        let p = bit_index as usize + self.offset;
        let byte = self.data[p / 8];
        Ok(byte & (128 >> (p % 8)) != 0)
    }
    
    /// Returns the bit offset to the data in the Bits object.
    pub fn offset(&self) -> usize {
        self.offset
    }

    /// Returns the length of the Bits object in bits.
    pub fn length(&self) -> usize {
        self.length
    }

    /// Returns a reference to the raw data in the Bits object.
    /// Note that the offset and length values govern which part of this raw buffer is the actual
    /// binary data.
    pub fn data(&self) -> &Vec<u8> {
        &self.data
    }

    /// Return a slice of the current BitRust. Uses a view on the current byte data.
    #[pyo3(signature = (start_bit, end_bit=None))]
    pub fn getslice(&self, start_bit: usize, end_bit: Option<usize>) -> PyResult<Self> {
        let end_bit = end_bit.unwrap_or(self.length);
        if start_bit >= end_bit {
            return Ok(BitRust::from_zeros(0)); // TODO: Use static instance for empty BitRust ?
        }
        assert!(start_bit < end_bit);
        if end_bit > self.length {
            return Err(PyValueError::new_err("end bit goes past the end"));
        }
        let new_length = end_bit - start_bit;
        Ok(BitRust {
            data: Arc::clone(&self.data),
            offset: start_bit + self.offset,
            length: new_length,
        })
    }

    // Return new BitRust with single bit flipped. If pos is None then flip all the bits.
    #[pyo3(signature = (pos=None))]
    pub fn invert(&self, pos: Option<usize>) -> Self {
        let mut data: Vec<u8> = Vec::new();
        match pos {
            None => {
                // Invert every bit
                for byte in self.data[self.start_byte()..self.end_byte()].iter() {
                    data.push(byte ^ 0xff);
                }
            }
            Some(pos) => {
                // Just invert the bit at pos
                data = self.active_data();
                data[(pos + self.offset) / 8] ^= 128 >> ((pos + self.offset) % 8);
            }
        }
        BitRust {
            data: Arc::new(data),
            offset: self.offset,
            length: self.length,
        }
    }

    /// Returns true if all of the bits are set to 1.
    pub fn all_set(&self) -> bool {
        self.count() == self.length
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
    pub fn set_from_sequence(&self, value: bool, indices: Vec<i64>) -> PyResult<Self> {
        let mut data: Vec<u8> = self.active_data();
        let offset = self.offset % 8;
        let mut positive_indices: Vec<usize> = vec![];
        for index in indices {
            if -index > self.length as i64 {
                return Err(PyIndexError::new_err("Negative index past the end"));
            }
            if index >= self.length as i64 {
                return Err(PyIndexError::new_err("Index out of range."))
            }
            positive_indices.push(if index < 0 { (self.length as i64 + index) as usize } else { index as usize});
        }
        for index in positive_indices {
            let byte_offset = (index + offset) / 8;
            let bit_offset = (index + offset) % 8;
            if value {
                data[byte_offset] |= 128 >> bit_offset;
            } else {
                data[byte_offset] &= !(128 >> bit_offset);
            }
        }
        Ok(BitRust {
            data: Arc::new(data),
            offset,
            length: self.length,
        })
    }

    pub fn set_from_slice(&self, value: bool, start: i64, stop: i64, step: i64) -> PyResult<Self> {
        // One way to do this (for lower values of step) would be to create a whole-byte mask
        // of the bit pattern and apply that before cleaning up the edges.
        // And of course if step is 1 or -1 that's a special case too!
        let mut data: Vec<u8> = self.active_data();
        let offset = self.offset % 8;
        let positive_start = if start < 0 { start + self.length as i64 } else { start };
        let positive_stop = if stop < 0 { stop + self.length as i64 } else { stop };
        if positive_start < 0 || positive_start >= self.length as i64 {
            return Err(PyIndexError::new_err("Start of slice out of bounds."));
        }
        if positive_stop < 0 || positive_start >= self.length as i64 {
            return Err(PyIndexError::new_err("End of slice out of bounds."));
        }
        for index in (positive_start..positive_stop).step_by(step as usize) {
            let byte_offset = (index as usize + offset) / 8;
            let bit_offset = (index as usize + offset) % 8;
            if value {
                data[byte_offset] |= 128 >> bit_offset;
            } else {
                data[byte_offset] &= !(128 >> bit_offset);
            }
        }
        Ok(BitRust {
            data: Arc::new(data),
            offset,
            length: self.length,
        })
    }

    /// Return a copy with a real copy of the data.
    pub fn get_mutable_copy(&self) -> Self {
        BitRust {
            data: Arc::new(self.active_data()),
            offset: self.offset % 8,
            length: self.length,
        }
    }

    pub fn set_mutable_slice(&mut self, start: usize, end: usize, value: &BitRust) -> PyResult<()> {
        let start_slice = self.getslice(0, Some(start))?;
        let end_slice = self.getslice(end, Some(self.length))?;
        let joined = BitRust::join_internal(&vec![&start_slice, value, &end_slice]);
        *self = joined;
        Ok(())
    }
}

#[test]
fn from_bytes() {
    let data: Vec<u8> = vec![10, 20, 30];
    let bits = BitRust::from_bytes(data);
    assert_eq!(*bits.data(), vec![10, 20, 30]);
    assert_eq!(bits.offset(), 0);
    assert_eq!(bits.length(), 24);
}

#[test]
fn from_hex() {
    let bits = BitRust::from_hex("0a141e").unwrap();
    assert_eq!(*bits.data(), vec![10, 20, 30]);
    assert_eq!(bits.offset(), 0);
    assert_eq!(bits.length(), 24);
    let bits = BitRust::from_hex("").unwrap();
    assert_eq!(bits.offset(), 0);
    assert_eq!(bits.length(), 0);
    let bits = BitRust::from_hex("hello");
    assert!(bits.is_err());
    let bits = BitRust::from_hex("1").unwrap();
    assert_eq!(*bits.data(), vec![16]);
    assert_eq!(bits.offset(), 0);
    assert_eq!(bits.length(), 4);
}

#[test]
fn from_bin() {
    let bits = BitRust::from_bin("00001010").unwrap();
    assert_eq!(*bits.data(), vec![10]);
    assert_eq!(bits.offset(), 0);
    assert_eq!(bits.length(), 8);
    let bits = BitRust::from_bin("").unwrap();
    assert_eq!(bits.offset(), 0);
    assert_eq!(bits.length(), 0);
    let bits = BitRust::from_bin("hello");
    assert!(bits.is_err());
    let bits = BitRust::from_bin("1").unwrap();
    assert_eq!(*bits.data(), vec![128]);
    assert_eq!(bits.offset(), 0);
    assert_eq!(bits.length(), 1);
}

#[test]
fn from_zeros() {
    let bits = BitRust::from_zeros(8);
    assert_eq!(*bits.data(), vec![0]);
    assert_eq!(bits.offset(), 0);
    assert_eq!(bits.length(), 8);
    assert_eq!(bits.to_hex().unwrap(), "00");
    let bits = BitRust::from_zeros(9);
    assert_eq!(*bits.data(), vec![0, 0]);
    assert_eq!(bits.offset(), 0);
    assert_eq!(bits.length(), 9);
    let bits = BitRust::from_zeros(0);
    assert_eq!(bits.offset(), 0);
    assert_eq!(bits.length(), 0);
}

#[test]
fn from_ones() {
    let bits = BitRust::from_ones(8);
    assert_eq!(*bits.data(), vec![255]);
    assert_eq!(bits.offset(), 0);
    assert_eq!(bits.length(), 8);
    assert_eq!(bits.to_hex().unwrap(), "ff");
    let bits = BitRust::from_ones(9);
    assert_eq!(bits.to_bin(), "111111111");
    assert!(bits.to_hex().is_err());
    assert_eq!((*bits.data())[0], 0xff);
    assert_eq!((*bits.data())[1] & 0x80, 0x80);
    assert_eq!(bits.offset(), 0);
    assert_eq!(bits.length(), 9);
    let bits = BitRust::from_ones(0);
    assert_eq!(bits.offset(), 0);
    assert_eq!(bits.length(), 0);
}

#[test]
fn get_index() {
    let bits = BitRust::from_bin("001100").unwrap();
    assert_eq!(bits.getindex(0).unwrap(), false);
    assert_eq!(bits.getindex(1).unwrap(), false);
    assert_eq!(bits.getindex(2).unwrap(), true);
    assert_eq!(bits.getindex(3).unwrap(), true);
    assert_eq!(bits.getindex(4).unwrap(), false);
    assert_eq!(bits.getindex(5).unwrap(), false);
    assert!(bits.getindex(6).is_err());
    assert!(bits.getindex(60).is_err());
}

// #[test]
// fn join_whole_byte() {
//     let b1 = BitRust::from_bytes(vec![5, 10, 20], None).slice( 0, 24);
//     let b2 = BitRust::from_bytes(vec![30, 40, 50], None);
//     let j = BitRust::join(&vec![&b1, &b2, &b1], None);
//     assert_eq!(*j.data(), vec![5, 10, 20, 30, 40, 50, 5, 10, 20]);
//     assert_eq!(j.offset(), 0);
//     assert_eq!(j.length(), 72);
// }

// #[test]
// fn join_single_bits() {
//     let b1 = Bits::from_bin("1").unwrap();
//     let b2 = Bits::from_bin("0").unwrap();
//     let bits = Bits::join(&vec![&b1, &b2, &b1]);
//     assert_eq!(bits.offset(), 0);
//     assert_eq!(bits.length(), 3);
//     assert_eq!(*bits.data(), vec![0b10100000]);
//     let b3 = Bits::from_bin("11111111").unwrap();
//     let j = Bits::join(&vec![&b2, &b3]);
//     assert_eq!(j.offset(), 0);
//     assert_eq!(j.length(), 9);
//     assert_eq!(*j.data(), vec![0b01111111, 0b10000000]);
//     let j = Bits::join(&vec![&b3, &b2, &b3]);
//     assert_eq!(j.offset(), 0);
//     assert_eq!(j.length(), 17);
//     assert_eq!(j, Bits::from_bin("11111111011111111").unwrap());
// }

#[test]
fn hex_edge_cases() {
    let b1 = BitRust::from_hex("0123456789abcdef").unwrap();
    let b2 = b1.getslice(12, Some(b1.length())).unwrap();
    assert_eq!(b2.to_hex().unwrap(), "3456789abcdef");
    assert_eq!(b2.offset(), 12);
    assert_eq!(b2.length(), 52);
    assert_eq!(b2.data().len(), 8);
    let bp = b2.trim();
    assert_eq!(bp, b2);
    assert_eq!(bp.offset(), 4);
    assert_eq!(bp.length(), 52);
    assert_eq!(bp.data().len(), 7);

    // let b2 = Bits::new(vec![0x01, 0x23, 0x45, 0x67], 12, 12).unwrap();
    // assert_eq!(b2.to_hex().unwrap(), "345");
}

// #[test]
// fn a_few_things() {
//     let b1 = Bits::from_hex("abcdef").unwrap();
//     let b2 = Bits::from_bin("01").unwrap();
//     let b4 = Bits::join(&vec![&b1, &b2]).trim();
//     assert_eq!(b4.length(), 26);
//     assert_eq!(b4.to_bin(), "10101011110011011110111101");
//     let b5 = Bits::join(&vec![&b1, &b1]);
//     assert_eq!(b5.length(), 48);
//     assert_eq!(b5.to_hex().unwrap(), "abcdefabcdef");
//     let b6 = Bits::join(&vec![&b2, &b2, &b1]);
//     assert_eq!(b6.length(), 28);
//     assert_eq!(b6.to_bin(), "0101101010111100110111101111");
//     assert_eq!(b6.to_hex().unwrap(), "5abcdef");
//     let b3 = Bits::join(&vec![&b1, &b2, &b1, &b2]);
//     assert_eq!(b3.length(), 52);
//     assert_eq!(b3.to_hex().unwrap(), "abcdef6af37bd");
//     // assert_eq!(b3.get_slice(Some(b1.get_length() + 2), Some(b3.get_length() - 2)).unwrap().to_hex().unwrap(), "abcdef");
// }

#[test]
fn test_count() {
    let x = vec![1, 2, 3];
    let b = BitRust::from_bytes(x);
    assert_eq!(b.count(), 4);
}

#[test]
fn test_reverse() {
    let b = BitRust::from_bin("11110000").unwrap();
    let bp = b.reverse();
    assert_eq!(bp.to_bin(), "00001111");
    let b = BitRust::from_bin("1").unwrap();
    let bp = b.reverse();
    assert_eq!(bp.to_bin(), "1");
    let empty = BitRust::from_bin("").unwrap();
    let empty_p = empty.reverse();
    assert_eq!(empty_p.to_bin(), "");
    let b = BitRust::from_bin("11001").unwrap();
    let bp = b.reverse();
    assert_eq!(bp.to_bin(), "10011");
    let hex_str = "98798379287592836521000cbdbeff";
    let long = BitRust::from_hex(hex_str).unwrap();
    let rev = long.reverse();
    assert_eq!(rev.reverse(), long);
}

#[test]
fn test_invert() {
    let b = BitRust::from_bin("0").unwrap();
    assert_eq!(b.invert(None).to_bin(), "1");
    let b = BitRust::from_bin("01110").unwrap();
    assert_eq!(b.invert(None).to_bin(), "10001");
    let hex_str = "abcdef8716258765162548716258176253172635712654714";
    let long = BitRust::from_hex(hex_str).unwrap();
    let temp = long.invert(None);
    assert_eq!(long.length(), temp.length());
    assert_eq!(temp.invert(None), long);
}

// #[test]
// fn test_join_again() {
//     let b1 = Bits::from_hex("0123456789").unwrap();
//     let b2 = b1.slice(12, 24);
//     let b3 = Bits::join(&vec![&b2, &b2]);
//     assert_eq!(b3.to_hex().unwrap(), "345345");
//     let b3 = Bits::join(&vec![&b2, &b2, &b1]);
//     assert_eq!(b3.to_hex().unwrap(), "3453450123456789");
// }

#[test]
fn test_find() {
    let b1 = BitRust::from_zeros(10);
    let b2 = BitRust::from_ones(2);
    assert_eq!(b1.find(&b2, 0,false), None);
    let b3 = BitRust::from_bin("00001110").unwrap();
    let b4 = BitRust::from_bin("01").unwrap();
    assert_eq!(b3.find(&b4, 0, false), Some(3));
    assert_eq!(b3.find(&b4, 2,false), Some(3));

    let s = BitRust::from_bin("0000110110000").unwrap();
    let f = BitRust::from_bin("11011").unwrap();
    let p = s.find(&f, 0, false).unwrap();
    assert_eq!(p, 4);

    let s = BitRust::from_hex("010203040102ff").unwrap();
    // assert s.find("0x05", bytealigned=True) is None
    let f = BitRust::from_hex("02").unwrap();
    let p = s.find(&f, 0, true);
    assert_eq!(p, Some(8));

}

#[test]
fn test_rfind() {
    let b1 = BitRust::from_hex("00780f0").unwrap();
    let b2 = BitRust::from_bin("1111").unwrap();
    assert_eq!(b1.rfind(&b2, 0, false), Some(20));
    assert_eq!(b1.find(&b2, 0, false), Some(9));

}

#[test]
fn test_and() {
    let a1 = BitRust::from_hex("f0f").unwrap();
    let a2 = BitRust::from_hex("123").unwrap();
    let a3 = a1.__and__(&a2).unwrap();
    assert_eq!(a3, BitRust::from_hex("103").unwrap());
}

#[test]
fn test_findall() {
    let b = BitRust::from_hex("00ff0ff0").unwrap();
    let a = BitRust::from_hex("ff").unwrap();
    let q: Vec<usize> = b.find_all_rust(&a, false).collect();
    assert_eq!(q, vec![8, 20]);

    let a = BitRust::from_hex("fffff4512345ff1234ff12ff").unwrap();
    let b = BitRust::from_hex("ff").unwrap();
    let q: Vec<usize> = a.find_all_rust(&b, true).collect();
    assert_eq!(q, vec![0, 8, 6*8, 9*8, 11*8]);
}

#[test]
fn test_copy_with_new_offset() {
    let bit_list = vec!["0", "1", "00110011", "11111111000000001", "00", "11", "01010101010101010101010101010"];
    for bit_str in bit_list {
        for start in 0..bit_str.len() {
            for end in start..bit_str.len() {
                let a = BitRust::from_bin(bit_str).unwrap().slice(start, end);
                for offset in 0..=7 {
                    let b = a.copy_with_new_offset(offset);
                    assert_eq!(b.to_bin(), &bit_str[start..end], "'{}' {} {} {}", bit_str, offset, start, end);
                    if b.length() != 0 {
                        assert_eq!(b.offset, offset, "'{}' {} {} {}", bit_str, offset, start, end);
                    }
                }
            }
        }
    }
}

#[test]
fn test_set_mutable_slice() {
    let mut a = BitRust::from_hex("0011223344").unwrap();
    let b = BitRust::from_hex("ff").unwrap();
    a.set_mutable_slice(8, 16, &b).unwrap();
    assert_eq!(a.to_hex().unwrap(), "00ff223344");
}

#[test]
fn test_getslice() {
    let a = BitRust::from_bin("00010001").unwrap();
    assert_eq!(a.getslice(0, Some(4)).unwrap().to_bin(), "0001");
    assert_eq!(a.getslice(4, Some(8)).unwrap().to_bin(), "0001");
}

#[test]
fn test_all_set() {
    let b = BitRust::from_bin("111").unwrap();
    assert!(b.all_set());
    let c = BitRust::from_oct("7777777777").unwrap();
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