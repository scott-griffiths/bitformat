/// Helper functions.
use crate::bits::Bits;
use crate::core::BitCollection;
use bitvec::prelude::*;
use pyo3::exceptions::{PyIndexError, PyValueError};
use pyo3::PyResult;
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

pub(crate) fn find_bitvec(
    haystack: &Bits,
    needle: &Bits,
    start: usize,
    byte_aligned: bool,
) -> Option<usize> {
    if byte_aligned {
        find_bitvec_impl::<true>(haystack, needle, start)
    } else {
        find_bitvec_impl::<false>(haystack, needle, start)
    }
}

#[inline]
fn find_bitvec_impl<const BYTE_ALIGNED: bool>(
    haystack: &Bits,
    needle: &Bits,
    start: usize,
) -> Option<usize> {
    if needle.len() == 0 || needle.len() > haystack.len() - start {
        return None;
    }

    let lps = compute_lps(&needle.data);
    let needle_len = needle.len();
    let mut i = start;
    let mut j = 0;

    while i < haystack.len() {
        if needle.data[j] == haystack.data[i] {
            i += 1;
            j += 1;

            if j == needle_len {
                let match_pos = i - j;
                if !BYTE_ALIGNED || (match_pos & 7) == 0 {
                    return Some(match_pos);
                }
                // Continue searching for a byte-aligned match
                j = lps[j - 1];
            }
        } else if j != 0 {
            j = lps[j - 1];
        } else {
            i += 1;
        }
    }
    None
}

pub(crate) fn validate_index(index: i64, length: usize) -> PyResult<usize> {
    let index_p = if index < 0 {
        length as i64 + index
    } else {
        index
    };
    if index_p >= length as i64 || index_p < 0 {
        return Err(PyIndexError::new_err(format!(
            "Index of {index} is out of range for length of {length}"
        )));
    }
    Ok(index_p as usize)
}

pub(crate) fn validate_slice(
    length: usize,
    start: Option<i64>,
    end: Option<i64>,
) -> PyResult<(usize, usize)> {
    let mut start = start.unwrap_or(0);
    let mut end = end.unwrap_or(length as i64);
    if start < 0 {
        start += length as i64;
    }
    if end < 0 {
        end += length as i64;
    }

    if !(0 <= start && start <= end && end <= length as i64) {
        return Err(PyValueError::new_err(format!(
            "Invalid slice positions for MutableBits of length {length}: start={start}, end={end}."
        )));
    }
    Ok((start as usize, end as usize))
}
