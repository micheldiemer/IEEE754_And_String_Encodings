import struct
import bitarray
import bitarray.util
import re
import decimal as dc
import copy
import sys
from math import frexp, isnan, isfinite

__author__ = 'Michel Diemer'
__copyright__ = 'Copyright 2021, Pthon float_IEEE754'
__credits__ = ['Michel Diemer']
__version__ = '0.2.beta'
__maintainer__ = 'Michel Diemer'
__email__ = 'pub.diemer@laposte.net'
__status__ = 'Development'

class float_IEEE754(float):

    SIGN_PLUS = ''
    SIGN_MINUS = '-'

    # description of pack/unpack to_bytes formats
    # and number of bits for exponent
    __desc = {
        16: {'pack': 'H', 'unpack': 'e', 'e': 5},
        32: {'pack': 'I', 'unpack': 'f', 'e': 8},
        64: {'pack': 'Q', 'unpack': 'd', 'e': 11}
    }

    # TODO test byte orders other than big-endian
    __bytesOrders = {
    'native-align': {'p': '@', 'tb': sys.byteorder},
    'native': {'p': '=', 'tb': sys.byteorder},
    'little-endian': {'p': '<', 'tb': 'little'},
    'big-endian': {'p': '>', 'tb': 'big'},
    'network':  {'p': '!', 'tb': 'big'}  # big-e,dian
    }

    def fromString(value, nbits=64, base=2, forcePositive=False,
                    byteOrder: str = sys.byteorder + '-endian'):

        byteOrder = "big-endian"
        botb = float_IEEE754.__bytesOrders[byteOrder]['tb']
        bop = float_IEEE754.__bytesOrders[byteOrder]['p']

        # Create float_IEEE754 from int string according to base given
        if(forcePositive):
            if base == 2:
                value[0] = '0'
            elif value[0] == float_IEEE754.SIGN_MINUS:
                value = value[1:]
        x = int(value, base)
        if nbits < 32:
            nbits = 16
        elif nbits < 63:
            nbits = 32
        else:
            nbits = 64
        bits_required = x.bit_length()
        while(bits_required % 8 != 0):
            bits_required += 1
        xbytes = bits_required // 8
        nbytes = nbits // 8
        bf = x.to_bytes(xbytes, botb)
        while(len(bf) < nbytes):
            # TODO test endianess
            bf.append(b'\x00')
        # bfb = x.to_bytes(nbytes, 'big')
        # bfl = x.to_bytes(nbytes, 'little')

        lf = struct.unpack(bop+float_IEEE754.__desc[nbits]['unpack'], bf)[0]
        return float_IEEE754(lf,nbits)

    def fromBytes(value, nbits=64,
                    byteOrder: str = sys.byteorder + '-endian'):
        # Create float_IEEE754 from bytes

        # TODO exception if len(bytes) != 8*nbits
        bop = float_IEEE754.__bytesOrders[byteOrder]['p']
        lf = struct.unpack(bop+float_IEEE754.__desc[nbits]['unpack'], value)
        return float_IEEE754(lf[0], nbits)

    def fromBitarray(value,
                        byteOrder: str = sys.byteorder + '-endian'):
        # Create float_IEEE754 from bitarray
        return float_IEEE754.fromBytes(value.tobytes(), len(value), byteOrder)

    def __new__(self, value, nbits, forcePositive = False):
        # new instance
        value=value if not forcePositive else abs(value)
        return super().__new__(self, value)


    def __init__(self, value, nbits = 64, base = 2):
        # new instance
        float.__init__(value)

        self.nbits=nbits if nbits in self.__desc else 64
        self.base = base
        self.p = 53   # TODO support other formats
        self.emin = 1
        self.emax = 1023

        # formula (-1)^S x b^e x m
        #   emin <= e <= emax
        #   0 <= m < b

        # formula (-1)^S x b^q x c
        #   emin <= q + p - 1 <= emax
        #   0 <= c < b^p

        self.__fmt=self.__desc[self.nbits]
        packed=struct.pack('!'+self.__fmt['unpack'], value)

        self.__bitarray=bitarray.bitarray()
        self.__bitarray.frombytes(packed)

        SP=float_IEEE754.SIGN_PLUS
        SM=float_IEEE754.SIGN_MINUS

        self.rawSign=self.__bitarray[0]
        self.rawExp=self.__bitarray[1:self.__fmt['e']+1]
        self.rawMantissa=self.__bitarray[self.__fmt['e']+1:]

        self.isExp0=not self.rawExp.any()

        # TODO check this closely
        self.expBias=2**(self.__fmt['e'] - 1) - 1

        # IEEE 754 fields
        self.sign=SM if self.__bitarray[0] == 1 else SP

        self.normal=self.rawExp.any() or not self.rawMantissa.any()
        self.negativeNormal=self.normal and self.sign == SM
        self.positiveNormal=self.normal and self.sign == SP

        self.subnormal=not self.rawExp.any() and self.rawMantissa.any()
        self.negativeSubnormal=self.subnormal and self.sign == SM
        self.positiveSubnormal=self.subnormal and self.sign == SP

        self.zero=not self.rawMantissa.any() and not self.rawExp.any()
        self.positiveZero=self.zero and self.sign == SP
        self.negativeZero=self.zero and self.sign == SM

        self.infinity=self.rawExp.all() and not self.rawMantissa.any()
        self.negativeInfinity=self.infinity and self.sign == SM
        self.positiveInfinity=self.infinity and self.sign == SP

        self.NaN=self.rawExp.all() and self.rawMantissa.any()
        self.signalingNaN=self.NaN and self.rawMantissa[0] == 0
        self.quietNaN=self.NaN and self.rawMantissa[0] == 1
        self.finite=self.zero or (not self.infinity and not self.NaN)

        # TODO is this correct ?
        self.canonical=not self.NaN or self.signalingNaN or not self.rawMantissa[1:].any(
        )

        self.emin=1
        self.emax=2**self.__fmt['e'] - self.expBias
        # 2 ** EXP - BIAS
        # http://mathcenter.oxford.emory.edu/site/cs170/ieee754/
        self.intRawExp=bitarray.util.ba2int(self.rawExp)
        # TODO why +1 here ??? It give correct results
        #      but I don't understand it very well
        self.exp=self.intRawExp - self.expBias + 1
        if self.infinity or self.NaN or self.zero:
            self.exp=0


        if self.infinity:
            # TODO verify mantissa value for Inf/NaN
            self.mantissaExpr='inf'
            self.bmantissa=self.rawMantissa
            self.mantissa=float('inf')
        elif self.NaN:
            self.mantissaExpr='nan'
            self.bmantissa=self.rawMantissa
            self.mantissa=float('nan')
        else:
            if self.zero:
                self.bmantissa=self.rawMantissa
            else:
                self.bmantissa=bitarray.bitarray()
                self.bmantissa.append(1)
                self.bmantissa.extend(self.rawMantissa)

            mantissaExprList=[]
            i=0
            temp=dc.Decimal(0.0)
            for v in self.bmantissa:
                i -= 1
                if v == 1:
                    mantissaExprList.append(i)
                    temp=temp + dc.Decimal(1) / dc.Decimal(2**(-i))
            self.mantissaExpr=mantissaExprList
            self.mantissa=float(temp)

        # TODO shorten syntax
        self.bitstring=''
        self.bitstring += str(self.rawSign)
        self.bitstring += '_' + str(self.rawExp)[10:-2]
        self.bitstring += '_' + str(self.rawMantissa)[10:-2]


    def as_int_tuple(self):
        return tuple(self.nbits, self.rawSign, bitarray.util.ba2int(self.rawExp), bitarray.util.ba2int(self.rawMantissa))

    def __getitem__(self, index):
        # get bit at position index
        return self.__bitarray[index]

    def new_from_int_tuple(ftuple, byteOrder: str = sys.byteorder + '-endian'):
        # tuple should come from as_int_tuple
        #  (numberOfBits,
        # sign,
        # uintRawExponent,
        # unitRawMantissa)

        nbits=ftuple[0]

        s=f'{ftuple[1]:0b}'
        if(len(s) != 1):
            raise ValueError('Incorrect length for sign')

        nbits_e=float_IEEE754.__desc[nbits]['e']
        if ftuple[2].bit_length() > nbits_e:
            raise OverflowError('Value too large for exponent')
        e=f'{ftuple[2]:0b}'.zfill(nbits_e)

        nbits_m=nbits - 1 - nbits_e
        if ftuple[3].bit_length() > nbits_m:
            raise OverflowError('Value too large for mantissa')
        m=f'{ftuple[3]:0b}'.zfill(nbits_m)

        return fromString(s+e+m, nbits, byteOrder=byteOrder)


    def newFromBitSet(self, index, value,
                        byteOrder: str=sys.byteorder + '-endian'):
        # deepcopies internal bitarray, set one bit and gives new instance
        if self.__bitarray[index] == value:
            return self
        t=copy.deepcopy(self.__bitarray)
        t[index]=value
        return float_IEEE754.fromBitarray(t, byteOrder)

    def newFromBitReverse(self, bit):
        # creates a new instance from current instance, reversing one bit

        # TODO better syntax
        v=1 if self.__bitarray[bit] == 0 else 0
        return float_IEEE754.newFromBitSet(self, bit, v)

    def abs(value):
        return float_IEEE754(value, value.nbits, True)

    def isSignMinus(self):
        return self.sign == float_IEEE754.SIGN_MINUS

    def isNormal(self):
        return self.normal

    def isFinite(self):
        return self.finite

    def isZero(self):
        return self.zero

    def isSubnormal(self):
        return self.subnormal

    def isInfinite(self):
        return self.infinity

    def isNaN(self):
        return self.NaN

    def isSignaling(self):
        return self.signalingNaN

    def isCanonical(self):
        # TODO check self.canonical in __init__ function
        return self.canonical

    def nanPayload(self):
        # Returns a bitarray of a non-canonical NaN

        # TODO check if correct and test
        if not self.NaN or self.canonical:
            return 0
        return copy.deepcopy(self.__fmt['e'][2:])

    def radix(self):
        # TODO improve
        return 2

    def totalOrder(x, y):
        SP=float_IEEE754.SIGN_PLUS
        SM=float_IEEE754.SIGN_MINUS
        if x.finite and y.finite:
            if not x.zero and not y.zero:
                if x < y:
                    return True
                if x > y:
                    return False
                if x == y:
                    if y.negativeZero and x.positiveZero:
                        return True
                    if x.positiveZero and y.negativeZero:
                        return False
                    if x.sign == SM and y.sign == SM:
                        return x.exp >= y.exp
                    else:
                        return x.exp <= y.exp
            else:
                if x.positiveZero and y.negativeZero:
                    return False
                else:
                    return True
        if x.NaN or y.NaN:
            if x.sign == SM and not y.NaN:
                return True
            if y.sign == SP and not x.NaN:
                return True
            if x.sign == SM and y.sign == SP:
                return True
            if x.sign == SP and y.sign == SM:
                return False
            else:
                # TODO / not accurate
                # signaling orders below quiet for +NaN
                #                  reverse for -NaN
                # lesser payload when regarded as integer
                # orders below naNgreater payload fir +NaN
                # reverse for -NaN
                return False


    def totalOrderMag(x, y):
        # TODO test
        return totalOrder(self.abs(x), self.abs(y))

def floatIEEE754vsPythonFloat(f754):
    # compares float_IEEE754 instance with Python equivalent value
    # compares results of isnan and isfinite and other values

    fPython=float(f754)
    if f754.nbits != 64:
        return False

    if f754.isNaN() and f754.isFinite():
        return False

    if f754.isNaN() and f754.infinity:
        return False

    if f754.isFinite() and f754.infinity:
        return False

    if isnan(fPython) and f754.isNaN():
        return isfinite(fPython) == f754.isFinite()

    if not isfinite(fPython) and not f754.isFinite():
        return fPython == f754

    if isnan(fPython) and not f754.isNaN():
        return False

    if not isnan(fPython) and f754.isNaN():
        return False

    if isfinite(fPython) and not f754.isFinite():
        return False

    if f754.isFinite() and not isfinite(fPython):
        return False

    if f754.isFinite() and isfinite(fPython):
        v=frexp(fPython)
        return f754 == fPython and v[0] == f754.mantissa and v[1] == f754.exp

    return False



def test():
    # performs the test
    # using floatIEEE754vsPythonFloat function
    print('testing')

    for t in ['+0', '-0', 'Inf', '-Inf', 'NaN', '-NaN']:
        v=float(t)
        f=float_IEEE754(v, 64)
        if not floatIEEE754vsPythonFloat(f):
            print("test failed f=", f.bitstring)

    for i in range(4):
        for j in range(4):
            if (i == 0 and j == 0):
                v=0
            elif (i == 0):
                v=2.0 ** (-j)
            else:
                v=2.0 ** (j-1) + 2.0 ** (-i)
            f=float_IEEE754(v, 64)
            if not floatIEEE754vsPythonFloat(f):
                print("test failed f=", f.bitstring)



    for i in range(1, 11):
        for j in range(1, 11):
            l=['0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0']
            l[i]='1'
            l[11-j]='1'
            v='0' + ''.join(l) + '1111' + '0'*48
            f=float_IEEE754.fromString(v, 64)
            if not floatIEEE754vsPythonFloat(f):
                print("test failed f=", f.bitstring)

    v='0' + '11111111110' + '1111' + '0'*48
    f=float_IEEE754.fromString(v, 64)
    if not floatIEEE754vsPythonFloat(f):
        print("test failed f=", f.bitstring)


    v='0' + '01111111111' + '1111' + '0'*48
    f=float_IEEE754.fromString(v, 64)
    if not floatIEEE754vsPythonFloat(f):
        print("test failed f=", f.bitstring)


    for i in range(4):
        for j in range(4):
            if (i == 0 and j == 0):
                v=0
            elif (i == 0):
                v=2.0 ** (-j)
            else:
                v=2.0 ** (j-1) + 2.0 ** (-i)

            f=float_IEEE754(v, 64)
            if not floatIEEE754vsPythonFloat(f):
                print("test failed f=", f.bitstring)

    print('test done')

def usage():
    print('Usage:')
    print(' ' + sys.argv[0] + ' value1 value2 ... valueN')
    print(' Possible values : ')
    print('    0bnnnnnnnn      : 16/32/64 bits binary string')
    print('    0xnnnnnnnn      :  4/ 8/16   hex digits')
    print('    0fnnnnnnnn      : float value')
    print('    0innnnnnnn      : int value (64 bits float)')
    print('    --test          : test')
    print('')
    print('python.exe .\float_IEEE754.py 0i1024 0i1023 working')
    sys.exit()

if __name__ == '__main__':

    for arg in sys.argv[1:]:
        showFloat = False
        if re.match('^0b', arg):
            f=float_IEEE754.fromString(arg[2:], len(arg)-2)
            showFloat = True
        elif re.match('^0f', arg):
            f=float_IEEE754(float(arg[2:]), 64)
            showFloat = True
        elif re.match('^0x', arg):
            nbits = (len(arg[2:]) - 2) * 8
            f=float_IEEE754.fromString(arg[2:],nbits=nbits,base=16)
            showFloat = True
        elif re.match('^0i', arg):
            f=float_IEEE754(float(arg[2:]), 64, 10)
            showFloat = True
        elif arg == "--test":
            test()
        elif arg == "--compare":
            test()
        else:
            usage()

        if showFloat:
            print(f.bitstring)
            #print(f.as_int_tuple())

    if len(sys.argv) == 1:
        usage()
