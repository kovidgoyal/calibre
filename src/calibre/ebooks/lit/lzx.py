# License: GPLv3 Copyright: 2008, Marshall T. Vandegrift <llasram@gmail.com>

"""
LZX compression/decompression wrapper.
"""

from calibre_extensions import lzx as _lzx

__all__ = ['Compressor', 'Decompressor', 'LZXError']

LZXError = _lzx.LZXError
Compressor = _lzx.Compressor


class Decompressor:
    def __init__(self, wbits):
        self.wbits = wbits
        self.blocksize = 1 << wbits
        _lzx.init(wbits)

    def decompress(self, data, outlen):
        return _lzx.decompress(data, outlen)

    def reset(self):
        return _lzx.reset()
