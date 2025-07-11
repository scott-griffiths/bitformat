pub mod bitrust;
use pyo3::prelude::*;

#[pymodule]
fn bit_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<bitrust::Bits>()?;
    m.add_class::<bitrust::MutableBits>()?;
    m.add_class::<bitrust::PyBitRustFindAllIterator>()?;
    m.add_function(wrap_pyfunction!(bitrust::split_tokens, m)?)?;
    m.add_function(wrap_pyfunction!(bitrust::string_literal_to_bitrust, m)?)?;
    Ok(())
}