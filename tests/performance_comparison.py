# Comparison of performace between bitformat and bitstring.
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import bitstring
import bitformat
import timeit
import random
import math

def test_cutting_bitstring():
    s = bitstring.Bits('0xef1356a6200b3, 0b0')
    s *= 6000
    c = 0
    for triplet in s.cut(3):
        if triplet == '0b001':
            c += 1
    return c

def test_cutting_bitformat():
    s = bitformat.Bits('0xef1356a6200b3, 0b0')
    s *= 6000
    c = 0
    for triplet in s.chunks(3):
        if triplet == '0b001':
            c += 1
    return c

def test_primes_bitstring():
    limit = 10000000
    is_prime = bitstring.BitArray(limit)
    is_prime.set(True)
    # Manually set 0 and 1 to be not prime.
    is_prime.set(False, [0, 1])
    # For every other integer, if it's set as prime then unset all of its multiples
    for i in range(2, math.ceil(math.sqrt(limit))):
        if is_prime[i]:
            is_prime.set(False, range(i * i, limit, i))
    twin_primes = len(list(is_prime.findall('0b101')))
    return twin_primes

def test_primes_bitformat():
    limit = 10000000
    is_prime = bitformat.Bits.from_ones(limit)
    # Manually set 0 and 1 to be not prime.
    is_prime = is_prime.set(False, [0, 1])
    # For every other integer, if it's set as prime then unset all of its multiples
    for i in range(2, math.ceil(math.sqrt(limit))):
        if is_prime[i]:
            is_prime = is_prime.set(False, range(i * i, limit, i))
    twin_primes = len(list(is_prime.find_all('0b101')))
    return twin_primes

def test_token_parsing_bitstring():
    s = bitstring.BitArray()
    for i in range(10000):
        s += 'uint:12=244, float:32=0.4'
        s += '0x3e44f, 0b11011, 0o75523'
        s += [0, 1, 2, 0, 0, 1, 2, 0, -1, 0, 'hello']
        s += bitstring.BitArray(104)

def test_token_parsing_bitformat():
    s = []
    for i in range(10000):
        s.append(bitformat.Bits.from_string('u12=244, f32=0.4'))
        s.append(bitformat.Bits.from_string('0x3e44f, 0b11011, 0o75523'))
        s.append(bitformat.Bits.from_bools([0, 1, 2, 0, 0, 1, 2, 0, -1, 0, 'hello']))
        s.append(bitformat.Bits.from_zeros(104))
    s = bitformat.Bits.from_joined(s)

def test_count_bitstring():
    s = bitstring.BitArray(100000000)
    s.set(1, [10, 100, 1000, 10000000])
    return s.count(1)

def test_count_bitformat():
    s = bitformat.Bits.from_zeros(100000000)
    s = s.set(1, [10, 100, 1000, 10000000])
    return s.count(1)

def test_finding_bitstring():
    random.seed(999)
    i = random.randrange(0, 2 ** 20000000)
    s = bitstring.BitArray(uint=i, length=20000000)
    for ss in ['0b11010010101', '0xabcdef1234, 0b000101111010101010011010100100101010101', '0x4321']:
        x = len(list(s.findall(ss)))
    return x

def test_finding_bitformat():
    random.seed(999)
    i = random.randrange(0, 2 ** 20000000)
    s = bitformat.Bits.from_dtype('u20000000', i)
    for ss in ['0b11010010101', '0xabcdef1234, 0b000101111010101010011010100100101010101', '0x4321']:
        x = len(list(s.find_all(ss)))
    return x

class FunctionPairs:
    def __init__(self, name, bitstring_func, bitformat_func):
        self.name = name
        self.bitstring_func = bitstring_func
        self.bitformat_func = bitformat_func
        self.ratio = 1.0

    def run(self):
        bs_time = timeit.timeit(self.bitstring_func, number=5)
        bf_time = timeit.timeit(self.bitformat_func, number=5)
        self.ratio = bs_time / bf_time

class TestSuite:
    def __init__(self, pairs):
        self.pairs = pairs

    def run(self):
        for pair in self.pairs:
            pair.run()

    def print_results(self):
        for pair in self.pairs:
            if pair.ratio > 1.0:
                extra = ""
            else:
                extra = f"({1/pair.ratio:.2f}⨉ slower)"
            print(f'{pair.kind}: {pair.ratio:.2f}⨉ faster {extra}')
        # For ratios we use a geometric mean
        average = math.prod(r.ratio for r in self.pairs) ** (1 / len(self.pairs))
        print(f"AVERAGE: {average:.2f}⨉ faster")

def main():
    fn_pairs = [
        FunctionPairs("Cutting", test_cutting_bitstring, test_cutting_bitformat),
        FunctionPairs("Primes", test_primes_bitstring, test_primes_bitformat),
        FunctionPairs("Token parsing", test_token_parsing_bitstring, test_token_parsing_bitformat),
        FunctionPairs("Count", test_count_bitstring, test_count_bitformat),
        FunctionPairs("Finding", test_finding_bitstring, test_finding_bitformat),
    ]
    ts = TestSuite(fn_pairs)
    ts.run()
    ts.print_results()


if __name__ == "__main__":
    main()