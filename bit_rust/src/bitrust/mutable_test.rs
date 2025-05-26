#[cfg(test)]
mod tests {
    use crate::bitrust::{BitRust, MutableBitRust};

    #[test]
    fn test_set_and_get_index() {
        let mut mb = MutableBitRust::from_zeros(8);
        mb.set_index(true, 3).unwrap();
        assert_eq!(mb.getindex(3).unwrap(), true);
        mb.set_index(false, 3).unwrap();
        assert_eq!(mb.getindex(3).unwrap(), false);
    }

    #[test]
    fn test_invert_all() {
        let mut mb = MutableBitRust::from_zeros(4);
        mb.invert_all();
        assert_eq!(mb.to_bin(), "1111");
    }

    #[test]
    fn test_append_and_prepend() {
        let mut mb = MutableBitRust::from_zeros(2);
        let br = BitRust::from_ones(2);
        mb.append(&br);
        assert_eq!(mb.to_bin(), "0011");
        mb.prepend(&br);
        assert_eq!(mb.to_bin(), "110011");
    }

    #[test]
    fn test_set_slice() {
        let mut mb = MutableBitRust::from_zeros(6);
        let br = BitRust::from_ones(2);
        mb.set_slice(2, 4, &br).unwrap();
        assert_eq!(mb.to_bin(), "001100");
    }

    #[test]
    fn test_overwrite_slice() {
        let mut mb = MutableBitRust::from_zeros(6);
        let br = BitRust::from_ones(2);
        mb.set_slice(2, 4, &br).unwrap();
        assert_eq!(mb.to_bin(), "001100");
    }

    #[test]
    fn test_iand_ior_ixor() {
        let mut mb1 = MutableBitRust::from_ones(4);
        let mb2 = MutableBitRust::from_zeros(4);
        mb1.iand(&mb2).unwrap();
        assert_eq!(mb1.to_bin(), "0000");
        mb1.ior(&MutableBitRust::from_ones(4)).unwrap();
        assert_eq!(mb1.to_bin(), "1111");
        mb1.ixor(&MutableBitRust::from_ones(4)).unwrap();
        assert_eq!(mb1.to_bin(), "0000");
    }

    #[test]
    fn test_reverse() {
        let mut mb = MutableBitRust::from_bin_checked("1010").unwrap();
        mb.reverse();
        assert_eq!(mb.to_bin(), "0101");
    }
}

