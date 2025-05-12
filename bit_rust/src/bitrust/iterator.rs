use crate::bitrust::BitRust;
use pyo3::prelude::*;
use pyo3::PyResult;


#[pyclass]
pub struct BitRustIterator {
    pub(crate) positions: Vec<usize>,
    pub(crate) index: usize,
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
pub struct BitRustBoolIterator {
    pub(crate) bits: Py<BitRust>,
    pub(crate) index: usize,
    pub(crate) length: usize,
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
