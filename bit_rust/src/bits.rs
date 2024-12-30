use std::fmt;
use std::ops::Not;
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

// The same as find_bitvec but only returns matches that are a multiple of 8.
pub fn find_bitvec_bytealigned(s: &BitVec<u8, Msb0>, pattern: &BitVec<u8, Msb0>, start: usize) -> Option<usize> {
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
            if match_position % 8 == 0 {
                return Some(match_position);
            } else {
                j = lps[j - 1];
            }
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
    bv: BitVec<u8, Msb0>,
}


impl fmt::Debug for BitRust {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.bv.len() > 100 {
            return f.debug_struct("Bits")
                .field("hex", &self.slice(0, 100).to_hex().unwrap())
                .field("length", &self.bv.len())
                .finish();
        }
        if self.bv.len() % 4 == 0 {
            return f.debug_struct("Bits")
                .field("hex", &self.to_hex().unwrap())
                .field("length", &self.bv.len())
                .finish();
        }
        f.debug_struct("Bits")
            .field("bin", &self.to_bin())
            .field("length", &self.bv.len())
            .finish()
    }
}

impl Clone for BitRust {
    fn clone(&self) -> Self {
        BitRust {
            bv: self.bv.clone(),
        }
    }
}

impl PartialEq for BitRust {
    fn eq(&self, other: &Self) -> bool {
        self.bv == other.bv
    }
}

// Things not part of the Python interface.
impl BitRust {

    fn join_internal(bits_vec: &Vec<&BitRust>) -> Self {
        if bits_vec.is_empty() {
            return BitRust::from_zeros(0);
        }
        let mut bv = BitVec::new();
        for bits in bits_vec {
            bv.extend(bits.bv.clone());
        }
        BitRust {
            bv,
        }
    }
    
    /// Slice used internally without bounds checking.
    fn slice(&self, start_bit: usize, end_bit: usize) -> Self {
        BitRust {
            bv: self.bv[start_bit..end_bit].to_owned(),
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
}

#[pymethods]
impl BitRust {

    // A stop-gap. We really want to return an iterator of i64.
    pub fn findall_list(&self, b: &BitRust, bytealigned: bool) -> Vec<usize>  {
        let pos: Vec<usize> = self.find_all_rust(b, bytealigned).collect();
        pos
    }

    pub fn __len__(&self) -> usize {
        self.bv.len()
    }

    pub fn __eq__(&self, rhs: &BitRust) -> bool {
        self == rhs
    }

    #[staticmethod]
    pub fn from_zeros(length: usize) -> Self {
        BitRust {
            bv: BitVec::repeat(false, length),
        }
    }

    #[staticmethod]
    pub fn from_ones(length: usize) -> Self {
        BitRust {
            bv: BitVec::repeat(true, length),
        }
    }

    #[staticmethod]
    pub fn from_bytes(data: Vec<u8>) -> Self {
        BitRust {
            bv: BitVec::from_vec(data),
        }
    }

    #[staticmethod]
    pub fn from_bytes_with_offset(data: Vec<u8>, offset: usize) -> Self {
        assert!(offset < 8);
        let mut bv = BitVec::from_vec(data);
        bv.drain(..offset);
        BitRust {
            bv,
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
        Ok(BitRust {
            bv: b,
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
        let mut bv = BitVec::from_vec(data.clone());
        if is_odd_length {
            bv.drain(bv.len() - 4..bv.len());
        }
        Ok(BitRust {
            bv,
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
        // let mut bv = self.bv.clone();
        // bv.set_uninitialized(false);
        // bv.into_vec()

        // This is to get around the problem if there are unused bits at the start of the BitVec
        // Obviously not very optimal!
        let num_bytes = (self.bv.len() + 7) / 8;
        let mut bytes = vec![0u8; num_bytes];
        for (i, bit) in self.bv.iter().enumerate() {
            if *bit {
                bytes[i / 8] |= 1 << (7 - (i % 8));
            }
        }
        bytes
    }

    // Return bytes that can easily be converted to an int in Python
    pub fn to_int_byte_data(&self, signed: bool) -> Vec<u8> {
        // Want the offset to make there be no padding.
        let mut new_offset = 8 - self.bv.len() % 8;
        if new_offset == 8 {
            new_offset = 0;
        }
        debug_assert!((new_offset + self.bv.len()) % 8 == 0);
        let pad_with_ones = signed && self.bv.len() > 0 && self.bv[0];
        let mut t: BitVec<u8, Msb0> = BitVec::repeat(pad_with_ones, new_offset);
        t.extend(self.bv.clone());
        debug_assert_eq!(t.len() % 8, 0);
        debug_assert_eq!(t.len(), 8 * ((self.bv.len() + 7) / 8));
        t.into_vec()
    }

    pub fn to_hex(&self) -> PyResult<String> {
        if self.bv.len() % 4 != 0 {
            return Err(PyValueError::new_err("Not a multiple of 4 bits long."));
        }
        let bytes = self.bv.clone().into_vec();
        let hex_string = bytes.iter().map(|byte| format!("{:02x}", byte)).collect::<String>();
        if self.bv.len() % 8 == 0 {
            return Ok(hex_string);
        }
        // If the length is not a multiple of 8, we need to trim the padding bits
        Ok(hex_string[1..hex_string.len()].to_string())

    }

    pub fn to_bin(&self) -> String {
        self.bv.iter().map(|x| if *x { '1' } else { '0' }).collect::<String>()
    }

    pub fn to_oct(&self) -> PyResult<String> {
        if self.bv.len() % 3 != 0 {
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
        if self.bv.len() != other.bv.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }
        let bv = self.bv.clone() & other.clone().bv;
        Ok(BitRust {
            bv,
        })
    }
    pub fn __or__(&self, other: &BitRust) -> PyResult<BitRust> {
        if self.bv.len() != other.bv.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }
        let bv = self.bv.clone() | other.clone().bv;
        Ok(BitRust {
            bv,
        })
    }
    pub fn __xor__(&self, other: &BitRust) -> PyResult<BitRust> {
        if self.bv.len() != other.bv.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }
        let bv = self.bv.clone() ^ other.clone().bv;
        Ok(BitRust {
            bv,
        })
    }

    pub fn find(&self, b: &BitRust, start: usize, bytealigned: bool) -> Option<usize> {
        if bytealigned {
            find_bitvec_bytealigned(&self.bv, &b.bv, start)
        } else {
            find_bitvec(&self.bv, &b.bv, start)
        }
    }
    
    pub fn rfind(&self, b: &BitRust, start: usize, bytealigned: bool) -> Option<usize> {
        if b.bv.len() + start > self.bv.len() {
            return None;
        }
        let step = if bytealigned { 8 } else { 1 };
        let mut pos = self.bv.len() - b.bv.len();
        if bytealigned {
            pos = pos / 8 * 8;
        }
        while pos >= start + step {
            if self.slice(pos, pos + b.bv.len()) == *b {
                return Some(pos - start);
            }
            pos -= step;
        }
        None
    }

    pub fn count(&self) -> usize {
        if self.bv.len() == 0 {
            return 0;
        }
        self.bv.count_ones()

        // The version below is about 15x faster on the count benchmark.
        // I'm presuming that all the time is being spent in the conversion to the bitvec
        // so it will speed up a lot when BitVec is used as the storage.

        // let offset = self.offset % 8;
        // let padding = if (self.length + offset) % 8 == 0 { 0 } else { 8 - (self.length + offset) % 8 };
        // // Case where there's only one byte of used data.
        // if self.start_byte() + 1 == self.end_byte() {
        //     return ((self.data[self.start_byte()] << offset) >> (offset + padding)).count_ones() as usize;
        // }
        // let mut c = hamming::weight(&self.data[self.start_byte()..self.end_byte()]) as usize;
        // // Subtract any bits in the offset or padding.
        // if offset != 0 {
        //     c -= (self.data[self.start_byte()] >> (8 - offset)).count_ones() as usize;
        // }
        // if padding != 0 {
        //     c -= (self.data[self.end_byte() - 1] << (8 -padding)).count_ones() as usize;
        // }
        // c
    }

    /// Returns a new BitRust with all bits reversed.
    pub fn reverse(&self) -> Self {
        let mut bv = self.bv.clone();
        bv.reverse();
        BitRust {
            bv,
        }
    }

    /// Returns the bool value at a given bit index.
    pub fn getindex(&self, mut bit_index: i64) -> PyResult<bool> {
        let length = self.bv.len();
        if bit_index >= length as i64 || bit_index < -(length as i64) {
            return Err(PyIndexError::new_err("Out of range."));
        }
        if bit_index < 0 {
            bit_index += length as i64;
        }
        debug_assert!(bit_index >= 0);
        let p = bit_index as usize;
        Ok(self.bv[p])
    }

    /// Returns the length of the Bits object in bits.
    pub fn length(&self) -> usize {
        self.bv.len()
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
        let end_bit = end_bit.unwrap_or(self.bv.len());
        if start_bit >= end_bit {
            return Ok(BitRust::from_zeros(0));
        }
        assert!(start_bit < end_bit);
        if end_bit > self.bv.len() {
            return Err(PyValueError::new_err("end bit goes past the end"));
        }
        Ok(BitRust {
            bv: self.bv[start_bit..end_bit].to_owned(),
        })
    }

    // Return new BitRust with single bit flipped. If pos is None then flip all the bits.
    #[pyo3(signature = (pos=None))]
    pub fn invert(&self, pos: Option<usize>) -> Self {
        let mut bv = self.bv.clone();
        match pos {
            None => {
                // Invert every bit
                bv = bv.not();
            }
            Some(pos) => {
                // Just invert the bit at pos
                let value = bv[pos]; // TODO handle error ?
                bv.set(pos, value);
            }
        }
        BitRust {
            bv,
        }
    }

    /// Returns true if all of the bits are set to 1.
    pub fn all_set(&self) -> bool {
        self.count() == self.bv.len()
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
        let mut bv = self.bv.clone();
        let mut positive_indices: Vec<usize> = vec![];
        for index in indices {
            if -index > self.bv.len() as i64 {
                return Err(PyIndexError::new_err("Negative index past the end"));
            }
            if index >= self.bv.len() as i64 {
                return Err(PyIndexError::new_err("Index out of range."))
            }
            positive_indices.push(if index < 0 { (self.bv.len() as i64 + index) as usize } else { index as usize});
        }
        for index in positive_indices {
            bv.set(index, value);
        }
        Ok(BitRust {
            bv,
        })
    }

    pub fn set_from_slice(&self, value: bool, start: i64, stop: i64, step: i64) -> PyResult<Self> {
        let mut bv: BitVec<u8, Msb0> = self.bv.clone();
        let positive_start = if start < 0 { start + self.bv.len() as i64 } else { start };
        let positive_stop = if stop < 0 { stop + self.bv.len() as i64 } else { stop };
        if positive_start < 0 || positive_start >= self.bv.len() as i64 {
            return Err(PyIndexError::new_err("Start of slice out of bounds."));
        }
        if positive_stop < 0 || positive_start >= self.bv.len() as i64 {
            return Err(PyIndexError::new_err("End of slice out of bounds."));
        }
        for index in (positive_start..positive_stop).step_by(step as usize) {
            bv.set(index as usize, value);
        }
        Ok(BitRust {
            bv,
        })
    }

    /// Return a copy with a real copy of the data.
    pub fn get_mutable_copy(&self) -> Self {
        BitRust {
            bv: self.bv.clone(),
        }
    }

    pub fn set_mutable_slice(&mut self, start: usize, end: usize, value: &BitRust) -> PyResult<()> {
        let start_slice = self.getslice(0, Some(start))?;
        let end_slice = self.getslice(end, Some(self.bv.len()))?;
        let joined = BitRust::join_internal(&vec![&start_slice, value, &end_slice]);
        *self = joined;
        Ok(())
    }

    pub fn data(&self) -> Vec<u8> {
        self.bv.clone().into_vec()
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
    let bits = BitRust::from_hex("0a141e").unwrap();
    assert_eq!(*bits.data(), vec![10, 20, 30]);
    assert_eq!(bits.length(), 24);
    let bits = BitRust::from_hex("").unwrap();
    assert_eq!(bits.length(), 0);
    let bits = BitRust::from_hex("hello");
    assert!(bits.is_err());
    let bits = BitRust::from_hex("1").unwrap();
    assert_eq!(*bits.data(), vec![16]);
    assert_eq!(bits.length(), 4);
}

#[test]
fn from_bin() {
    let bits = BitRust::from_bin("00001010").unwrap();
    assert_eq!(*bits.data(), vec![10]);
    assert_eq!(bits.length(), 8);
    let bits = BitRust::from_bin("").unwrap();
    assert_eq!(bits.length(), 0);
    let bits = BitRust::from_bin("hello");
    assert!(bits.is_err());
    let bits = BitRust::from_bin("1").unwrap();
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
    assert_eq!(b2.length(), 52);
    // assert_eq!(b2.data().len(), 8);

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
    println!("b.bv: {:?}", b.bv);
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
    let b = BitRust::from_hex("103").unwrap();
    assert_eq!(a3, b);
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