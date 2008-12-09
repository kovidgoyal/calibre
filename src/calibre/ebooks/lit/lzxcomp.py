from __future__ import with_statement
import sys
import os
from cStringIO import StringIO
from ctypes import *
from calibre import plugins
_lzx, LzxError = plugins['lzx']

__all__ = ['Compressor']

class lzx_data(Structure):
    pass
    
lzx_get_bytes_t = CFUNCTYPE(c_int, c_voidp, c_int, c_voidp)
lzx_put_bytes_t = CFUNCTYPE(c_int, c_voidp, c_int, c_voidp)
lzx_mark_frame_t = CFUNCTYPE(None, c_voidp, c_uint32, c_uint32)
lzx_at_eof_t = CFUNCTYPE(c_int, c_voidp)

class lzx_results(Structure):
    _fields_ = [('len_compressed_output', c_long),
                ('len_uncompressed_input', c_long)]

# int lzx_init(struct lzx_data **lzxdp, int wsize_code, 
#              lzx_get_bytes_t get_bytes, void *get_bytes_arg,
#              lzx_at_eof_t at_eof,
#              lzx_put_bytes_t put_bytes, void *put_bytes_arg,
#              lzx_mark_frame_t mark_frame, void *mark_frame_arg);
lzx_init_t = CFUNCTYPE(
    c_int, POINTER(POINTER(lzx_data)), c_int, lzx_get_bytes_t, c_voidp,
    lzx_at_eof_t, lzx_put_bytes_t, c_voidp, lzx_mark_frame_t, c_voidp)
lzx_init = lzx_init_t(_lzx._lzxc_init)

# void  lzx_reset(lzx_data *lzxd);
lzx_reset_t = CFUNCTYPE(None, POINTER(lzx_data))
lzx_reset = lzx_reset_t(_lzx._lzxc_reset)

# int lzx_compress_block(lzx_data *lzxd, int block_size, int subdivide);
lzx_compress_block_t = CFUNCTYPE(c_int, POINTER(lzx_data), c_int, c_int)
lzx_compress_block = lzx_compress_block_t(_lzx._lzxc_compress_block)

# int lzx_finish(struct lzx_data *lzxd, struct lzx_results *lzxr);
lzx_finish_t = CFUNCTYPE(c_int, POINTER(lzx_data), POINTER(lzx_results))
lzx_finish = lzx_finish_t(_lzx._lzxc_finish)


class Compressor(object):
    def __init__(self, wbits, reset=True):
        self._reset = reset
        self._blocksize = 1 << wbits
        self._buffered = 0
        self._input = StringIO()
        self._output = StringIO()
        self._flushing = False
        self._rtable = []
        self._get_bytes = lzx_get_bytes_t(self._get_bytes)
        self._at_eof = lzx_at_eof_t(self._at_eof)
        self._put_bytes = lzx_put_bytes_t(self._put_bytes)
        self._mark_frame = lzx_mark_frame_t(self._mark_frame)
        self._lzx = POINTER(lzx_data)()
        self._results = lzx_results()
        rv = lzx_init(self._lzx, wbits, self._get_bytes, c_voidp(),
                      self._at_eof, self._put_bytes, c_voidp(),
                      self._mark_frame, c_voidp())
        if rv != 0:
            raise LzxError("lzx_init() failed with %d" % rv)

    def _add_input(self, data):
        self._input.seek(0, 2)
        self._input.write(data)
        self._input.seek(0)
        self._buffered += len(data)

    def _reset_input(self):
        data = self._input.read()
        self._input.seek(0)
        self._input.truncate()
        self._input.write(data)
        self._input.seek(0)

    def _reset_output(self):
        data = self._output.getvalue()
        self._output.seek(0)
        self._output.truncate()
        return data

    def _reset_rtable(self):
        rtable = list(self._rtable)
        del self._rtable[:]
        return rtable
        
    def _get_bytes(self, arg, n, buf):
        data = self._input.read(n)
        memmove(buf, data, len(data))
        self._buffered -= len(data)
        return len(data)

    def _put_bytes(self, arg, n, buf):
        self._output.write(string_at(buf, n))
        return n

    def _at_eof(self, arg):
        if self._flushing and self._buffered == 0:
            return 1
        return 0

    def _mark_frame(self, arg, uncomp, comp):
        self._rtable.append((uncomp, comp))
        return

    def _compress_block(self):
        rv = lzx_compress_block(self._lzx, self._blocksize, 1)
        if rv != 0:
            raise LzxError("lzx_compress_block() failed with %d" % rv)
        if self._reset:
            lzx_reset(self._lzx)        
    
    def compress(self, data, flush=False):
        self._add_input(data)
        self._flushing = flush
        while self._buffered >= self._blocksize:
            self._compress_block()
        if self._buffered > 0 and flush:
            self._compress_block()
        self._reset_input()
        data = self._reset_output()
        rtable = self._reset_rtable()
        return (data, rtable)

    def flush(self):
        self._flushing = True
        if self._buffered > 0:
            self._compress_block()
            self._reset_input()
        data = self._reset_output()
        rtable = self._reset_rtable()
        return (data, rtable)

    def close(self):
        if self._lzx:
            lzx_finish(self._lzx, self._results)
            self._lzx = None
        pass
    
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def __del__(self):
        self.close()


def main(argv=sys.argv):
    wbits, inf, outf = argv[1:]
    with open(inf, 'rb') as f:
        data = f.read()
    with Compressor(int(wbits)) as lzx:
        data, rtable = lzx.compress(data, flush=True)
    print rtable
    with open(outf, 'wb') as f:
        f.write(data)
    return 0
    
if __name__ == '__main__':
    sys.exit(main())
