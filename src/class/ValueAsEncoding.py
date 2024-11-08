import sys
import re
import struct
import base64
import enum
import copy
import encodings

__author__ = 'Michel Diemer'
__copyright__ = 'Copyright 2021, Pthon float_IEEE754'
__credits__ = ['Michel Diemer']
__version__ = '0.1.beta'
__maintainer__ = 'Michel Diemer'
__email__ = 'pub.diemer@laposte.net'
__status__ = 'Development'

class ValueImportFormats(enum.Enum):
    '''Formats from which data can be imported with class ValueAsEncoding'''
    BIN = 'unsigned binary string (uses python int)',
    INT = 'unsigned integer string (uses python int)',
    HEX = 'unsigned hexadecimal string (uses python int)',
    FLOAT = 'python float',
    SIGNED_INT = 'signed integer string (uses python int)',
    BASE64 = 'base64 ascii string, both standard and url supported',
    STR = 'string ; please provide encoding'


class ValueAsEncoding:
    ''' Import raw values according to one of the ValueImportFormats
        Reencode the raw value in different formats
        Uses struct.pack, base64.decodebytes and string.encode to import bytes
        Uses struct.unpack, base64.eencodebytes and string.decode to decode bytes'''

    __encodings = tuple(['ascii', 'utf_8', 'utf_16', 'utf_32',
                        'cp1252', 'latin_1', 'iso8859_15', 'mac_roman'])
    '''Python string encodings used with decode'''

    __bytesOrders = {
        'native-align': {'p': '@', 'tb': sys.byteorder},
        'native': {'p': '=', 'tb': sys.byteorder},
        'little-endian': {'p': '<', 'tb': 'little'},
        'big-endian': {'p': '>', 'tb': 'big'},
        'network':  {'p': '!', 'tb': 'big'}  # big-e,dian
    }
    """ List of ByteOrders and format values for struct.pack (key 'p')
        and int.to_bytes (key 'tb')"""

    #           Int   Float  Str
    #  8 bits ? b B          ascii cp1252 hex mac_roman
    # 16 bits   h H   e
    # 32 bits   i I   f
    # 64 bits   q Q   d
    # full                   int uint base64
    __formats = {
        8: {'ints': {'bool': '?', 'int': 'b', 'uint': 'B'}, 'encs': ['ascii', 'cp1252', 'mac_roman'], 'hex': ''},
        16: {'ints': {'int': 'h', 'uint': 'H'}, 'float': 'e'},
        32: {'ints': {'int': 'i', 'uint': 'I'}, 'float': 'f'},
        64: {'ints': {'int': 'q', 'uint': 'Q'}, 'float': 'd'},
        'all': {'encs': __encodings, 'hex': '', 'base64': '', 'bigint': ''}
    }
    """ List of formats in which data is decoded
        chuncks uf 8 bits/16 bits/32 bits/64 bits as well as full packed data"""

    """
    TODO unit tests / make sure it is robust
    TODO test performance / improve
    TODO better handling of string encode/decode errors
        strict - default response which raises a UnicodeDecodeError exception on failure
        ignore - ignores the unencodable unicode from the result
        replace - replaces the unencodable unicode to a question mark ?
        xmlcharrefreplace - inserts XML character reference instead of unencodable unicode
        backslashreplace - inserts a \\uNNNN escape sequence instead of unencodable unicode
        namereplace - inserts a \\N{...} escape sequence instead of unencodable unicode"""

    def __init__(self,
                strValue: str = '',
                fmt=ValueImportFormats.STR,
                strEncoding: str = 'utf_8',
                byteOrder: str = sys.byteorder + '-endian'):
        '''Creates bytes from a string value and interprets these bytes according to various formats

            Parameters
            ----------
                strValue     : raw string value to import of type string
                fmt          : format of raw value
                strEncoding  : if raw value is ValueImportFormats.STR, string encoding
                byteOrder    : see __bytesOrders above

            Process
            -------
                Translates strValue as bytes
                Retranslates bytes as various formats
                Public methods are available
        '''

        # default values
        self.__value = str(strValue)
        self.__format = ValueImportFormats.STR
        self.__reEncoded = dict()
        self.__packed = bytearray()
        self.__strEncoding = 'utf_8'
        self.__bo = self.__bytesOrders['big-endian']
        self.__strEncodeErrors = 'namereplace'
        self.__strDecodeErrors = 'ignore'

        # Apply encoding parameter if correct
        if strEncoding in self.__encodings:
            self.__strEncoding = strEncoding

        # Apply byteOrder parameter if correct
        if(byteOrder in self.__bytesOrders):
            self.__bo = self.__bytesOrders[byteOrder]

        # Apply format parameter if correct
        if isinstance(fmt, ValueImportFormats):
            self.__format = fmt

        # Packbytes, creates __self.packed attribute
        self.__packBytes()

        # UnpackBytes using __self.packed ; creates __reEncoded attribute as a dictonnary
        self.__unpackBytes()

    def __getitem__(self, key):
        '''Return relevant decoded/interpreted value'''
        return copy.deepcopy(self.__reEncoded[key])

    def keys(self):
        '''Returns the available keys'''
        return self.__reEncoded.keys()

    def __packInt(self, value, signed=False):
        ''' Wrapper for int.to_bytes
            taking care of the sign and number of bits required'''
        #fmt = 'B' if nBits <= 8 else 'H' if nBits <= 16 else 'L' if nBits <= 32 else 'Q' if nBits <= 64 else 'P'
        # return struct.pack(bytesOrder[bo]['p']+fmt, value)
        nbytes = ((value.bit_length() + 7) // 8)
        try:
            return value.to_bytes(nbytes, self.__bo['tb'], signed=signed)
        except OverflowError:
            return value.to_bytes(nbytes+1, self.__bo['tb'], signed=signed)

    def __myStructUnpack(self, packed, fmt, l):
        '''Wrapper for struct.unpack, checking size and ignoring exceptions'''
        if len(packed) >= struct.calcsize(fmt):
            try:
                unpackfmt = str(len(packed) // struct.calcsize(fmt))+fmt
                l.append(struct.unpack(unpackfmt, packed))
            except struct.error as err:
                pass

    def getBytes(self):
        '''Return the bytes as is'''
        return copy.deepcopy(self.__packed)

    def bytesOrders(self):
        '''Returns the tuple of available bytes orders'''
        return tuple(self.__bytesOrders.keys())

    def byteOrder(self):
        '''Returns the byte ordering applied'''
        return self.__bo

    def stringEncodings(self):
        '''Returns the available string encodings'''
        return tuple(self.__encodings)

    def __packBytes(self):
        '''Creates the self.__packed attribute, see __init__'''
        match self.__format:
            case ValueImportFormats.BIN:
                self.__packed = self.__packInt(int(self.__value, 2))
            case ValueImportFormats.INT:
                self.__packed = self.__packInt(int(self.__value))
            case ValueImportFormats.HEX:
                self.__packed = self.__packInt(int(self.__value, 16))
            case ValueImportFormats.FLOAT:
                # 'd' for double which is Python float format
                self.__packed = struct.pack(
                    self.__bo['p']+'d', float(self.__value))
            case ValueImportFormats.SIGNED_INT:
                self.__packed = self.__packInt(value, True)
            case ValueImportFormats.BASE64:
                # Both standard and URL base64 allowed
                # Before decoding bytes, make sure the string is ASCII
                self.__packed = base64.decodebytes(self.__value.replace(
                    '+', '-').replace('/', '_').encode('ascii'))
            case ValueImportFormats.STR:
                self.__packed = value.encode(
                    self.__strEncoding, self.__strEncodeErrors)
            case _:
                self.__format = ValueImportFormats.STR
                self.__packed = value.encode(
                    self.__strEncoding, self.__strEncodeErrors)

    def __unpackBytes(self):
        ''' Creates the self.__reEncoded attribute being used by __get_item__
            see __init__'''

        # empy dictionnary
        o = dict()

        for n in self.__formats:
            # n is 8/16/32/64 all
            o[n] = dict()

            packedList = []
            if isinstance(n, int):
                # creates chunks of 8/16/32/64 bits according to the value of n
                k = len(self.__packed) // (n // 8)
                for i in range(k):
                    # packedList will contain chuncks of (n*8) bytes
                    # 32 bits : 4 chuncks of 1 byte, 2 chuncks of 2 bytes, 1 chunck of 4 bytes, 0 chuncks of 8 bytes
                    packedList.append(self.__packed[(n // 8)*i:(n // 8)*(i+1)])
            else:
                # treats self.__packed as a unit of data
                packedList.append(self.__packed)

            for fmt in self.__formats[n]:

                if fmt != 'encs' and fmt != 'ints':
                    o[n][fmt] = []

                if fmt == 'ints':
                    # encodes as various ints formats
                    for fmti in self.__formats[n][fmt]:
                        o[n].setdefault(fmti, [])
                        u = n//8

                        if isinstance(n, int) and (len(self.__packed) % u) != 0:
                            # put 24 bits into 16 bit otherwises 24 bits won't fit in 16 bits
                            self.__myStructUnpack(
                                self.__packed[:u*(len(self.__packed)//u)], self.__formats[n]['ints'][fmti], o[n][fmti])
                        else:
                            self.__myStructUnpack(
                                self.__packed, self.__formats[n]['ints'][fmti], o[n][fmti])

                # loops for chunks
                # eg if 32 bits value given as strValue un __init
                #    for n==8   4 chunks of  8 bits   loop 4 chunks
                #        n==16  2 chunks of 16 bits   loop 2 chunks, including 16 bit float
                #        n==32  1 chunk  of 32 bits   loop 1 chunk, including 2x16 bit float and 1 32 bit float
                #        n==64  packedList is empty, don't loop
                for lpacked in packedList:

                    if fmt == 'ints':
                        # ints processes above
                        pass

                    elif fmt == 'float':
                        self.__myStructUnpack(
                            lpacked, self.__formats[n][fmt], o[n][fmt])

                    elif fmt == 'encs':
                        # some 8 bits encodings : cp1252 latin_1 ...
                        # utf_8 utf_16 on the whole packet only
                        for enc in self.__formats[n][fmt]:
                            o[n].setdefault(enc, [])
                            try:
                                o[n][enc].append(lpacked.decode(
                                    enc, self.__strDecodeErrors))
                            except struct.error as err:
                                pass

                    elif fmt == 'base64':
                        # base65 string, remove leading b' and ending '
                        o[n][fmt].append(str(base64.b64encode(lpacked))[2:-1])

                    elif fmt == 'hex':
                        # hex data, remove lading 0x
                        o[n][fmt].append(
                            hex(int.from_bytes(lpacked, self.__bo['tb']))[2:].upper())

                    elif fmt == 'bigint':
                        # bigint on full packed data, in practice called once
                        o[n][fmt].append(int.from_bytes(
                            lpacked, self.__bo['tb']))

        # o is a dictionnary containing
        # o[8]     :  8 bits decdings
        # o[16]    : 16 bits decdings
        # ...
        # o['all'] : encodings on full stri
        # final result will have int8 uint8 int16 uint16 ... base64 hex utf_8 indices
        res = dict()
        for n in o:
            for k in o[n]:
                if n == 'all':
                    key = k
                elif str(k)[-1].isnumeric():
                    key = k + '_' + str(n)
                else:
                    key = k + str(n)
                res[key] = o[n][k]

        # creates the __reEncoded attribute
        self.__reEncoded = res


def usage():
    print('Program that takes binary/raw values and decodes it one by one according to various encodings')
    print('Raw values are interpreded according to :')
    print('    8/12/32/64 bits numeric data types')
    print('    several string characher encodings including utt8/16/32 cp1252 latin_1 and more')
    print('    uses systen endianess by default')
    print('Usage : ')
    print('    ' + sys.argv[0] + ' value1 value2 value3 ... valueN')
    print('   ' + ' Values : ')
    print('   ' + '     0b<binary>              : encoded as binary')
    print('   ' + '     0x<hex>                 : encoded as hexadecimal ')
    print('   ' + '     0f<float>               : encoded as Python float ')
    print('   ' + '     0ui<int>                : encoded as unsigned integer')
    print('   ' + '     0i<int>                 : encoded as signed integer ')
    print('   ' + '     0s#<encoding>#<string>  : encoded as string encoded according to encoding')
    print('   ' + '         Encodings : ' + str(encodings))
    print('   ' + '     0sb64#<string>          : encoded as base64 ascii string')
    sys.exit()


if __name__ == '__main__':

    if len(sys.argv) == 1 or sys.argv[1] == '-h' or sys.argv[1] == '--help':
        usage()

    for arg in sys.argv[1:]:

        vae = ValueAsEncoding

        vae = None

        if re.match('^0b', arg):
            value = int(arg[2:], 2)
            vae = ValueAsEncoding(arg[2:], ValueImportFormats.BIN)
        elif re.match('^0x', arg):
            value = int(arg[2:], 16)
            vae = ValueAsEncoding(arg[2:], ValueImportFormats.HEX)
        elif re.match('^0f', arg):
            value = float(arg[2:])
            vae = ValueAsEncoding(float(arg[2:]), ValueImportFormats.FLOAT)
        elif re.match('^0ui', arg):
            value = int(arg[2:])
            vae = ValueAsEncoding(int(arg[2:]), ValueImportFormats.INT)
        elif re.match('^0i', arg):
            value = int(arg[3:])
            vae = ValueAsEncoding(int(arg[3:]), ValueImportFormats.SIGNED_INT)
        elif re.match('^0s#.*#.*$', arg):
            value = arg.split("#", 2)[2]
            encoding = arg.split("#", 2)[1]
            packed = ValueAsEncoding(
                arg.split("#", 2)[2], ValueImportFormats.SIGNED_STR, arg.split("#", 2)[1])

        elif re.match('^0sb64#.*$', arg):
            value = arg[len('^0sb64#'):]
            vae = ValueAsEncoding(
                arg[len('^0sb64#'):], ValueImportFormats.BASE64)

        else:
            value = arg
            vae = ValueAsEncoding(value)

    for k in vae.keys():
        print(k, vae[k])
