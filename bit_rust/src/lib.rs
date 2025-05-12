pub mod bitrust;
use pyo3::prelude::*;

#[pymodule]
fn bit_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<bitrust::BitRust>()?;
    m.add_class::<bitrust::MutableBitRust>()?;
    Ok(())
}