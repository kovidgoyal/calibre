# vim:fileencoding=utf-8
# License: BSD Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

def base64encode(bytes, altchars, pad_char):
    # Convert an array of bytes into a base-64 encoded string
    l = bytes.length
    remainder = l % 3
    main_length = l - remainder
    encodings = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789' + (altchars or '+/')
    pad_char = '=' if pad_char is undefined else pad_char
    ans = v'[]'
    for v'var i = 0; i < main_length; i += 3':
        chunk = (bytes[i] << 16) | (bytes[i + 1] << 8) | bytes[i + 2]
        ans.push(encodings[(chunk & 16515072) >> 18], encodings[(chunk & 258048) >> 12], encodings[(chunk & 4032) >> 6], encodings[chunk & 63])
    if remainder is 1:
        chunk = bytes[main_length]
        ans.push(encodings[(chunk & 252) >> 2], encodings[(chunk & 3) << 4], pad_char, pad_char)
    elif remainder is 2:
        chunk = (bytes[main_length] << 8) | bytes[main_length + 1]
        ans.push(encodings[(chunk & 64512) >> 10], encodings[(chunk & 1008) >> 4], encodings[(chunk & 15) << 2], pad_char)
    return ans.join('')

def base64decode(string):
    # convert the output of base64encode back into an array of bytes
    # (Uint8Array) only works with the standard altchars and pad_char
    if jstype(window) is not 'undefined':
        chars = window.atob(string)
    else:
        chars = new Buffer(string, 'base64').toString('binary')  # noqa: undef
    ans = Uint8Array(chars.length)
    for i in range(ans.length):
        ans[i] = chars.charCodeAt(i)
    return ans

def urlsafe_b64encode(bytes, pad_char):
    return base64encode(bytes, '-_', pad_char)

def urlsafe_b64decode(string):
    string = String.prototype.replace.call(string, /[_-]/g, def(m): return '+' if m is '-' else '/';)
    return base64decode(string)

def hexlify(bytes):
    ans = v'[]'
    for v'var i = 0; i < bytes.length; i++':
        x = bytes[i].toString(16)
        if x.length is 1:
            x = '0' + x
        ans.push(x)
    return ans.join('')

def unhexlify(string):
    num = string.length // 2
    if num * 2 is not string.length:
        raise ValueError('string length is not a multiple of two')
    ans = Uint8Array(num)
    for v'var i = 0; i < num; i++':
        x = parseInt(string[i*2:i*2+2], 16)
        if isNaN(x):
            raise ValueError('string is not hex-encoded')
        ans[i] = x
    return ans

utf8_decoder_table = v'''[
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 00..1f
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 20..3f
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 40..5f
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 60..7f
  1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9, // 80..9f
  7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7, // a0..bf
  8,8,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2, // c0..df
  0xa,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x4,0x3,0x3, // e0..ef
  0xb,0x6,0x6,0x6,0x5,0x8,0x8,0x8,0x8,0x8,0x8,0x8,0x8,0x8,0x8,0x8, // f0..ff
  0x0,0x1,0x2,0x3,0x5,0x8,0x7,0x1,0x1,0x1,0x4,0x6,0x1,0x1,0x1,0x1, // s0..s0
  1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,1,1,1,1,1,0,1,0,1,1,1,1,1,1, // s1..s2
  1,2,1,1,1,1,1,2,1,2,1,1,1,1,1,1,1,1,1,1,1,1,1,2,1,1,1,1,1,1,1,1, // s3..s4
  1,2,1,1,1,1,1,1,1,2,1,1,1,1,1,1,1,1,1,1,1,1,1,3,1,3,1,1,1,1,1,1, // s5..s6
  1,3,1,1,1,1,1,3,1,3,1,1,1,1,1,1,1,3,1,1,1,1,1,1,1,1,1,1,1,1,1,1, // s7..s8
]'''

def _from_code_point(x):
    if x <= 0xFFFF:
        return String.fromCharCode(x)
    x -= 0x10000
    return String.fromCharCode((x >> 10) + 0xD800, (x % 0x400) + 0xDC00)

def utf8_decode(bytes, errors, replacement):
    # Convert an array of UTF-8 encoded bytes into a string
    state = 0
    ans = v'[]'

    for v'var i = 0, l = bytes.length; i < l; i++':  # noqa
        byte = bytes[i]
        typ = utf8_decoder_table[byte]
        codep = (byte & 0x3f) | (codep << 6) if state is not 0 else (0xff >> typ) & (byte)
        state = utf8_decoder_table[256 + state*16 + typ]
        if state is 0:
            ans.push(_from_code_point(codep))
        elif state is 1:
            if not errors or errors is 'strict':
                raise UnicodeDecodeError(str.format('The byte 0x{:02x} at position {} is not valid UTF-8', byte, i))
            elif errors is 'replace':
                ans.push(replacement or '?')
    return ans.join('')

def utf8_encode_js(string):
    # Encode a string as an array of UTF-8 bytes
    escstr = encodeURIComponent(string)
    ans = v'[]'
    for v'var i = 0; i < escstr.length; i++':
        ch = escstr[i]
        if ch is '%':
            ans.push(parseInt(escstr[i+1:i+3], 16))
            i += 2
        else:
            ans.push(ch.charCodeAt(0))
    return Uint8Array(ans)

if jstype(TextEncoder) is 'function':
    _u8enc = TextEncoder('utf-8')
    utf8_encode = _u8enc.encode.bind(_u8enc)
    _u8enc = undefined
else:
    utf8_encode = utf8_encode_js

def utf8_encode_native(string):
    return _u8enc.encode(string)
