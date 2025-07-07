pub mod bitrust;
use pyo3::prelude::*;

#[pymodule]
fn bit_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<bitrust::BitRust>()?;
    m.add_class::<bitrust::MutableBitRust>()?;
    m.add_class::<bitrust::PyBitRustFindAllIterator>()?;
    m.add_function(wrap_pyfunction!(bitrust::split_tokens, m)?)?;
    Ok(())
}