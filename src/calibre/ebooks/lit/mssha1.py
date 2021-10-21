"""
Modified version of SHA-1 used in Microsoft LIT files.

Adapted from the PyPy pure-Python SHA-1 implementation.
"""

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import struct, copy
from polyglot.builtins import long_type

# ======================================================================
# Bit-Manipulation helpers
#
#   _long2bytes() was contributed by Barry Warsaw
#   and is reused here with tiny modifications.
# ======================================================================


def _long2bytesBigEndian(n, blocksize=0):
    """Convert a long integer to a byte string.

    If optional blocksize is given and greater than zero, pad the front
    of the byte string with binary zeros so that the length is a multiple
    of blocksize.
    """

    # After much testing, this algorithm was deemed to be the fastest.
    s = b''
    pack = struct.pack
    while n > 0:
        s = pack('>I', n & 0xffffffff) + s
        n = n >> 32

    # Strip off leading zeros.
    s = s.lstrip(b'\0')

    # Add back some pad bytes. This could be done more efficiently
    # w.r.t. the de-padding being done above, but sigh...
    if blocksize > 0 and len(s) % blocksize:
        s = (blocksize - len(s) % blocksize) * b'\000' + s

    return s


def _bytelist2longBigEndian(blist):
    "Transform a list of characters into a list of longs."

    imax = len(blist)//4
    hl = [0] * imax

    j = 0
    i = 0
    while i < imax:
        b0 = long_type(blist[j]) << 24
        b1 = long_type(blist[j+1]) << 16
        b2 = long_type(blist[j+2]) << 8
        b3 = long_type(blist[j+3])
        hl[i] = b0 | b1 | b2 | b3
        i = i+1
        j = j+4

    return hl


def _rotateLeft(x, n):
    "Rotate x (32 bit) left n bits circular."

    return (x << n) | (x >> (32-n))


# ======================================================================
# The SHA transformation functions
#
# ======================================================================

def f0_19(B, C, D):
    return (B & (C ^ D)) ^ D


def f20_39(B, C, D):
    return B ^ C ^ D


def f40_59(B, C, D):
    return ((B | C) & D) | (B & C)


def f60_79(B, C, D):
    return B ^ C ^ D

# Microsoft's lovely addition...


def f6_42(B, C, D):
    return (B + C) ^ C


f = [f0_19]*20 + [f20_39]*20 + [f40_59]*20 + [f60_79]*20

# ...and delightful changes
f[3] = f20_39
f[6] = f6_42
f[10] = f20_39
f[15] = f20_39
f[26] = f0_19
f[31] = f40_59
f[42] = f6_42
f[51] = f20_39
f[68] = f0_19


# Constants to be used
K = [
    0x5A827999,  # ( 0 <= t <= 19)
    0x6ED9EBA1,  # (20 <= t <= 39)
    0x8F1BBCDC,  # (40 <= t <= 59)
    0xCA62C1D6  # (60 <= t <= 79)
    ]


class mssha1:
    "An implementation of the MD5 hash function in pure Python."

    def __init__(self):
        "Initialisation."

        # Initial message length in bits(!).
        self.length = 0
        self.count = [0, 0]

        # Initial empty message as a sequence of bytes (8 bit characters).
        self.input = bytearray()

        # Call a separate init function, that can be used repeatedly
        # to start from scratch on the same object.
        self.init()

    def init(self):
        "Initialize the message-digest and set all fields to zero."

        self.length = 0
        self.input = []

        # Initial 160 bit message digest (5 times 32 bit).
        # Also changed by Microsoft from standard.
        self.H0 = 0x32107654
        self.H1 = 0x23016745
        self.H2 = 0xC4E680A2
        self.H3 = 0xDC679823
        self.H4 = 0xD0857A34

    def _transform(self, W):
        for t in range(16, 80):
            W.append(_rotateLeft(
                W[t-3] ^ W[t-8] ^ W[t-14] ^ W[t-16], 1) & 0xffffffff)

        A = self.H0
        B = self.H1
        C = self.H2
        D = self.H3
        E = self.H4

        for t in range(0, 80):
            TEMP = _rotateLeft(A, 5) + f[t](B, C, D) + E + W[t] + K[t//20]
            E = D
            D = C
            C = _rotateLeft(B, 30) & 0xffffffff
            B = A
            A = TEMP & 0xffffffff

        self.H0 = (self.H0 + A) & 0xffffffff
        self.H1 = (self.H1 + B) & 0xffffffff
        self.H2 = (self.H2 + C) & 0xffffffff
        self.H3 = (self.H3 + D) & 0xffffffff
        self.H4 = (self.H4 + E) & 0xffffffff

    # Down from here all methods follow the Python Standard Library
    # API of the sha module.

    def update(self, inBuf):
        """Add to the current message.

        Update the mssha1 object with the string arg. Repeated calls
        are equivalent to a single call with the concatenation of all
        the arguments, i.e. s.update(a); s.update(b) is equivalent
        to s.update(a+b).

        The hash is immediately calculated for all full blocks. The final
        calculation is made in digest(). It will calculate 1-2 blocks,
        depending on how much padding we have to add. This allows us to
        keep an intermediate value for the hash, so that we only need to
        make minimal recalculation if we call update() to add more data
        to the hashed string.
        """

        inBuf = bytearray(inBuf)
        leninBuf = long_type(len(inBuf))

        # Compute number of bytes mod 64.
        index = (self.count[1] >> 3) & 0x3F

        # Update number of bits.
        self.count[1] = self.count[1] + (leninBuf << 3)
        if self.count[1] < (leninBuf << 3):
            self.count[0] = self.count[0] + 1
        self.count[0] = self.count[0] + (leninBuf >> 29)

        partLen = 64 - index

        if leninBuf >= partLen:
            self.input[index:] = inBuf[:partLen]
            self._transform(_bytelist2longBigEndian(self.input))
            i = partLen
            while i + 63 < leninBuf:
                self._transform(_bytelist2longBigEndian(inBuf[i:i+64]))
                i = i + 64
            else:
                self.input = inBuf[i:leninBuf]
        else:
            i = 0
            self.input = self.input + inBuf

    def digest(self):
        """Terminate the message-digest computation and return digest.

        Return the digest of the strings passed to the update()
        method so far. This is a 16-byte string which may contain
        non-ASCII characters, including null bytes.
        """

        H0 = self.H0
        H1 = self.H1
        H2 = self.H2
        H3 = self.H3
        H4 = self.H4
        inp = bytearray(self.input)
        count = [] + self.count

        index = (self.count[1] >> 3) & 0x3f

        if index < 56:
            padLen = 56 - index
        else:
            padLen = 120 - index

        padding = b'\200' + (b'\000' * 63)
        self.update(padding[:padLen])

        # Append length (before padding).
        bits = _bytelist2longBigEndian(self.input[:56]) + count

        self._transform(bits)

        # Store state in digest.
        digest = _long2bytesBigEndian(self.H0, 4) + \
                 _long2bytesBigEndian(self.H1, 4) + \
                 _long2bytesBigEndian(self.H2, 4) + \
                 _long2bytesBigEndian(self.H3, 4) + \
                 _long2bytesBigEndian(self.H4, 4)

        self.H0 = H0
        self.H1 = H1
        self.H2 = H2
        self.H3 = H3
        self.H4 = H4
        self.input = inp
        self.count = count

        return digest

    def hexdigest(self):
        """Terminate and return digest in HEX form.

        Like digest() except the digest is returned as a string of
        length 32, containing only hexadecimal digits. This may be
        used to exchange the value safely in email or other non-
        binary environments.
        """
        return ''.join(['%02x' % c for c in bytearray(self.digest())])

    def copy(self):
        """Return a clone object.

        Return a copy ('clone') of the md5 object. This can be used
        to efficiently compute the digests of strings that share
        a common initial substring.
        """

        return copy.deepcopy(self)


# ======================================================================
# Mimic Python top-level functions from standard library API
# for consistency with the md5 module of the standard library.
# ======================================================================

# These are mandatory variables in the module. They have constant values
# in the SHA standard.

digest_size = digestsize = 20
blocksize = 1


def new(arg=None):
    """Return a new mssha1 crypto object.

    If arg is present, the method call update(arg) is made.
    """

    crypto = mssha1()
    if arg:
        crypto.update(arg)

    return crypto


if __name__ == '__main__':
    def main():
        import sys
        file = None
        if len(sys.argv) > 2:
            print("usage: %s [FILE]" % sys.argv[0])
            return
        elif len(sys.argv) < 2:
            file = sys.stdin
        else:
            file = open(sys.argv[1], 'rb')
        context = new()
        data = file.read(16384)
        while data:
            context.update(data)
            data = file.read(16384)
        file.close()
        digest = context.hexdigest().upper()
        for i in range(0, 40, 8):
            print(digest[i:i+8], end=' ')
        print()
    main()
