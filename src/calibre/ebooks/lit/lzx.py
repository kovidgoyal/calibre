

'''
LZX compression/decompression wrapper.
'''

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

from calibre_extensions import lzx as _lzx

__all__ = ['Compressor', 'Decompressor', 'LZXError']

LZXError = _lzx.LZXError
Compressor = _lzx.Compressor


class Decompressor(object):

    def __init__(self, wbits):
        self.wbits = wbits
        self.blocksize = 1 << wbits
        _lzx.init(wbits)

    def decompress(self, data, outlen):
        return _lzx.decompress(data, outlen)

    def reset(self):
        return _lzx.reset()
