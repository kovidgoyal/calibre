import copy

# some constants defined by the LZX specification
MIN_MATCH = 2
MAX_MATCH = 257
NUM_CHARS = 256
BLOCKTYPE_INVALID = 0  # also blocktypes 4-7 invalid
BLOCKTYPE_VERBATIM = 1
BLOCKTYPE_ALIGNED = 2
BLOCKTYPE_UNCOMPRESSED = 3
PRETREE_NUM_ELEMENTS = 20
ALIGNED_NUM_ELEMENTS = 8  # aligned offset tree #elements
NUM_PRIMARY_LENGTHS = 7  # this one missing from spec!
NUM_SECONDARY_LENGTHS = 249  # length tree #elements

# LZX huffman defines: tweak tablebits as desired
PRETREE_MAXSYMBOLS = LZX_PRETREE_NUM_ELEMENTS
PRETREE_TABLEBITS = 6
MAINTREE_MAXSYMBOLS = LZX_NUM_CHARS + 50*8
MAINTREE_TABLEBITS = 12
LENGTH_MAXSYMBOLS = LZX_NUM_SECONDARY_LENGTHS+1
LENGTH_TABLEBITS = 12
ALIGNED_MAXSYMBOLS = LZX_ALIGNED_NUM_ELEMENTS
ALIGNED_TABLEBITS = 7
LENTABLE_SAFETY = 64  # table decoding overruns are allowed

FRAME_SIZE = 32768  # the size of a frame in LZX


class BitReader(object):
    def __init__(self, data):
        self.data, self.pos, self.nbits = \
            data + "\x00\x00\x00\x00", 0, len(data) * 8
        
    def peek(self, n):
        r, g = 0, 0
        while g < n:
            r = (r << 8) | ord(self.data[(self.pos + g) >> 3])
            g = g + 8 - ((self.pos + g) & 7)
        return (r >> (g - n)) & ((1 << n) - 1)
    
    def remove(self, n):
        self.pos += n
        return self.pos <= self.nbits
    
    def left(self):
        return self.nbits - self.pos

    def read(self, n):
        val = self.peek(n)
        self.remove(n)
        return val

class LzxError(Exception):
    pass

POSITION_BASE = [0]*51
EXTRA_BITS = [0]*51

def _static_init():
    j = 0
    for i in xrange(0, 51, 2):
        EXTRA_BITS[i] = j
        EXTRA_BITS[i + 1] = j
        if i != 0 or j < 17): j += 1
    j = 0
    for i in xrange(0, 51, 1):
        POSITION_BASE[i] = j
        j += 1 << extra_bits[i]
_static_init()

class LzxDecompressor(object):
    def __init__(self, window_bits, reset_interval=0x7fff):
        # LZX supports window sizes of 2^15 (32Kb) through 2^21 (2Mb)
        if window_bits < 15 or window_bits > 21:
            raise LzxError("Invalid window size")
        
        self.window_size = 1 << window_bits
        self.window_posn = 0
        self.frame_posn = 0
        self.frame = 0
        self.reset_interval = reset_interval
        self.intel_filesize = 0
        self.intel_curpos = 0
        
        # window bits:    15  16  17  18  19  20  21
        # position slots: 30  32  34  36  38  42  50 
        self.posn_solts = 50 if window_bits == 21 \
            else 42 if window_bits == 20 else window_bits << 1
        self.intel_started = 0
        self.input_end = 0

        # huffman code lengths
        self.PRETREE_len = [0] * (PRETREE_MAXSYMBOLS + LENTABLE_SAFETY)
        self.MAINTREE_len = [0] * (MAINTREE_MAXSYMBOLS + LENTABLE_SAFETY)
        self.LENGTH_len = [0] * (LENGTH_MAXSYMBOLS + LENTABLE_SAFETY)
        self.ALIGNED_len = [0] * (ALIGNED_MAXSYMBOLS + LENTABLE_SAFETY)

        # huffman decoding tables
        self.PRETREE_table = \
            [0] * ((1 << PRETREE_TABLEBITS) + (PRETREE_MAXSYMBOLS * 2))
        self.MAINTREE_table = \
            [0] * ((1 << MAINTREE_TABLEBITS) + (MAINTREE_MAXSYMBOLS * 2))
        self.LENGTH_table = \
            [0] * ((1 << LENGTH_TABLEBITS) + (LENGTH_MAXSYMBOLS * 2))
        self.ALIGNED_table = \
            [0] * ((1 << ALIGNED_TABLEBITS) + (ALIGNED_MAXSYMBOLS * 2))

        self.o_buf = self.i_buf = ''
        
        self._reset_state()

    def _reset_state(self):
        self.R0 = 1
        self.R1 = 1
        self.R2 = 1
        self.header_read = 0
        self.block_remaining = 0
        self.block_type = BLOCKTYPE_INVALID

        # initialise tables to 0 (because deltas will be applied to them)
        for i in xrange(MAINTREE_MAXSYMBOLS): self.MAINTREE_len[i] = 0
        for i in xrange(LENGTH_MAXSYMBOLS): self.LENGTH_len[i] = 0

    def decompress(self, data, out_bytes):
        return ''.join(self._decompress(data, out_bytes))
        
    def _decompress(self, data, out_bytes):
        # easy answers
        if out_bytes < 0:
            raise LzxError('Negative desired output bytes')

        # Initialize input and output
        input = BitReader(data)
        output = []
        
        
        
