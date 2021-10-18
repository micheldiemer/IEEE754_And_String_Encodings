# IEEE754_And_String_Encodings

In computer science, all data is bits
With n bits one can encode at most 2^n values, numbered from 0 to 2^n - 1

With 8 bits one can encode 256 different values, variying from 0 to 255
or, if we interpret those 8 bits as signed integers, those vary from -128 to 127
and if we interpret those 8 bits as a character, we have (most usualliy) 128 ASCII values
and for the 8th bit it depends on the character encoding : cp1252 latin_1 iso8859_15 mac_roman
and so on

For IEEE754 numbers we have sign, biased or unbiased exponent and mantisssa
    and special values : nan inf +0 -0 and more
    
The same 64 bit values can mean a lot of different things :
    * unsigned long long value from 0 to 2^64 - 1
    * signed long long value from 6 2^63 to 2^63 - 1
    * 2 utf-32 characters
    * 8 ascii caracters
    * 1 IEEE754 64 bits double (float with double precision)
    * 2 IEEE754 32 bits floats
    * ... and more
    
Both programs aim at taking some binary (or string) input, 
packing it into bytes
and unpacking it into a lot of different formats

The IEEE754 class also allows to change one bit of the number 
to watch the difference

## Please note
This has been roughly tested manually, not deeply
It should work for "standard" input and "standard" bit ordering
but some edge cases are not yet neither tested nor well implemented


## Enjoy !
