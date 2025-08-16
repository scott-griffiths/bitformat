use crate::bitrust::bits::BitCollection;
use crate::bitrust::{helpers, Bits};
use pyo3::prelude::*;
use pyo3::PyResult;

#[pyclass]
pub struct BitsBoolIterator {
    pub(crate) bits: Py<Bits>,
    pub(crate) index: usize,
    pub(crate) length: usize,
}

#[pymethods]
impl BitsBoolIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(&mut self, py: Python<'_>) -> PyResult<Option<bool>> {
        if self.index < self.length {
            let bits = self.bits.borrow(py);
            let result = bits._getindex(self.index as i64);
            self.index += 1;
            result.map(Some)
        } else {
            Ok(None)
        }
    }
}

#[pyclass(name = "BitsFindAllIterator")]
pub struct BitsFindAllIterator {
    pub haystack: Py<Bits>, // Py<T> keeps the Python object alive
    pub needle: Py<Bits>,
    pub current_pos: usize,
    pub byte_aligned: bool,
    pub step: usize,
}

#[pymethods]
impl BitsFindAllIterator {
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

#[pyclass]
pub struct ChunksIterator {
    pub(crate) bits_object: Py<Bits>,
    pub(crate) chunk_size: usize,
    pub(crate) max_chunks: usize,
    pub(crate) current_pos: usize,
    pub(crate) chunks_generated: usize,
}

#[pymethods]
impl ChunksIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<'_, Self>) -> PyResult<Option<Bits>> {
        // Early exit conditions
        if slf.chunks_generated >= slf.max_chunks {
            return Ok(None);
        }

        let py = slf.py();

        // Create chunk data and get chunk length in a scope to limit the borrow
        let (chunk, chunk_len) = {
            let bits = slf.bits_object.borrow(py);
            let bits_len = bits.len();

            // Early return if we've reached the end
            if slf.current_pos >= bits_len {
                return Ok(None);
            }

            // Get a chunk directly using bitvec's chunks method
            if let Some(chunk_slice) = bits.data[slf.current_pos..].chunks(slf.chunk_size).next() {
                let chunk_len = chunk_slice.len();
                (Bits::new(chunk_slice.to_bitvec()), chunk_len)
            } else {
                // This should not happen given our check above, but just in case
                return Ok(None);
            }
        };

        // Now we can safely update the position after the borrow is dropped
        slf.current_pos += chunk_len;
        slf.chunks_generated += 1;

        Ok(Some(chunk))
    }
}
