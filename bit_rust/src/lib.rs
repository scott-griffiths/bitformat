pub mod bitrust;
use pyo3::prelude::*;

#[pymodule]
fn bit_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<bitrust::Bits>()?;
    m.add_class::<bitrust::MutableBits>()?;
    m.add_class::<bitrust::PyBitsFindAllIterator>()?;
    Ok(())
}
