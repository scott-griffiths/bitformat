/// Helper functions.
use super::*;
use bitvec::prelude::*;
use bytemuck::cast_slice;
use pyo3::exceptions::PyIndexError;
use pyo3::PyResult;
use bits::BitCollection;
// The choice of size is interesting. Can choose u8, u16, u32, u64.
// Also can choose Lsb0 or Msb0.
// Not sure of all the performance implications yet.
pub type BV = BitVec<u8, Msb0>;
pub type BS = BitSlice<u8, Msb0>;

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
    if needle.len() == 0 || needle.len() > haystack.len() - start {
        return None;
    }

    let lps = compute_lps(&needle.data);
    let mut i = start; // index for haystack
    let mut j = 0; // index for needle

    while i < haystack.len() {
        // Match current bits
        if needle.data[j] == haystack.data[i] {
            i += 1;
            j += 1;

            // Check if we found a match
            if j == needle.len() {
                return Some(i - j);
            }
        } else if j != 0 {
            // Mismatch after at least one match - use KMP to skip
            j = lps[j - 1];
        } else {
            // Mismatch at first position - move forward
            i += 1;
        }
    }
    None
}

// The same as find_bitvec but only returns matches that are a multiple of 8.
pub fn find_bitvec_bytealigned(
    haystack: &BitRust,
    needle: &BitRust,
    start: usize,
) -> Option<usize> {
    // Early return if needle is empty or longer than haystack
    if needle.len() == 0 || needle.len() > haystack.len() - start {
        return None;
    }

    let lps = compute_lps(&needle.data);
    let mut i = start; // index for haystack
    let mut j = 0; // index for needle

    while i < haystack.len() {
        // Match current bits
        if needle.data[j] == haystack.data[i] {
            i += 1;
            j += 1;

            // Check if we found a match
            if j == needle.len() {
                let match_position = i - j;
                if match_position % 8 == 0 {
                    return Some(match_position);
                }
                // Not byte-aligned, continue searching
                j = lps[j - 1];
            }
        } else if j != 0 {
            // Mismatch after at least one match - use KMP to skip
            j = lps[j - 1];
        } else {
            // Mismatch at first position - move forward
            i += 1;
        }
    }
    None
}

pub fn convert_bitrust_to_bytes(bits: &BitRust) -> Vec<u8> {
    // This only works because BV = BitVec<u8, Msb0>. If we use a wider base this needs a fix.
    let mut bytes = cast_slice(bits.data.as_raw_slice()).to_vec();
    let byte_len = bytes.len();
    if bits.len() % 8 != 0 {
        let mask = 0xff << (8 - (bits.len() % 8));
        bytes[byte_len- 1] &= mask;
    }
    bytes
}

pub fn validate_index(index: i64, length: usize) -> PyResult<usize> {
    let index = if index < 0 {
        length as i64 + index
    } else {
        index
    };
    if index >= length as i64 || index < 0 {
        return Err(PyIndexError::new_err("Out of range."));
    }
    Ok(index as usize)
}