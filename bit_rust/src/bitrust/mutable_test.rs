#[cfg(test)]
mod tests {
    use crate::bitrust::bits::BitCollection;
    use crate::bitrust::{Bits, MutableBits};

    #[test]
    fn test_set_and_get_index() {
        let mut mb = <MutableBits as BitCollection>::from_zeros(8);
        mb._set_index(true, 3).unwrap();
        assert_eq!(mb._getindex(3).unwrap(), true);
        mb._set_index(false, 3).unwrap();
        assert_eq!(mb._getindex(3).unwrap(), false);
    }

    #[test]
    fn test_set_slice() {
        let mut mb = <MutableBits as BitCollection>::from_zeros(6);
        let br = <Bits as BitCollection>::from_ones(2);
        mb._set_slice(2, 4, &br).unwrap();
        assert_eq!(mb.to_bin(), "001100");
    }

    #[test]
    fn test_overwrite_slice() {
        let mut mb = <MutableBits as BitCollection>::from_zeros(6);
        let br = <Bits as BitCollection>::from_ones(2);
        mb._set_slice(2, 4, &br).unwrap();
        assert_eq!(mb.to_bin(), "001100");
    }

    #[test]
    fn test_iand_ior_ixor() {
        let mut mb1 = <MutableBits as BitCollection>::from_ones(4);
        let mb2 = <MutableBits as BitCollection>::from_zeros(4);
        mb1._iand(&mb2).unwrap();
        assert_eq!(mb1.to_bin(), "0000");
        mb1._ior(&<MutableBits as BitCollection>::from_ones(4))
            .unwrap();
        assert_eq!(mb1.to_bin(), "1111");
        mb1._ixor(&<MutableBits as BitCollection>::from_ones(4))
            .unwrap();
        assert_eq!(mb1.to_bin(), "0000");
    }
}
