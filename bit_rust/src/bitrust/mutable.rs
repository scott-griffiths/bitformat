use crate::bitrust::{bits, helpers};
use crate::bitrust::BitRust;
use pyo3::exceptions::{PyIndexError, PyValueError};
use pyo3::{pyclass, pymethods, PyObject, PyRef, PyResult, Python};
use crate::bitrust::BitRustIterator;
use std::ops::Not;
use bits::BitCollection;

#[pyclass(eq)]
pub struct MutableBitRust {
    pub(crate) inner: BitRust,
}

impl BitCollection for MutableBitRust {
    fn len(&self) -> usize {
        self.inner.len()
    }
    fn from_zeros(length: usize) -> Self {
        Self { inner: <BitRust as BitCollection>::from_zeros(length) }
    }
    fn from_ones(length: usize) -> Self {
        Self { inner: <BitRust as BitCollection>::from_ones(length) }
    }
    fn from_bytes(data: Vec<u8>) -> Self {
        Self { inner: <BitRust as BitCollection>::from_bytes(data) }
    }
    fn from_bin(binary_string: &str) -> Result<Self, String> {
        Ok(Self { inner: <BitRust as BitCollection>::from_bin(binary_string)? })
    }
    fn from_oct(oct: &str) -> Result<Self, String> {
        Ok(Self { inner: <BitRust as BitCollection>::from_oct(oct)? })
    }
    fn from_hex(hex: &str) -> Result<Self, String> {
        Ok(Self { inner: <BitRust as BitCollection>::from_hex(hex)? })
    }
    fn from_u64(value: u64, length: usize) -> Self {
        Self { inner: <BitRust as BitCollection>::from_u64(value, length) }
    }
    fn from_i64(value: i64, length: usize) -> Self {
        Self { inner: <BitRust as BitCollection>::from_i64(value, length) }
    }
}

impl PartialEq for MutableBitRust {
    fn eq(&self, other: &Self) -> bool {
        self.inner.data == other.inner.data
    }
}

impl PartialEq<BitRust> for MutableBitRust {
    fn eq(&self, other: &BitRust) -> bool {
        self.inner.data == other.data
    }
}

impl MutableBitRust {
    pub fn new(bv: &helpers::BV) -> Self {
        Self { inner: BitRust::new(bv.clone()) }
    }
}

#[pymethods]
impl MutableBitRust {

    pub fn set_slice(&mut self, start: usize, end: usize, value: &BitRust) -> PyResult<()> {
        if end - start == value.len() {
            // This is an overwrite, so no need to move data around.
            if start + value.len() > self.len() {
                return Err(PyIndexError::new_err("Slice out of bounds"));
            }
            self.inner.data[start..start + value.len()].copy_from_bitslice(&value.data);
            return Ok(());
        }
        let start_slice = self.getslice(0, Some(start))?.inner.data;
        let value_slice = value.data.clone();
        let end_slice = self.getslice(end, Some(self.len()))?.inner.data;

        let mut new_data = start_slice;
        new_data.extend(&value_slice);
        new_data.extend(&end_slice);

        self.inner.data = new_data;
        Ok(())
    }

    pub fn ixor(&mut self, other: &MutableBitRust) -> PyResult<()> {
        if self.len() != other.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }

        self.inner.data ^= &other.inner.data;
        Ok(())
    }

    pub fn ior(&mut self, other: &MutableBitRust) -> PyResult<()> {
        if self.len() != other.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }

        self.inner.data |= &other.inner.data;
        Ok(())
    }

    pub fn iand(&mut self, other: &MutableBitRust) -> PyResult<()> {
        if self.len() != other.len() {
            return Err(PyValueError::new_err("Lengths do not match."));
        }

        self.inner.data &= &other.inner.data;
        Ok(())
    }

    #[staticmethod]
    pub fn from_u64(value: u64, length: usize) -> Self {
        BitCollection::from_u64(value, length)
    }

    #[staticmethod]
    pub fn from_i64(value: i64, length: usize) -> Self {
        BitCollection::from_i64(value, length)
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
    pub fn from_bools(values: Vec<PyObject>, py: Python) -> PyResult<Self> {
        let mut bv = helpers::BV::with_capacity(values.len());

        for value in values {
            let b: bool = value.extract(py)?;
            bv.push(b);
        }
        Ok(Self { inner: BitRust::new(bv)})
    }

    #[staticmethod]
    pub fn from_bytes(data: Vec<u8>) -> Self {
        BitCollection::from_bytes(data)
    }

    #[staticmethod]
    pub fn from_bytes_with_offset(data: Vec<u8>, offset: usize) -> Self {
        Self { inner: BitRust::from_bytes_with_offset(data, offset) }
    }

    #[staticmethod]
    pub fn from_bin_checked(binary_string: &str) -> PyResult<Self> {
        match BitCollection::from_bin(binary_string) {
            Ok(bits) => Ok(bits),
            Err(e) => Err(PyValueError::new_err(e)),
        }
    }

    #[staticmethod]
    pub fn from_hex_checked(hex: &str) -> PyResult<Self> {
        match BitCollection::from_hex(hex) {
            Ok(bits) => Ok(bits),
            Err(e) => Err(PyValueError::new_err(e)),
        }
    }

    #[staticmethod]
    pub fn from_oct_checked(oct: &str) -> PyResult<Self> {
        match BitCollection::from_oct(oct) {
            Ok(bits) => Ok(bits),
            Err(e) => Err(PyValueError::new_err(e)),
        }
    }

    #[staticmethod]
    pub fn join(bits_vec: Vec<PyRef<BitRust>>) -> Self {
        let bitrust_vec: Vec<&BitRust> = bits_vec.iter().map(|x| &**x).collect();
        let total_len: usize = bitrust_vec.iter().map(|b| b.len()).sum();
        let mut bv = helpers::BV::with_capacity(total_len);
        for bits in bitrust_vec {
            bv.extend_from_bitslice(&bits.data);
        }
        MutableBitRust::new(&bv)
    }

    pub fn to_u64(&self) -> u64 {
        self.inner.to_u64()
    }

    pub fn to_i64(&self) -> i64 {
        self.inner.to_i64()
    }

    pub fn __len__(&self) -> usize {
        self.inner.len()
    }

    pub fn getindex(&self, bit_index: i64) -> PyResult<bool> {
        self.inner.getindex(bit_index)
    }

    pub fn getslice(&self, start_bit: usize, end_bit: Option<usize>) -> PyResult<MutableBitRust> {
        self.inner.getslice(start_bit, end_bit).map(|bits| MutableBitRust { inner: bits })
    }

    pub fn getslice_with_step(&self, start_bit: i64, end_bit: i64, step: i64) -> PyResult<MutableBitRust> {
        self.inner.getslice_with_step(start_bit, end_bit, step).map(|bits| MutableBitRust { inner: bits })
    }

    pub fn to_bytes(&self) -> Vec<u8> {
        self.inner.to_bytes()
    }

    pub fn to_hex(&self) -> PyResult<String> {
        self.inner.to_hex()
    }

    pub fn to_bin(&self) -> String {
        self.inner.to_bin()
    }

    pub fn to_oct(&self) -> PyResult<String> {
        self.inner.to_oct()
    }

    pub fn to_int_byte_data(&self, signed: bool) -> Vec<u8> {
        self.inner.to_int_byte_data(signed)
    }

    pub fn count(&self) -> usize {
        self.inner.count()
    }

    pub fn all_set(&self) -> bool {
        self.inner.all_set()
    }

    pub fn any_set(&self) -> bool {
        self.inner.any_set()
    }

    pub fn find(&self, b: &BitRust, start: usize, bytealigned: bool) -> Option<usize> {
        self.inner.find(&b, start, bytealigned)
    }

    pub fn rfind(&self, b: &BitRust, start: usize, bytealigned: bool) -> Option<usize> {
        self.inner.rfind(&b, start, bytealigned)
    }

    #[pyo3(signature = (bs, byte_aligned=false))]
    pub fn findall(&self, bs: &BitRust, byte_aligned: bool) -> PyResult<BitRustIterator> {
        self.inner.findall(&bs, byte_aligned)
    }

    // Return new BitRust with single bit flipped. If pos is None then flip all the bits.
    #[pyo3(signature = (pos=None))]
    pub fn invert(&mut self, pos: Option<usize>) -> Self {
        match pos {
            None => {
                // Invert all bits
                MutableBitRust::new(&self.inner.data.clone().not())
            }
            Some(pos) => {
                // Invert a single bit
                let index = pos;
                let mut data = self.inner.data.clone();
                let old_val = data[index];
                data.set(index, !old_val);
                MutableBitRust::new(&data)
            }
        }
    }

    pub fn invert_bit_list(&mut self, pos_list: Vec<i64>) -> PyResult<()> {
        for pos in pos_list {
            let pos: usize = helpers::validate_index(pos, self.len())?;
            let value = self.inner.data[pos];
            self.inner.data.set(pos, !value);
        }
        Ok(())
    }

    pub fn invert_single_bit(&mut self, pos: i64) -> PyResult<()> {
        let pos: usize = helpers::validate_index(pos, self.len())?;
        let mut new_data = self.inner.data.clone();
        let bv = &mut new_data;
        let value = bv[pos];
        self.inner.data.set(pos, !value);
        Ok(())
    }

    pub fn invert_all(&mut self) {
        self.inner.data = self.inner.data.clone().not();
    }

    pub fn set_from_sequence(&mut self, value: bool, indices: Vec<i64>) -> PyResult<()> {
        for idx in indices {
            let pos: usize = helpers::validate_index(idx, self.inner.len())?;
            self.inner.data.set(pos, value);
        }
        Ok(())
    }

    pub fn set_index(&mut self, value: bool, index: i64) -> PyResult<()> {
        self.set_from_sequence(value, vec![index])
    }

    pub fn set_from_slice(&mut self, value: bool, start: i64, stop: i64, step: i64) -> PyResult<()> {
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

    /// Return a copy with a real copy of the data.
    pub fn clone(&self) -> MutableBitRust {
        MutableBitRust::new(&self.inner.data.clone())
    }

    // Convert to immutable BitRust - cloning the data.
    pub fn clone_as_immutable(&self) -> BitRust {
        BitRust::new(self.inner.data.clone())
    }

    /// Convert to immutable BitRust - without cloning the data.
    pub fn as_immutable(&mut self) -> BitRust {
        let data = std::mem::take(&mut self.inner.data);

        // let empty_data = helpers::BV::new();
        // let data = std::mem::replace(&mut self.inner.data, empty_data);
        BitRust::new(data)
    }

    /// Reverses all bits in place.
    pub fn reverse(&mut self) {
        self.inner.data.reverse();
    }

    /// Append in-place
    pub fn append(&mut self, other: &BitRust) {
        self.inner.data.extend(&other.data);
    }

    /// Prepend in-place
    pub fn prepend(&mut self, other: &BitRust) {
        let mut new_data = other.data.clone();
        new_data.extend(&self.inner.data);
        self.inner.data = new_data;
    }

}
