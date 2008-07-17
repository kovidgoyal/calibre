# Re-modified for use in MS LIT decryption.  Un-reversed the bytebit[] array.
# Substituted Microsoft's absurd modified S-boxes.  Modified the encrypt/decrypt
# methods to handle more than one block at a time.
#
# And lo, all the previous notices follow:

# Modified DES encryption for VNC password authentication.
# Ported from realvnc's java viewer by <cliechti@gmx.net>
# I chose this package name because it is not compatible with the
# original DES algorithm, e.g. found pycrypto.
#
# (C) 2003 chris <cliechti@gmx.net>
# Released as free software under the Python License.
#
# You're free to use it for commercial and noncommercial
# application, modify and redistribute it as long as the
# copyright notices are intact. There are no warranties, not
# even that it does what it says to do ;-)
#
# Original notice following:

# This DES class has been extracted from package Acme.Crypto for use in VNC.
# The bytebit[] array has been reversed so that the most significant bit
# in each byte of the key is ignored, not the least significant.  Also the
# unnecessary odd parity code has been removed.
#
# These changes are:
#  Copyright (C) 1999 AT&T Laboratories Cambridge.  All Rights Reserved.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#

# DesCipher - the DES encryption method
#
# The meat of this code is by Dave Zimmerman <dzimm@widget.com>, and is:
#
# Copyright (c) 1996 Widget Workshop, Inc. All Rights Reserved.
#
# Permission to use, copy, modify, and distribute this software
# and its documentation for NON-COMMERCIAL or COMMERCIAL purposes and
# without fee is hereby granted, provided that this copyright notice is kept 
# intact. 
# 
# WIDGET WORKSHOP MAKES NO REPRESENTATIONS OR WARRANTIES ABOUT THE SUITABILITY
# OF THE SOFTWARE, EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
# TO THE IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE, OR NON-INFRINGEMENT. WIDGET WORKSHOP SHALL NOT BE LIABLE
# FOR ANY DAMAGES SUFFERED BY LICENSEE AS A RESULT OF USING, MODIFYING OR
# DISTRIBUTING THIS SOFTWARE OR ITS DERIVATIVES.
# 
# THIS SOFTWARE IS NOT DESIGNED OR INTENDED FOR USE OR RESALE AS ON-LINE
# CONTROL EQUIPMENT IN HAZARDOUS ENVIRONMENTS REQUIRING FAIL-SAFE
# PERFORMANCE, SUCH AS IN THE OPERATION OF NUCLEAR FACILITIES, AIRCRAFT
# NAVIGATION OR COMMUNICATION SYSTEMS, AIR TRAFFIC CONTROL, DIRECT LIFE
# SUPPORT MACHINES, OR WEAPONS SYSTEMS, IN WHICH THE FAILURE OF THE
# SOFTWARE COULD LEAD DIRECTLY TO DEATH, PERSONAL INJURY, OR SEVERE
# PHYSICAL OR ENVIRONMENTAL DAMAGE ("HIGH RISK ACTIVITIES").  WIDGET WORKSHOP
# SPECIFICALLY DISCLAIMS ANY EXPRESS OR IMPLIED WARRANTY OF FITNESS FOR
# HIGH RISK ACTIVITIES.
#
#
# The rest is:
#
# Copyright (C) 1996 by Jef Poskanzer <jef@acme.com>.  All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#
# Visit the ACME Labs Java page for up-to-date versions of this and other
# fine Java utilities: http://www.acme.com/java/


#/ The DES encryption method.
# <P>
# This is surprisingly fast, for pure Java.  On a SPARC 20, wrapped
# in Acme.Crypto.EncryptedOutputStream or Acme.Crypto.EncryptedInputStream,
# it does around 7000 bytes/second.
# <P>
# Most of this code is by Dave Zimmerman <dzimm@widget.com>, and is
# Copyright (c) 1996 Widget Workshop, Inc.  See the source file for details.
# <P>
# <A HREF="/resources/classes/Acme/Crypto/DesCipher.java">Fetch the software.</A><BR>
# <A HREF="/resources/classes/Acme.tar.Z">Fetch the entire Acme package.</A>
# <P>
# @see Des3Cipher
# @see EncryptedOutputStream
# @see EncryptedInputStream

import struct

class DesCipher:
    # Constructor, byte-array key.
    def __init__(self, key):
        self.setKey(key)

    #/ Set the key.
    def setKey(self, key):
        self.encryptKeys = self.deskey([ord(x) for x in key], 1)
        self.decryptKeys = self.deskey([ord(x) for x in key], 0)

    # Turn an 8-byte key into internal keys.
    def deskey(self, keyBlock, encrypting):
        #~ int i, j, l, m, n;
        pc1m = [0]*56   #new int[56];
        pcr = [0]*56    #new int[56];
        kn = [0]*32     #new int[32];

        for j in range(56):
            l = pc1[j]
            m = l & 07
            pc1m[j] = ((keyBlock[l >> 3] & bytebit[m]) != 0)
        for i in range(16):
            if encrypting:
                m = i << 1
            else:
                m = (15-i) << 1
            n = m + 1
            kn[m] = kn[n] = 0
            for j in range(28):
                l = j + totrot[i]
                if l < 28:
                    pcr[j] = pc1m[l]
                else:
                    pcr[j] = pc1m[l - 28]
            for j in range(28, 56):
                l = j + totrot[i]
                if l < 56:
                    pcr[j] = pc1m[l]
                else:
                    pcr[j] = pc1m[l - 28]
            for j in range(24):
                if pcr[pc2[j]] != 0:
                    kn[m] |= bigbyte[j]
                if pcr[pc2[j+24]] != 0:
                    kn[n] |= bigbyte[j]
        return self.cookey(kn)

    def cookey(self, raw):
        #~ int raw0, raw1;
        #~ int rawi, KnLi;
        #~ int i;
        KnL = [0]*32

        rawi = 0
        KnLi = 0
        for i in range(16):
            raw0 = raw[rawi]
            rawi += 1
            raw1 = raw[rawi]
            rawi += 1
            KnL[KnLi]  = (raw0 & 0x00fc0000L) <<  6
            KnL[KnLi] |= (raw0 & 0x00000fc0L) << 10
            KnL[KnLi] |= (raw1 & 0x00fc0000L) >> 10
            KnL[KnLi] |= (raw1 & 0x00000fc0L) >>  6
            KnLi += 1
            KnL[KnLi]  = (raw0 & 0x0003f000L) << 12
            KnL[KnLi] |= (raw0 & 0x0000003fL) << 16
            KnL[KnLi] |= (raw1 & 0x0003f000L) >>  4
            KnL[KnLi] |= (raw1 & 0x0000003fL)
            KnLi += 1
        return KnL

    # Block encryption routines.
    
    #/ Encrypt a block of eight bytes.
    def encrypt(self, clearText):
        if len(clearText) % 8 != 0:
            raise TypeError, "length must be multiple of block size"
        result = []
        while clearText:
            result.append(struct.pack(
                ">LL", *self.des(struct.unpack(">LL", clearText[:8]),
                                 self.encryptKeys)))
            clearText = clearText[8:]
        return ''.join(result)

    #/ Decrypt a block of eight bytes.
    def decrypt(self, cipherText):
        if len(cipherText) % 8 != 0:
            raise TypeError, "length must be multiple of block size"
        result = []
        while cipherText:
            result.append(struct.pack(
                ">LL", *self.des(struct.unpack(">LL", cipherText[:8]),
                                 self.decryptKeys)))
            cipherText = cipherText[8:]
        return ''.join(result)

    # The DES function.
    def des(self, (leftt, right), keys):
        #~ int fval, work, right, leftt;
        #~ int round
        keysi = 0

        work   = ((leftt >>  4) ^ right) & 0x0f0f0f0fL
        right ^= work
        leftt ^= (work << 4) & 0xffffffffL

        work   = ((leftt >> 16) ^ right) & 0x0000ffffL
        right ^= work
        leftt ^= (work << 16) & 0xffffffffL

        work   = ((right >>  2) ^ leftt) & 0x33333333L
        leftt ^= work
        right ^= (work << 2) & 0xffffffffL

        work   = ((right >>  8) ^ leftt) & 0x00ff00ffL
        leftt ^= work
        right ^= (work << 8) & 0xffffffffL
        right  = ((right << 1) | ((right >> 31) & 1)) & 0xffffffffL

        work   = (leftt ^ right) & 0xaaaaaaaaL
        leftt ^= work
        right ^= work
        leftt  = ((leftt << 1) | ((leftt >> 31) & 1)) & 0xffffffffL

        for round in range(8):
            work   = ((right << 28) | (right >> 4)) & 0xffffffffL
            work  ^= keys[keysi]
            keysi += 1
            fval   = SP7[ work        & 0x0000003fL ]
            fval  |= SP5[(work >>  8) & 0x0000003fL ]
            fval  |= SP3[(work >> 16) & 0x0000003fL ]
            fval  |= SP1[(work >> 24) & 0x0000003fL ]
            work   = right ^ keys[keysi]
            keysi += 1
            fval  |= SP8[ work        & 0x0000003fL ]
            fval  |= SP6[(work >>  8) & 0x0000003fL ]
            fval  |= SP4[(work >> 16) & 0x0000003fL ]
            fval  |= SP2[(work >> 24) & 0x0000003fL ]
            leftt ^= fval
            work   = ((leftt << 28) | (leftt >> 4)) & 0xffffffffL
            work  ^= keys[keysi]
            keysi += 1
            fval   = SP7[ work        & 0x0000003fL ]
            fval  |= SP5[(work >>  8) & 0x0000003fL ]
            fval  |= SP3[(work >> 16) & 0x0000003fL ]
            fval  |= SP1[(work >> 24) & 0x0000003fL ]
            work   = leftt ^ keys[keysi]
            keysi += 1
            fval  |= SP8[ work        & 0x0000003fL ]
            fval  |= SP6[(work >>  8) & 0x0000003fL ]
            fval  |= SP4[(work >> 16) & 0x0000003fL ]
            fval  |= SP2[(work >> 24) & 0x0000003fL ]
            right ^= fval

        right  = ((right << 31) | (right >> 1)) & 0xffffffffL
        work   = (leftt ^ right) & 0xaaaaaaaaL
        leftt ^= work
        right ^= work
        leftt  = ((leftt << 31) | (leftt >> 1)) & 0xffffffffL
        work   = ((leftt >>  8) ^ right) & 0x00ff00ffL
        right ^= work
        leftt ^= (work << 8) & 0xffffffffL
        work   = ((leftt >>  2) ^ right) & 0x33333333L
        right ^= work
        leftt ^= (work << 2) & 0xffffffffL
        work   = ((right >> 16) ^ leftt) & 0x0000ffffL
        leftt ^= work
        right ^= (work << 16) & 0xffffffffL
        work   = ((right >>  4) ^ leftt) & 0x0f0f0f0fL
        leftt ^= work
        right ^= (work << 4) & 0xffffffffL
        return right, leftt

# Tables, permutations, S-boxes, etc.

bytebit = [0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01]

bigbyte = [
    0x800000, 0x400000, 0x200000, 0x100000,
    0x080000, 0x040000, 0x020000, 0x010000,
    0x008000, 0x004000, 0x002000, 0x001000,
    0x000800, 0x000400, 0x000200, 0x000100,
    0x000080, 0x000040, 0x000020, 0x000010,
    0x000008, 0x000004, 0x000002, 0x000001
]

pc1 = [
    56, 48, 40, 32, 24, 16,  8,
     0, 57, 49, 41, 33, 25, 17,
     9,  1, 58, 50, 42, 34, 26,
    18, 10,  2, 59, 51, 43, 35,
    62, 54, 46, 38, 30, 22, 14,
     6, 61, 53, 45, 37, 29, 21,
    13,  5, 60, 52, 44, 36, 28,
    20, 12,  4, 27, 19, 11, 3
]

totrot = [
    1, 2, 4, 6, 8, 10, 12, 14, 15, 17, 19, 21, 23, 25, 27, 28
]

pc2 = [
    13, 16, 10, 23,  0,  4,
    2, 27, 14,  5, 20,  9,
    22, 18, 11, 3 , 25,  7,
    15,  6, 26, 19, 12,  1,
    40, 51, 30, 36, 46, 54,
    29, 39, 50, 44, 32, 47,
    43, 48, 38, 55, 33, 52,
    45, 41, 49, 35, 28, 31,
]

SP1 = [
0x02080800L, 0x00080000L, 0x02000002L, 0x02080802L,
0x02000000L, 0x00080802L, 0x00080002L, 0x02000002L,
0x00080802L, 0x02080800L, 0x02080000L, 0x00000802L,
0x02000802L, 0x02000000L, 0x00000000L, 0x00080002L,
0x00080000L, 0x00000002L, 0x02000800L, 0x00080800L,
0x02080802L, 0x02080000L, 0x00000802L, 0x02000800L,
0x00000002L, 0x00000800L, 0x00080800L, 0x02080002L,
0x00000800L, 0x02000802L, 0x02080002L, 0x00000000L,
0x00000000L, 0x02080802L, 0x02000800L, 0x00080002L,
0x02080800L, 0x00080000L, 0x00000802L, 0x02000800L,
0x02080002L, 0x00000800L, 0x00080800L, 0x02000002L,
0x00080802L, 0x00000002L, 0x02000002L, 0x02080000L,
0x02080802L, 0x00080800L, 0x02080000L, 0x02000802L,
0x02000000L, 0x00000802L, 0x00080002L, 0x00000000L,
0x00080000L, 0x02000000L, 0x02000802L, 0x02080800L,
0x00000002L, 0x02080002L, 0x00000800L, 0x00080802L
]
SP2 = [
0x40108010L, 0x00000000L, 0x00108000L, 0x40100000L,
0x40000010L, 0x00008010L, 0x40008000L, 0x00108000L,
0x00008000L, 0x40100010L, 0x00000010L, 0x40008000L,
0x00100010L, 0x40108000L, 0x40100000L, 0x00000010L,
0x00100000L, 0x40008010L, 0x40100010L, 0x00008000L,
0x00108010L, 0x40000000L, 0x00000000L, 0x00100010L,
0x40008010L, 0x00108010L, 0x40108000L, 0x40000010L,
0x40000000L, 0x00100000L, 0x00008010L, 0x40108010L,
0x00100010L, 0x40108000L, 0x40008000L, 0x00108010L,
0x40108010L, 0x00100010L, 0x40000010L, 0x00000000L,
0x40000000L, 0x00008010L, 0x00100000L, 0x40100010L,
0x00008000L, 0x40000000L, 0x00108010L, 0x40008010L,
0x40108000L, 0x00008000L, 0x00000000L, 0x40000010L,
0x00000010L, 0x40108010L, 0x00108000L, 0x40100000L,
0x40100010L, 0x00100000L, 0x00008010L, 0x40008000L,
0x40008010L, 0x00000010L, 0x40100000L, 0x00108000L
]
SP3 = [
0x04000001L, 0x04040100L, 0x00000100L, 0x04000101L,
0x00040001L, 0x04000000L, 0x04000101L, 0x00040100L,
0x04000100L, 0x00040000L, 0x04040000L, 0x00000001L,
0x04040101L, 0x00000101L, 0x00000001L, 0x04040001L,
0x00000000L, 0x00040001L, 0x04040100L, 0x00000100L,
0x00000101L, 0x04040101L, 0x00040000L, 0x04000001L,
0x04040001L, 0x04000100L, 0x00040101L, 0x04040000L,
0x00040100L, 0x00000000L, 0x04000000L, 0x00040101L,
0x04040100L, 0x00000100L, 0x00000001L, 0x00040000L,
0x00000101L, 0x00040001L, 0x04040000L, 0x04000101L,
0x00000000L, 0x04040100L, 0x00040100L, 0x04040001L,
0x00040001L, 0x04000000L, 0x04040101L, 0x00000001L,
0x00040101L, 0x04000001L, 0x04000000L, 0x04040101L,
0x00040000L, 0x04000100L, 0x04000101L, 0x00040100L,
0x04000100L, 0x00000000L, 0x04040001L, 0x00000101L,
0x04000001L, 0x00040101L, 0x00000100L, 0x04040000L
]
SP4 = [
0x00401008L, 0x10001000L, 0x00000008L, 0x10401008L,
0x00000000L, 0x10400000L, 0x10001008L, 0x00400008L,
0x10401000L, 0x10000008L, 0x10000000L, 0x00001008L,
0x10000008L, 0x00401008L, 0x00400000L, 0x10000000L,
0x10400008L, 0x00401000L, 0x00001000L, 0x00000008L,
0x00401000L, 0x10001008L, 0x10400000L, 0x00001000L,
0x00001008L, 0x00000000L, 0x00400008L, 0x10401000L,
0x10001000L, 0x10400008L, 0x10401008L, 0x00400000L,
0x10400008L, 0x00001008L, 0x00400000L, 0x10000008L,
0x00401000L, 0x10001000L, 0x00000008L, 0x10400000L,
0x10001008L, 0x00000000L, 0x00001000L, 0x00400008L,
0x00000000L, 0x10400008L, 0x10401000L, 0x00001000L,
0x10000000L, 0x10401008L, 0x00401008L, 0x00400000L,
0x10401008L, 0x00000008L, 0x10001000L, 0x00401008L,
0x00400008L, 0x00401000L, 0x10400000L, 0x10001008L,
0x00001008L, 0x10000000L, 0x10000008L, 0x10401000L
]
SP5 = [
0x08000000L, 0x00010000L, 0x00000400L, 0x08010420L,
0x08010020L, 0x08000400L, 0x00010420L, 0x08010000L,
0x00010000L, 0x00000020L, 0x08000020L, 0x00010400L,
0x08000420L, 0x08010020L, 0x08010400L, 0x00000000L,
0x00010400L, 0x08000000L, 0x00010020L, 0x00000420L,
0x08000400L, 0x00010420L, 0x00000000L, 0x08000020L,
0x00000020L, 0x08000420L, 0x08010420L, 0x00010020L,
0x08010000L, 0x00000400L, 0x00000420L, 0x08010400L,
0x08010400L, 0x08000420L, 0x00010020L, 0x08010000L,
0x00010000L, 0x00000020L, 0x08000020L, 0x08000400L,
0x08000000L, 0x00010400L, 0x08010420L, 0x00000000L,
0x00010420L, 0x08000000L, 0x00000400L, 0x00010020L,
0x08000420L, 0x00000400L, 0x00000000L, 0x08010420L,
0x08010020L, 0x08010400L, 0x00000420L, 0x00010000L,
0x00010400L, 0x08010020L, 0x08000400L, 0x00000420L,
0x00000020L, 0x00010420L, 0x08010000L, 0x08000020L
]
SP6 = [
0x80000040L, 0x00200040L, 0x00000000L, 0x80202000L,
0x00200040L, 0x00002000L, 0x80002040L, 0x00200000L,
0x00002040L, 0x80202040L, 0x00202000L, 0x80000000L,
0x80002000L, 0x80000040L, 0x80200000L, 0x00202040L,
0x00200000L, 0x80002040L, 0x80200040L, 0x00000000L,
0x00002000L, 0x00000040L, 0x80202000L, 0x80200040L,
0x80202040L, 0x80200000L, 0x80000000L, 0x00002040L,
0x00000040L, 0x00202000L, 0x00202040L, 0x80002000L,
0x00002040L, 0x80000000L, 0x80002000L, 0x00202040L,
0x80202000L, 0x00200040L, 0x00000000L, 0x80002000L,
0x80000000L, 0x00002000L, 0x80200040L, 0x00200000L,
0x00200040L, 0x80202040L, 0x00202000L, 0x00000040L,
0x80202040L, 0x00202000L, 0x00200000L, 0x80002040L,
0x80000040L, 0x80200000L, 0x00202040L, 0x00000000L,
0x00002000L, 0x80000040L, 0x80002040L, 0x80202000L,
0x80200000L, 0x00002040L, 0x00000040L, 0x80200040L,
]
SP7 = [
0x00004000L, 0x00000200L, 0x01000200L, 0x01000004L,
0x01004204L, 0x00004004L, 0x00004200L, 0x00000000L,
0x01000000L, 0x01000204L, 0x00000204L, 0x01004000L,
0x00000004L, 0x01004200L, 0x01004000L, 0x00000204L,
0x01000204L, 0x00004000L, 0x00004004L, 0x01004204L,
0x00000000L, 0x01000200L, 0x01000004L, 0x00004200L,
0x01004004L, 0x00004204L, 0x01004200L, 0x00000004L,
0x00004204L, 0x01004004L, 0x00000200L, 0x01000000L,
0x00004204L, 0x01004000L, 0x01004004L, 0x00000204L,
0x00004000L, 0x00000200L, 0x01000000L, 0x01004004L,
0x01000204L, 0x00004204L, 0x00004200L, 0x00000000L,
0x00000200L, 0x01000004L, 0x00000004L, 0x01000200L,
0x00000000L, 0x01000204L, 0x01000200L, 0x00004200L,
0x00000204L, 0x00004000L, 0x01004204L, 0x01000000L,
0x01004200L, 0x00000004L, 0x00004004L, 0x01004204L,
0x01000004L, 0x01004200L, 0x01004000L, 0x00004004L,
]
SP8 = [
0x20800080L, 0x20820000L, 0x00020080L, 0x00000000L,
0x20020000L, 0x00800080L, 0x20800000L, 0x20820080L,
0x00000080L, 0x20000000L, 0x00820000L, 0x00020080L,
0x00820080L, 0x20020080L, 0x20000080L, 0x20800000L,
0x00020000L, 0x00820080L, 0x00800080L, 0x20020000L,
0x20820080L, 0x20000080L, 0x00000000L, 0x00820000L,
0x20000000L, 0x00800000L, 0x20020080L, 0x20800080L,
0x00800000L, 0x00020000L, 0x20820000L, 0x00000080L,
0x00800000L, 0x00020000L, 0x20000080L, 0x20820080L,
0x00020080L, 0x20000000L, 0x00000000L, 0x00820000L,
0x20800080L, 0x20020080L, 0x20020000L, 0x00800080L,
0x20820000L, 0x00000080L, 0x00800080L, 0x20020000L,
0x20820080L, 0x00800000L, 0x20800000L, 0x20000080L,
0x00820000L, 0x00020080L, 0x20020080L, 0x20800000L,
0x00000080L, 0x20820000L, 0x00820080L, 0x00000000L,
0x20000000L, 0x20800080L, 0x00020000L, 0x00820080L,
]

def new(key):
    return DesCipher(key)

block_size = 8
key_size = 8

#test only:
if __name__ == '__main__':
    des = DesCipher("\x01\x23\x45\x67\x89\xab\xcd\xef")
    print ''.join(
        "%02x" % ord(x) for x in des.encrypt("Now is t"))
    
