pub mod bitrust;
use pyo3::prelude::*;

#[pymodule]
fn bit_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<bitrust::Bits>()?;
    m.add_class::<bitrust::MutableBits>()?;
    m.add_class::<bitrust::PyBitsFindAllIterator>()?;

    m.add_function(wrap_pyfunction!(bitrust::str_to_bits_rust, m)?)?;
    m.add_function(wrap_pyfunction!(bitrust::set_dtype_parser, m)?)?;
    m.add_function(wrap_pyfunction!(bitrust::bits_from_any, m)?)?;
    m.add_function(wrap_pyfunction!(bitrust::mutable_bits_from_any, m)?)?;
    Ok(())
}
