from construct import *
import sys
sys.path.insert(1, '../')
from bitformat import Format, Bits

d = Struct(
    "count" / Int32ul,
    "num1" / Int8ul,
    "num2" / Int24ul,
)


data = d.build(dict(count=1000, num1=0, num2=0))
with open("blob","wb") as f:
    f.write(data)

from timeit import timeit
d.parse(data)
parsetime = timeit(lambda: d.parse(data), number=10000)/10000
print("Timeit measurements:")
print("parsing:           {:.10f} sec/call".format(parsetime))

# d = d.compile()
# print(d.benchmark(data))

f = Format('', [
    'u32 <count>',
    'u8 <num1>',
    'u24 <num2>'
])

data = Bits(data)
f.parse(data)

parsetime = timeit(lambda: f.parse(data), number=10000)/10000
print("Timeit measurements:")
print("parsing:           {:.10f} sec/call".format(parsetime))