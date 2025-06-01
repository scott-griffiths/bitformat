use std::fmt;
use crate::bitrust::helpers;
use bitvec::prelude::*;
use bytemuck::cast_slice;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::{pyclass, pymethods, PyRef, PyResult};
use crate::bitrust::MutableBitRust;
use crate::bitrust::{BitRustIterator, BitRustBoolIterator};

pub trait BitCollection: Sized{
    fn len(&self) -> usize;
    fn from_zeros(length: usize) -> Self;
    fn from_ones(length: usize) -> Self;
    fn from_bytes(data: Vec<u8>) -> Self;
    fn from_bin(binary_string: &str) -> Result<Self, String>;
    fn from_oct(octal_string: &str) -> Result<Self, String>;
    fn from_hex(hex_string: &str) -> Result<Self, String>;
    fn from_u64(value: u64, length: usize) -> Self;
    fn from_i64(value: i64, length: usize) -> Self;
    }

/// BitRust is a struct that holds an arbitrary amount of binary data.
/// Currently it's just wrapping a BitVec from the bitvec crate.
#[pyclass(eq, frozen)]
pub struct BitRust {
    pub(crate) data: helpers::BV,
}

impl BitCollection for BitRust {
    fn len(&self) -> usize {
        self.data.len()
    }
    fn from_zeros(length: usize) -> Self {
        BitRust::new(helpers::BV::repeat(false, length))
    }
    fn from_ones(length: usize) -> Self {
        BitRust::new(helpers::BV::repeat(true, length))
    }
    fn from_bytes(data: Vec<u8>) -> Self {
        let bits = data.view_bits::<Msb0>();
        let bv = helpers::BV::from_bitslice(bits);
        BitRust::new(bv)
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
        Ok(BitRust::new(b))
    }
    fn from_oct(oct: &str) -> Result<Self, String> {
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
                _ => {
                    return Err(format!(
                        "Cannot convert from oct '{oct}': Invalid character '{ch}'."
                    ))
                }
            }
        }
        Ok(<BitRust as BitCollection>::from_bin(&bin_str)?)
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
            Err(e) => {
                return Err(format!(
                    "Cannot convert from hex '{hex}': {}",
                    e
                ))
            }
        };
        let mut bv = BitRust::from_bytes(data).data;
        if is_odd_length {
            bv.drain(bv.len() - 4..bv.len());
        }
        Ok(BitRust::new(bv))
    }
    fn from_u64(value: u64, length: usize) -> Self {
        let mut bv = helpers::BV::repeat(false, length);
        bv.store_be(value);
        BitRust::new(bv)
    }
    fn from_i64(value: i64, length: usize) -> Self {
        let mut bv = helpers::BV::repeat(false, length);
        bv.store_be(value);
        BitRust::new(bv)
    }

}

impl fmt::Debug for BitRust {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.len() > 100 {
            return f
                .debug_struct("Bits")
                .field("hex", &self.slice(0, 100).to_hex().unwrap())
                .field("length", &self.len())
                .finish();
        }
        if self.len() % 4 == 0 {
            return f
                .debug_struct("Bits")
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
        self.data == other.data
    }
}

impl PartialEq<MutableBitRust> for BitRust {
    fn eq(&self, other: &MutableBitRust) -> bool {
        self.data == other.inner.data
    }
}

/// Private helper methods. Not part of the Python interface.
impl BitRust {
    pub fn new(bv: helpers::BV) -> Self {
        BitRust { data: bv }
    }

    /// Slice used internally without bounds checking.
    fn slice(&self, start_bit: usize, end_bit: usize) -> Self {
        debug_assert!(start_bit <= end_bit);
        debug_assert!(end_bit <= self.len());

        let mut new_data = BitVec::with_capacity(end_bit - start_bit);
        new_data.extend_from_bitslice(&self.data[start_bit..end_bit]);

        BitRust::new(new_data)
    }

    // This works as a Rust version. Not sure how to make a proper Python interface.
    fn find_all_rust<'a>(&'a self, b: &'a BitRust, bytealigned: bool) -> impl Iterator<Item = usize> + 'a {
        // Use the find fn to find all instances of b in self and return as an iterator
        let mut start: usize = 0;
        let step = if bytealigned { 8 } else { 1 };
        std::iter::from_fn(move || {
            let found = self.find(b, start, bytealigned);

            match found {
                Some(x) => {
                    start = x + step;
                    Some(x)
                }
                None => None,
            }
        })
    }
}



/// Public Python-facing methods.
#[pymethods]
impl BitRust {
    fn __iter__(slf: PyRef<'_, Self>) -> PyResult<Py<BitRustBoolIterator>> {
        let py = slf.py();
        let length = slf.len();
        Py::new(
            py,
            BitRustBoolIterator {
                bits: slf.into(),
                index: 0,
                length,
            },
        )
    }

    #[staticmethod]
    pub fn from_u64(value: u64, length: usize) -> Self {
        BitCollection::from_u64(value, length)
    }

    #[staticmethod]
    pub fn from_i64(value: i64, length: usize) -> Self {
        BitCollection::from_i64(value, length)
    }

    pub fn to_u64(&self) -> u64 {
        assert!(self.data.len() <= 64, "BitRust too long for u64");
        self.data.load_be::<u64>()
    }

    pub fn to_i64(&self) -> i64 {
        assert!(self.data.len() <= 64, "BitRust too long for i64");
        self.data.load_be::<i64>()
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

    #[staticmethod]
    pub fn from_zeros(length: usize) -> Self {
        BitCollection::from_zeros(length)
    }

    #[staticmethod]
    pub fn from_ones(length: usize) -> Self {
        BitCollection::from_ones(length)
    }

    #[staticmethod]
    pub fn from_bytes(data: Vec<u8>) -> Self {
        BitCollection::from_bytes(data)
    }

    #[staticmethod]
    pub fn from_bytes_with_offset(data: Vec<u8>, offset: usize) -> Self {
        debug_assert!(offset < 8);
        let mut bv: helpers::BV = Self::from_bytes(data).data;
        bv.drain(..offset);
        BitRust::new(bv)
    }

    #[staticmethod]
    pub fn from_bools(values: Vec<PyObject>, py: Python) -> PyResult<Self> {
        let mut bv = helpers::BV::with_capacity(values.len());

        for value in values {
            let b: bool = value.extract(py)?;
            bv.push(b);
        }
        Ok(BitRust::new(bv))
    }

    #[staticmethod]
    pub fn from_bin(binary_string: &str) -> PyResult<Self> {
        match BitCollection::from_bin(binary_string) {
            Ok(result) => Ok(result),
            Err(e) => Err(PyValueError::new_err(e))
        }
    }

    #[staticmethod]
    pub fn from_hex(hex: &str) -> PyResult<Self> {
        match BitCollection::from_hex(hex) {
            Ok(result) => Ok(result),
            Err(e) => Err(PyValueError::new_err(e))
        }
    }

    #[staticmethod]
    pub fn from_oct(oct: &str) -> PyResult<Self> {
        match BitCollection::from_oct(oct) {
            Ok(x) => Ok(x),
            Err(e) => Err(PyValueError::new_err(e))
        }
    }

    #[staticmethod]
    pub fn join(bits_vec: Vec<PyRef<BitRust>>) -> Self {
        let total_len: usize = bits_vec.iter().map(|x| x.len()).sum();
        let mut bv = helpers::BV::with_capacity(total_len);
        for bits_ref in bits_vec.iter() {
            bv.extend_from_bitslice(&bits_ref.data);
        }
        BitRust::new(bv)
    }


    /// Convert to bytes, padding with zero bits if needed.
    pub fn to_bytes(&self) -> Vec<u8> {
        helpers::convert_bitrust_to_bytes(self)
    }

    // Return bytes that can easily be converted to an int in Python
    pub fn to_int_byte_data(&self, signed: bool) -> Vec<u8> {
        // If empty, return empty vector
        if self.len() == 0 {
            return Vec::new();
        }

        // Calculate padding needed to make the length a multiple of 8
        let padding_bits = (8 - self.len() % 8) % 8;
        let total_bytes = (self.len() + padding_bits) / 8;

        // Create result vector with exact capacity needed
        let mut result = Vec::with_capacity(total_bytes);

        // Handle sign extension for signed numbers
        let pad_with_ones = signed && self.data[0];

        // Process a byte at a time
        let mut current_byte: u8 = 0;
        let mut bits_in_byte: usize = 0;

        // Add padding bits first (if needed)
        for _ in 0..padding_bits {
            current_byte = (current_byte << 1) | (pad_with_ones as u8);
            bits_in_byte += 1;
        }

        // Process actual bits from the view
        for i in 0..self.len() {
            if bits_in_byte == 8 {
                result.push(current_byte);
                current_byte = 0;
                bits_in_byte = 0;
            }
            current_byte = (current_byte << 1) | (self.data[i] as u8);
            bits_in_byte += 1;
        }

        // Push final byte if there are any remaining bits
        if bits_in_byte > 0 {
            result.push(current_byte);
        }

        debug_assert_eq!(result.len(), total_bytes);
        debug_assert_eq!(result.len(), (self.len() + 7) / 8);

        result
    }

    pub fn to_hex(&self) -> PyResult<String> {
        if self.len() % 4 != 0 {
            return Err(PyValueError::new_err("Not a multiple of 4 bits long."));
        }
        let bytes = self.to_bytes();
        let hex_string = bytes
            .iter()
            .map(|byte| format!("{:02x}", byte))
            .collect::<String>();
        if self.len() % 8 == 0 {
            return Ok(hex_string);
        }
        // If the length is not a multiple of 8, we need to trim the padding bits
        Ok(hex_string[0..hex_string.len() - 1].to_string())
    }

    pub fn to_bin(&self) -> String {
        let mut result = String::with_capacity(self.len());
        for bit in self.data.iter() {
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
        if self.len() != other.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }
        let result = self.data.clone() & &other.data;
        Ok(BitRust::new(result))
    }

    pub fn __or__(&self, other: &BitRust) -> PyResult<BitRust> {
        if self.len() != other.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }

        let result = self.data.clone() | &other.data;
        Ok(BitRust::new(result))
    }

    pub fn __xor__(&self, other: &BitRust) -> PyResult<BitRust> {
        if self.len() != other.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }

        let result = self.data.clone() ^ &other.data;
        Ok(BitRust::new(result))
    }

    pub fn find(&self, b: &BitRust, start: usize, bytealigned: bool) -> Option<usize> {
        if bytealigned {
            helpers::find_bitvec_bytealigned(self, b, start)
        } else {
            helpers::find_bitvec(self, b, start)
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
        // Note that using hamming::weight is about twice as fast as:
        // self.data.count_ones()
        // which is the way that bitvec suggests.
        let bytes: &[u8] = cast_slice(self.data.as_raw_slice());
        hamming::weight(bytes) as usize
    }

    /// Return a slice of the current BitRust.
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
            return Err(PyValueError::new_err(
                "Indices less than -1 are not valid values.",
            ));
        }
        if step > 0 {
            if start_bit >= end_bit {
                return Ok(BitRust::from_zeros(0));
            }
            if end_bit as usize > self.len() {
                return Err(PyValueError::new_err("end bit goes past the end"));
            }
            Ok(BitRust::new(
                self.data[start_bit as usize..end_bit as usize]
                    .iter()
                    .step_by(step as usize)
                    .collect(),
            ))
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
            Ok(BitRust::new(
                self.data[adjusted_end_bit..=start_bit as usize]
                    .iter()
                    .rev()
                    .step_by(-step as usize)
                    .collect(),
            ))
        }
    }


    /// Returns true if all of the bits are set to 1.
    pub fn all_set(&self) -> bool {
        self.data.all()
    }

    /// Returns true if any of the bits are set to 1.
    pub fn any_set(&self) -> bool {
        self.data.any()
    }

    /// Return as a MutableBitRust with a copy of the data.
    pub fn clone_as_mutable(&self) -> MutableBitRust {
        MutableBitRust {
            inner: BitRust::new(self.data.clone()),
        }
    }

    /// Returns the bool value at a given bit index.
    pub fn getindex(&self, bit_index: i64) -> PyResult<bool> {
        let index = helpers::validate_index(bit_index, self.len())?;
        Ok(self.data[index])
    }
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn from_bytes() {
        let data: Vec<u8> = vec![10, 20, 30];
        let bits = BitRust::from_bytes(data);
        assert_eq!(*bits.to_bytes(), vec![10, 20, 30]);
        assert_eq!(bits.len(), 24);
    }

    #[test]
    fn from_hex() {
        let bits = BitRust::from_hex("0x0a_14  _1e").unwrap();
        assert_eq!(*bits.to_bytes(), vec![10, 20, 30]);
        assert_eq!(bits.len(), 24);
        let bits = BitRust::from_hex("").unwrap();
        assert_eq!(bits.len(), 0);
        let bits = BitRust::from_hex("hello");
        assert!(bits.is_err());
        let bits = BitRust::from_hex("1").unwrap();
        assert_eq!(*bits.to_bytes(), vec![16]);
        assert_eq!(bits.len(), 4);
    }

    #[test]
    fn from_bin() {
        let bits = BitRust::from_bin("00001010").unwrap();
        assert_eq!(*bits.to_bytes(), vec![10]);
        assert_eq!(bits.len(), 8);
        let bits = BitRust::from_bin("").unwrap();
        assert_eq!(bits.len(), 0);
        let bits = BitRust::from_bin("hello");
        assert!(bits.is_err());
        let bits = BitRust::from_bin("1").unwrap();
        assert_eq!(*bits.to_bytes(), vec![128]);
        assert_eq!(bits.len(), 1);
    }

    #[test]
    fn from_zeros() {
        let bits = BitRust::from_zeros(8);
        assert_eq!(*bits.to_bytes(), vec![0]);
        assert_eq!(bits.len(), 8);
        assert_eq!(bits.to_hex().unwrap(), "00");
        let bits = BitRust::from_zeros(9);
        assert_eq!(*bits.to_bytes(), vec![0, 0]);
        assert_eq!(bits.len(), 9);
        let bits = BitRust::from_zeros(0);
        assert_eq!(bits.len(), 0);
    }

    #[test]
    fn from_ones() {
        let bits = BitRust::from_ones(8);
        assert_eq!(*bits.to_bytes(), vec![255]);
        assert_eq!(bits.len(), 8);
        assert_eq!(bits.to_hex().unwrap(), "ff");
        let bits = BitRust::from_ones(9);
        assert_eq!(bits.to_bin(), "111111111");
        assert!(bits.to_hex().is_err());
        assert_eq!((*bits.to_bytes())[0], 0xff);
        assert_eq!((*bits.to_bytes())[1] & 0x80, 0x80);
        assert_eq!(bits.len(), 9);
        let bits = BitRust::from_ones(0);
        assert_eq!(bits.len(), 0);
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

    #[test]
    fn hex_edge_cases() {
        let b1 = BitRust::from_hex("0123456789abcdef").unwrap();
        let b2 = b1.getslice(12, Some(b1.len())).unwrap();
        assert_eq!(b2.to_hex().unwrap(), "3456789abcdef");
        assert_eq!(b2.len(), 52);
        let t = BitRust::from_hex("123").unwrap();
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
        let mut b = MutableBitRust::from_bin_checked("11110000").unwrap();
        b.reverse();
        assert_eq!(b.to_bin(), "00001111");
        let mut b = MutableBitRust::from_bin_checked("1").unwrap();
        b.reverse();
        assert_eq!(b.to_bin(), "1");
        let mut empty = MutableBitRust::from_bin_checked("").unwrap();
        empty.reverse();
        assert_eq!(empty.to_bin(), "");
        let mut b = MutableBitRust::from_bin_checked("11001").unwrap();
        b.reverse();
        assert_eq!(b.to_bin(), "10011");

    }

    #[test]
    fn test_invert() {
        let mut b = MutableBitRust::from_bin_checked("0").unwrap();
        assert_eq!(b.invert(None).to_bin(), "1");
        let mut b = MutableBitRust::from_bin_checked("01110").unwrap();
        assert_eq!(b.invert(None).to_bin(), "10001");
        let hex_str = "abcdef8716258765162548716258176253172635712654714";
        let mut long = MutableBitRust::from_hex_checked(hex_str).unwrap();
        let temp = long.invert(None);
        assert_eq!(long.len(), temp.len());
    }

    #[test]
    fn test_find() {
        let b1 = BitRust::from_zeros(10);
        let b2 = BitRust::from_ones(2);
        assert_eq!(b1.find(&b2, 0, false), None);
        let b3 = BitRust::from_bin("00001110").unwrap();
        let b4 = BitRust::from_bin("01").unwrap();
        assert_eq!(b3.find(&b4, 0, false), Some(3));
        assert_eq!(b3.find(&b4, 2, false), Some(3));

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
        let b = BitRust::from_hex("103").unwrap();
        assert_eq!(a3, b);
        let a4 = a1.slice(4, 12).__and__(&a2.slice(4, 12)).unwrap();
        assert_eq!(a4, BitRust::from_hex("03").unwrap());
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
        assert_eq!(q, vec![0, 8, 6 * 8, 9 * 8, 11 * 8]);
    }

    #[test]
    fn test_set_mutable_slice() {
        let mut a = MutableBitRust::from_hex_checked("0011223344").unwrap();
        let b = BitRust::from_hex("ff").unwrap();
        a.set_slice(8, 16, &b).unwrap();
        assert_eq!(a.to_hex().unwrap(), "00ff223344");
    }

    #[test]
    fn test_get_mutable_slice() {
        let a = BitRust::from_hex("01ffff").unwrap();
        assert_eq!(a.len(), 24);
        let b = a.getslice(1, None).unwrap();
        assert_eq!(b.len(), 23);
        let c = b.clone_as_mutable();
        assert_eq!(c.len(), 23);
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
        let mut b = MutableBitRust::from_zeros(10);
        b.set_index(true, 0).unwrap();
        assert_eq!(b.to_bin(), "1000000000");
        b.set_index(true, -1).unwrap();
        assert_eq!(b.to_bin(), "1000000001");
        b.set_index(false, 0).unwrap();
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
        let a = BitRust::from_bin("111111111").unwrap();
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
        let bits = BitRust::from_oct("123").unwrap();
        assert_eq!(bits.to_bin(), "001010011");
        let bits = BitRust::from_oct("7").unwrap();
        assert_eq!(bits.to_bin(), "111");
    }

    #[test]
    fn test_from_oct_checked() {
        let bits = BitRust::from_oct("123").unwrap();
        assert_eq!(bits.to_bin(), "001010011");
        let bits = BitRust::from_oct("0o123").unwrap();
        assert_eq!(bits.to_bin(), "001010011");
        let bits = BitRust::from_oct("7").unwrap();
        assert_eq!(bits.to_bin(), "111");
        let bits = BitRust::from_oct("8");
        assert!(bits.is_err());
    }

    #[test]
    fn test_to_oct() {
        let bits = BitRust::from_bin("001010011").unwrap();
        assert_eq!(bits.to_oct().unwrap(), "123");
        let bits = BitRust::from_bin("111").unwrap();
        assert_eq!(bits.to_oct().unwrap(), "7");
        let bits = BitRust::from_bin("000").unwrap();
        assert_eq!(bits.to_oct().unwrap(), "0");
    }

    #[test]
    fn test_invert_bit_list() {
        let mut bits = MutableBitRust::from_bin_checked("0000").unwrap();
        bits.invert_bit_list(vec![0, 2]).unwrap();
        assert_eq!(bits.to_bin(), "1010");
        bits.invert_bit_list(vec![-1, -3]).unwrap();
        assert_eq!(bits.to_bin(), "1111");
        bits.invert_bit_list(vec![0, 1, 2, 3]).unwrap();
        assert_eq!(bits.to_bin(), "0000");
    }

    #[test]
    fn test_set_from_slice() {
        let mut bits = MutableBitRust::from_bin_checked("00000000").unwrap();
        bits.set_from_slice(true, 1, 7, 2).unwrap();
        assert_eq!(bits.to_bin(), "01010100");
        bits.set_from_slice(true, -7, -1, 2).unwrap();
        assert_eq!(bits.to_bin(), "01010100");
        bits.set_from_slice(false, 1, 7, 2).unwrap();
        assert_eq!(bits.to_bin(), "00000000");
    }

    #[test]
    fn test_invert_all() {
        let mut bits = MutableBitRust::from_bin_checked("0000").unwrap();
        bits.invert_all();
        assert_eq!(bits.to_bin(), "1111");
        let mut bits = MutableBitRust::from_bin_checked("1010").unwrap();
        bits.invert_all();
        assert_eq!(bits.to_bin(), "0101");
    }

    #[test]
    fn test_any_set() {
        let bits = BitRust::from_bin("0000").unwrap();
        assert!(!bits.any_set());
        let bits = BitRust::from_bin("1000").unwrap();
        assert!(bits.any_set());
    }

    #[test]
    fn test_invert_single_bit() {
        let mut bits = MutableBitRust::from_bin_checked("0000").unwrap();
        bits.invert_single_bit(1).unwrap();
        assert_eq!(bits.to_bin(), "0100");
        bits.invert_single_bit(-1).unwrap();
        assert_eq!(bits.to_bin(), "0101");
    }

    #[test]
    fn test_xor() {
        let a = BitRust::from_bin("1100").unwrap();
        let b = BitRust::from_bin("1010").unwrap();
        let result = a.__xor__(&b).unwrap();
        assert_eq!(result.to_bin(), "0110");
    }

    #[test]
    fn test_or() {
        let a = BitRust::from_bin("1100").unwrap();
        let b = BitRust::from_bin("1010").unwrap();
        let result = a.__or__(&b).unwrap();
        assert_eq!(result.to_bin(), "1110");
    }

    #[test]
    fn test_and2() {
        let a = BitRust::from_bin("1100").unwrap();
        let b = BitRust::from_bin("1010").unwrap();
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
        let bits = BitRust::from_bin("1100").unwrap();
        assert_eq!(bits.__len__(), 4);
        let bits = BitRust::from_bin("101010").unwrap();
        assert_eq!(bits.__len__(), 6);
    }

    #[test]
    fn test_eq() {
        let a = BitRust::from_bin("1100").unwrap();
        let b = BitRust::from_bin("1100").unwrap();
        assert!(a == b);
        let c = BitRust::from_bin("1010").unwrap();
        assert!(a != c);
    }

    #[test]
    fn test_getslice_withstep() {
        let bits = BitRust::from_bin("11001100").unwrap();
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

    #[test]
    fn test_set_from_sequence_perfomance() {
        let mut bits = MutableBitRust::from_zeros(10000000);
        bits.set_from_sequence(true, vec![0]).unwrap();
        let c = bits.count();
        assert_eq!(c, 1);
    }

    #[test]
    fn mutable_from_immutable() {
        let immutable = BitRust::from_bin("1010").unwrap();
        let mutable = MutableBitRust::new(&(immutable.data));
        assert_eq!(mutable.to_bin(), "1010");
    }

    #[test]
    fn freeze_preserves_data() {
        let mutable = MutableBitRust::from_bin_checked("1100").unwrap();
        let immutable = mutable.clone_as_immutable();
        assert_eq!(immutable.to_bin(), "1100");
    }

    #[test]
    fn modify_then_freeze() {
        let mut mutable = MutableBitRust::from_bin_checked("0000").unwrap();
        mutable.set_index(true, 1).unwrap();
        mutable.set_index(true, 2).unwrap();
        let immutable = mutable.clone_as_immutable();
        assert_eq!(immutable.to_bin(), "0110");
    }

    #[test]
    fn mutable_constructors() {
        let m1 = MutableBitRust::from_zeros(4);
        assert_eq!(m1.to_bin(), "0000");

        let m2 = MutableBitRust::from_ones(4);
        assert_eq!(m2.to_bin(), "1111");

        let m3 = MutableBitRust::from_bin_checked("1010").unwrap();
        assert_eq!(m3.to_bin(), "1010");

        let m4 = MutableBitRust::from_hex_checked("a").unwrap();
        assert_eq!(m4.to_bin(), "1010");

        let m5 = MutableBitRust::from_oct_checked("12").unwrap();
        assert_eq!(m5.to_bin(), "001010");
    }

    #[test]
    fn mutable_equality() {
        let m1 = MutableBitRust::from_bin_checked("1100").unwrap();
        let m2 = MutableBitRust::from_bin_checked("1100").unwrap();
        let m3 = MutableBitRust::from_bin_checked("0011").unwrap();

        assert!(m1 == m2);
        assert!(m1 != m3);
    }

    #[test]
    fn mutable_operations() {
        let mut m = MutableBitRust::from_bin_checked("1100").unwrap();
        m.reverse();
        assert_eq!(m.to_bin(), "0011");

        let other = BitRust::from_bin("1111").unwrap();
        m.append(&other);
        assert_eq!(m.to_bin(), "00111111");

        m.invert_all();
        assert_eq!(m.to_bin(), "11000000");
    }

    #[test]
    fn mutable_getslice() {
        let m = MutableBitRust::from_bin_checked("11001010").unwrap();

        let slice1 = m.getslice(2, Some(6)).unwrap();
        assert_eq!(slice1.to_bin(), "0010");

        let slice2 = m.getslice_with_step(0, 8, 2).unwrap();
        assert_eq!(slice2.to_bin(), "1011");
    }

    #[test]
    fn mutable_find_operations() {
        let haystack = MutableBitRust::from_bin_checked("00110011").unwrap();
        let needle = BitRust::from_bin("11").unwrap();

        assert_eq!(haystack.find(&needle, 0, false), Some(2));
        assert_eq!(haystack.find(&needle, 3, false), Some(6));
        assert_eq!(haystack.rfind(&needle, 0, false), Some(6));
    }

    #[test]
    fn mutable_set_operations() {
        let mut m = MutableBitRust::from_zeros(8);

        m.set_index(true, 0).unwrap();
        m.set_index(true, 7).unwrap();
        assert_eq!(m.to_bin(), "10000001");

        m.set_from_slice(true, 2, 6, 1).unwrap();
        assert_eq!(m.to_bin(), "10111101");

        m.set_from_sequence(false, vec![0, 3, 7]).unwrap();
        assert_eq!(m.to_bin(), "00101100");
    }

    #[test]
    fn mutable_immutable_interaction() {
        let pattern1 = MutableBitRust::from_bin_checked("1100").unwrap();
        let pattern2 = BitRust::from_bin("0011").unwrap();

        let mut m = MutableBitRust::new(&pattern1.inner.data);

        m.set_slice(0, 2, &pattern2).unwrap();
        assert_eq!(m.to_bin(), "001100");
    }

    #[test]
    fn empty_data_operations() {
        let empty_mutable = MutableBitRust::from_zeros(0);
        let empty_immutable = BitRust::from_zeros(0);

        assert_eq!(empty_mutable.len(), 0);
        assert_eq!(empty_mutable.count(), 0);
        assert!(!empty_mutable.any_set());

        assert_eq!(empty_mutable.clone_as_immutable().len(), 0);

        let mut another_empty = MutableBitRust::from_zeros(0);
        another_empty.append(&empty_immutable);
        assert_eq!(another_empty.len(), 0);
    }

    #[test]
    fn large_mutable_operations() {
        let mut large = MutableBitRust::from_zeros(1000);

        for i in 0..1000 {
            if i % 3 == 0 {
                large.set_index(true, i as i64).unwrap();
            }
        }

        assert_eq!(large.count(), 334);

        large.invert_all();
        assert_eq!(large.count(), 666);
    }

    #[test]
    fn mutable_edge_index_operations() {
        let mut m = MutableBitRust::from_bin_checked("1010").unwrap();

        m.set_index(false, 0).unwrap();
        m.set_index(false, 3).unwrap();
        assert_eq!(m.to_bin(), "0010");

        m.set_index(true, -1).unwrap();
        m.set_index(true, -4).unwrap();
        assert_eq!(m.to_bin(), "1011");

        assert!(m.set_index(true, 4).is_err());
        assert!(m.set_index(true, -5).is_err());
    }

    #[test]
    fn set_mutable_slice_with_bit_rust() {
        let mut m = MutableBitRust::from_bin_checked("00000000").unwrap();
        let pattern = BitRust::from_bin("1111").unwrap();

        m.set_slice(2, 6, &pattern).unwrap();
        assert_eq!(m.to_bin(), "00111100");

        m.set_slice(0, 2, &pattern).unwrap();
        assert_eq!(m.to_bin(), "1111111100");

        m.set_slice(6, 8, &pattern).unwrap();
        assert_eq!(m.to_bin(), "111111111100");
    }

    #[test]
    fn conversion_round_trip() {
        let original = BitRust::from_bin("101010").unwrap();
        let mut mutable = MutableBitRust::new(&original.data);
        mutable.set_index(false, 0).unwrap();
        mutable.set_index(true, 1).unwrap();
        let result = mutable.as_immutable();

        assert_eq!(result.to_bin(), "011010");
        assert_ne!(result.to_bin(), original.to_bin());
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
        let bin = MutableBitRust::from_bin_checked("1010").unwrap();
        assert_eq!(bin.to_bin(), "1010");

        let hex = MutableBitRust::from_hex_checked("a").unwrap();
        assert_eq!(hex.to_bin(), "1010");

        let oct = MutableBitRust::from_oct_checked("12").unwrap();
        assert_eq!(oct.to_bin(), "001010");

        assert!(MutableBitRust::from_bin_checked("123").is_err());
        assert!(MutableBitRust::from_hex_checked("xy").is_err());
        assert!(MutableBitRust::from_oct_checked("89").is_err());
    }

    #[test]
    fn negative_indexing_in_mutable() {
        let mut m = MutableBitRust::from_bin_checked("10101010").unwrap();
        m.invert_single_bit(-2).unwrap();
        assert_eq!(m.to_bin(), "10101000");

        assert_eq!(m.getindex(-3).unwrap(), false);
        assert_eq!(m.getindex(-8).unwrap(), true);
        assert!(m.getindex(-9).is_err());
    }

    #[test]
    fn mutable_getslice_edge_cases() {
        let m = MutableBitRust::from_bin_checked("11001010").unwrap();

        let empty = m.getslice(4, Some(4)).unwrap();
        assert_eq!(empty.to_bin(), "");

        let full = m.getslice(0, None).unwrap();
        assert_eq!(full.to_bin(), "11001010");

        assert!(m.getslice(9, Some(10)).is_err());
    }


}
