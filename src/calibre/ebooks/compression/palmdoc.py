#!/usr/bin/env  python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from cStringIO import StringIO
from struct import pack

from calibre.constants import plugins
cPalmdoc = plugins['cPalmdoc'][0]
if not cPalmdoc:
    raise RuntimeError(('Failed to load required cPalmdoc module: '
            '%s')%plugins['cPalmdoc'][1])

def decompress_doc(data):
    return cPalmdoc.decompress(data)

def compress_doc(data):
    if not data:
        return u''
    return cPalmdoc.compress(data)

def test():
    TESTS = [
            'abc\x03\x04\x05\x06ms', # Test binary writing
            'a b c \xfed ', # Test encoding of spaces
            '0123456789axyz2bxyz2cdfgfo9iuyerh',
            '0123456789asd0123456789asd|yyzzxxffhhjjkk',
            ('ciewacnaq eiu743 r787q 0w%  ; sa fd\xef\ffdxosac wocjp acoiecowei '
            'owaic jociowapjcivcjpoivjporeivjpoavca; p9aw8743y6r74%$^$^%8 ')
            ]
    for test in TESTS:
        print 'Test:', repr(test)
        print '\tTesting compression...'
        good = py_compress_doc(test)
        x = compress_doc(test)
        print '\t\tgood:',  repr(good)
        print '\t\tx   :',  repr(x)
        assert x == good
        print '\tTesting decompression...'
        print '\t\t', repr(decompress_doc(x))
        assert decompress_doc(x) == test
        print

def py_compress_doc(data):
    out = StringIO()
    i = 0
    ldata = len(data)
    while i < ldata:
        if i > 10 and (ldata - i) > 10:
            chunk = ''
            match = -1
            for j in xrange(10, 2, -1):
                chunk = data[i:i+j]
                try:
                    match = data.rindex(chunk, 0, i)
                except ValueError:
                    continue
                if (i - match) <= 2047:
                    break
                match = -1
            if match >= 0:
                n = len(chunk)
                m = i - match
                code = 0x8000 + ((m << 3) & 0x3ff8) + (n - 3)
                out.write(pack('>H', code))
                i += n
                continue
        ch = data[i]
        och = ord(ch)
        i += 1
        if ch == ' ' and (i + 1) < ldata:
            onch = ord(data[i])
            if onch >= 0x40 and onch < 0x80:
                out.write(pack('>B', onch ^ 0x80))
                i += 1
                continue
        if och == 0 or (och > 8 and och < 0x80):
            out.write(ch)
        else:
            j = i
            binseq = [ch]
            while j < ldata and len(binseq) < 8:
                ch = data[j]
                och = ord(ch)
                if och == 0 or (och > 8 and och < 0x80):
                    break
                binseq.append(ch)
                j += 1
            out.write(pack('>B', len(binseq)))
            out.write(''.join(binseq))
            i += len(binseq) - 1
    return out.getvalue()

