#@+leo
#@+node:0::@file easy/ezPyCrypto.py
#@+body


#@@language python
#@<< ezPyCrypto declarations >>
#@+node:1::<< ezPyCrypto declarations >>
#@+body
"""
ezPyCrypto - very simple API for military-grade cryptography
in Python.

Designed to be approachable for even total crypto newbies,
this may be the only crypto API for Python you ever need.

Features:
 - Create, Import and Export public keys and public/private keypairs - easy
 - Encrypt and Decrypt arbitrary-sized pieces of data, such as
   strings or files
 - Open up 'streams', so this object can be used as an encrypting/decrypting
   filter - good for socket-based comms and crypto of large files
 - Sign and Verify documents without fuss
 - Create private keys with or without a passphrase
 - Export private keys with a different (or no) passphrase
 - Sensible defaults - no need to specify a zillion options (or any options
   at all) unless you  want to
 - Algorithms include RSA, ElGamal, DSA, ARC2, Blowfish, CAST, DES3, IDEA and RC5
   (default RSA and Blowfish)
 - Choose your own public and session key sizes (or accept defaults)

Contains an easily-used yet versatile cryptography class, called
L{key}, that performs stream and block encryption.

Packaged with a suite of very simple example programs, which demonstrate
ezPyCrypto and speed learning.

ezPyCrypto requires the PyCrypto library (which I have hand-picked from
several different Python crypto APIs, since it's the only
API that doesn't lead its programmers on a wild goose chase
of 3rd party libs, or require dozens/hundreds of lines of
code just to do basic stuff, or lack in documentation.
PyCrypto is available from http://pycrypto.sf.net)

PyCrypto is a very usable and well implemented lower-level
crypto API for Python. C backends give it speed, while
well designed OO interface makes it relatively fast to learn.
Also, it compiles cleanly and smoothly on Linux and Windows
with no dramas.

But I've written this module because PyCrypto is relatively
low-level, and does present a harder learning curve for newbies.

ezPyCrypto is written by David McNab <david@freenet.org.nz>
Released under the GNU General Public License.
No warranty, yada yada

Refer to the documentation for class 'key' for more info.
"""

from pdb import set_trace as trace
import pickle
import types
import base64
import zlib

import Crypto

from Crypto.PublicKey import ElGamal, DSA, RSA
from Crypto.Util.randpool import RandomPool
from Crypto.Util.number import getPrime
from Crypto.Cipher import ARC2, Blowfish, CAST, DES3, IDEA, RC5
from Crypto.Hash import MD5

#@-body
#@-node:1::<< ezPyCrypto declarations >>


#@+others
#@+node:2::exceptions
#@+body
# Define some exceptions for the various problems that can happen

class CryptoKeyError(Exception):
    "Attempt to import invalid key"


#@-body
#@-node:2::exceptions
#@+node:3::class key
#@+body
class key:
    """
    This may well be the only crypto class for Python that you'll ever need.
    Think of this class, and the ezPyCrypto module, as 'cryptography for
    the rest of us'.

    Designed to strike the optimal balance between ease of use, features
    and performance.

    Basic High-level methods:

     - L{encString} - encrypt a string
     - L{decString} - decrypt a string

     - L{encStringToAscii} - encrypt a string to a printable, mailable format
     - L{decStringFromAscii} - decrypt an ascii-format encrypted string

     - L{signString} - produce ascii-format signature of a string
     - L{verifyString} - verify a string against a signature

     - L{importKey} - import public key (and possibly private key too)
     - L{exportKey} - export public key only, as printable mailable string
     - L{exportKeyPrivate} - same, but export private key as well
     - L{makeNewKeys} - generate a new, random private/public key pair

    Middle-level (stream-oriented) methods:

     - L{encStart} - start a stream encryption session
     - L{encNext} - encrypt another piece of data
     - L{encEnd} - finalise stream encryption session

     - L{decStart} - start a stream decryption session
     - L{decNext} - decrypt the next piece of available data
     - L{decEnd} - finalise stream decryption session

    Low-level methods:

     - refer to the source code
    
    Principle of operation:

     - Data is encrypted with choice of symmetric block-mode session cipher
       (or default Blowfish if user doesn't care)
     - CFB block chaining is used for added security - each next block's
       key is affected by the previous block
     - The session key and initial value (IV) are encrypted against an RSA
       or ElGamal public key (user's choice, default RSA)
     - Each block in the stream is prepended with a 'length' byte, indicating
       how many bytes in the decrypted block are significant - needed when
       total data len mod block size is non-zero
     - Format of encrypted data is:
         - public key len - 2 bytes, little-endian - size of public key in bytes
        - public key - public key of recipient
        - block cipher len - unencrypted length byte - size of block cipher in bytes
        - block cipher - encrypted against public key, index into array
          of session algorithms
        - block key len - unencrypted length byte - size of block key in bytes
        - block key - encrypted against public key
        - block IV len - unencrypted length of block cipher IV - IV length in bytes
        - block cipher IV - encrypted against public key, prefixed 1-byte length
        - block1 len - 1 byte - number of significant chars in block1 *
        - block1 data - always 8 bytes, encrypted against session key
        - ...
        - blockn len
        - blockn data
        - If last data block is of the same size as the session cipher blocksize,
          a final byte 0x00 is sent.
    """
    
    #@<< class key declarations >>
    #@+node:1::<< class key declarations >>
    #@+body
    # Various lookup tables for encryption algorithms
    
    _algosPub = {'ElGamal':ElGamal, 'RSA':RSA}
    
    _algosPub1 = {ElGamal:'ElGamal', RSA:'RSA'}
    
    _algosSes = { "ARC2":ARC2, "Blowfish":Blowfish, "CAST":CAST,
                  "DES3":DES3, "IDEA":IDEA, "RC5":RC5}
    _algosSes1 = {'ARC2':0, 'Blowfish':1, 'CAST':2, 'DES3':3, 'IDEA':4, 'RC5':5}
    
    _algosSes2 = [ARC2, Blowfish, CAST, DES3, IDEA, RC5]
    
    _algosSes3 = {ARC2:'ARC2', Blowfish:'Blowfish', CAST:'CAST',
                  DES3:'DES3', IDEA:'IDEA', RC5:'RC5'}
    
    # Generate IV for passphrase encryption
    _passIV = "w8Z4(51fKH#p{!29Q05HWcb@K 6(1qdyv{9|4=+gvji$chw!9$38^2cyGK#;}'@DHx%3)q_skvh4#0*="
    
    # Buffer for yet-to-be-encrypted stream data
    _encBuf = ''
    
    #@-body
    #@-node:1::<< class key declarations >>


    #@+others
    #@+node:2::__init__
    #@+body
    def __init__(self, something = 512, algoPub=None, algoSess=None, **kwds):
        """Constructor. Creates a key object
    
        This constructor, when creating the key object, does one of
        two things:
         1. Creates a completely new keypair, OR
         2. Imports an existing keypair
    
        Arguments:
         1. If new keys are desired:
             - key size in bits (int), default 512 - advise at least 1536
             - algoPub - either 'RSA' or 'ElGamal' (default 'RSA')
             - algoSess - one of 'ARC2', 'Blowfish', 'CAST', 'DES3', 'IDEA', 'RC5',
               (default 'Blowfish')
         2. If importing an existing key or keypair:
             - keyobj (string) - result of a prior exportKey() call
        Keywords:
         - passphrase - default '':
            - If creating new keypair, this passphrase is used to encrypt privkey when
              exporting.
            - If importing a new keypair, the passphrase is used to authenticate and
              grant/deny access to private key
        """
        passphrase = kwds.get('passphrase', '')
    
        if type(something) is types.IntType:
            # which public key algorithm did they choose?
            if algoPub == None:
                algoPub = 'RSA'
            algoP = self._algosPub.get(algoPub, None)
            if algoP == None:
                # Whoops - don't know that one
                raise Exception("AlgoPub must be one of 'ElGamel', 'RSA' or 'DSA'")
            self.algoPub = algoP
            self.algoPname = algoPub
    
            # which session key algorithm?
            if algoSess == None:
                algoSess = 'Blowfish'
            algoS = self._algosSes.get(algoSess, None)
            if algoS == None:
                # Whoops - don't know that session algorithm
                raise Exception("AlgoSess must be one of AES/ARC2/Blowfish/CAST/DES/DES3/IDEA/RC5")
            self.algoSes = algoS
            self.algoSname = algoSess
    
            # organise random data pool
            self.randpool = RandomPool()
            self.randfunc = self.randpool.get_bytes
    
            # now create the keypair
            self.makeNewKeys(something, passphrase=passphrase)
    
        elif type(something) is types.StringType:
            if algoPub != None:
                raise Exception("Don't specify algoPub if importing a key")
            if self.importKey(something, passphrase=passphrase) == False:
                raise CryptoKeyError(
                    "Attempted to import invalid key, or passphrase is bad")
            self.randpool = RandomPool()
            self.randfunc = self.randpool.get_bytes
        else:
            raise Exception("Must pass keysize or importable keys")
    
    #@-body
    #@-node:2::__init__
    #@+node:3::makeNewKeys()
    #@+body
    def makeNewKeys(self, keysize=512, **kwds):
        """
        Creates a new keypair in cipher object, and a new session key
    
        Arguments:
         - keysize (default 512), advise at least 1536
        Returns:
         - None
        Keywords:
         - passphrase - used to secure exported private key - default '' (no passphrase)
    
        Keypair gets stored within the key object. Refer L{exportKey},
        L{exportKeyPrivate} and L{importKey}.
        
        Generally no need to call this yourself, since the constructor
        calls this in cases where you aren't instantiating with an
        importable key.
        """
    
        passphrase = kwds.get('passphrase', '')
        if passphrase == None:
            passphrase = ''
        self.passphrase = passphrase
    
        # set up a public key object
        self.randpool.stir()
        self.k = self.algoPub.generate(keysize, self.randfunc)
        self.randpool.stir()
        self._calcPubBlkSize()
    
        # Generate random session key
        self._genNewSessKey()
    
        # Create session cipher object
        self.randpool.stir()
    
        #trace()
    
        # Create a new block cipher object
        self._initBlkCipher()
    
    #@-body
    #@-node:3::makeNewKeys()
    #@+node:4::importKey()
    #@+body
    def importKey(self, keystring, **kwds):
        """
        Imports a public key or private/public key pair.
    
        (as previously exported from this object
        with the L{exportKey} or L{exportKeyPrivate} methods.)
    
        Arguments:
         - keystring - a string previously imported with
           L{exportKey} or L{exportKeyPrivate}
        Keywords:
         - passphrase - string (default '', meaning 'try to import without passphrase')
        Returns:
         - True if import successful, False if failed
    
        You don't have to call this if you instantiate your key object
        in 'import' mode - ie, by calling it with a previously exported key.
    
        Note - you shouldn't give a 'passphrase' when importing a public key.
        """
    
        passphrase = kwds.get('passphrase', '')
        if passphrase == None:
            passphrase = ''
    
        try:
            #k1 = keystring.split("<StartPycryptoKey>", 1)
            #k2 = k1[1].split("<EndPycryptoKey>")
            ##print "decoding:\n", k2[0]
            #k = base64.decodestring(k2[0])
    
            #trace()
    
            keypickle = self._unwrap("Key", keystring)
            keytuple = pickle.loads(keypickle)
            haspass, size, keyobj = keytuple
    
            if haspass:
                # decrypt against passphrase
                blksiz = 8 # lazy of me
    
                # create temporary symmetric cipher object for passphrase - hardwire to Blowfish
                ppCipher = Blowfish.new(passphrase,
                                        Blowfish.MODE_CFB,
                                        self._passIV[0:blksiz])
                enclen = len(keyobj)
                decpriv = ''
                i = 0
                while i < enclen:
                    decbit = ppCipher.decrypt(keyobj[i:i+blksiz])
                    decpriv += decbit
                    i += blksiz
                keyobj = decpriv[0:size]
        
            self.algoPname, self.k = pickle.loads(keyobj)
            self.algoPub = self._algosPub[self.algoPname]
    
            #raise Exception("Tried to import Invalid Key")
            self._calcPubBlkSize()
            self.passphrase = passphrase
            return True
        except:
            return False
    
    #@-body
    #@-node:4::importKey()
    #@+node:5::exportKey()
    #@+body
    def exportKey(self):
        """
        Exports the public key as a printable string.
    
        Exported keys can be imported elsewhere into MyCipher instances
        with the L{importKey} method.
        
        Note that this object contains only the public key. If you want to
        export the private key as well, call L{exportKeyPrivate} instaead.
    
        Note also that the exported string is Base64-encoded, and safe for sending
        in email.
    
        Arguments:
         - None
        Returns:
         - a base64-encoded string containing an importable key
        """
        rawpub = self._rawPubKey()
        expTuple = (False, None, rawpub)
        expPickle = pickle.dumps(expTuple, True)
        return self._wrap("Key", expPickle)
    
    #@-body
    #@-node:5::exportKey()
    #@+node:6::exportKeyPrivate()
    #@+body
    def exportKeyPrivate(self, **kwds):
        """
        Exports public/private key pair as a printable string.
    
        This string is a binary string consisting of a pickled key object,
        that can be imported elsewhere into MyCipher instances
        with the L{importKey} method.
        
        Note that this object contains the public AND PRIVATE keys.
        Don't EVER email any keys you export with this function (unless you
        know what you're doing, and you encrypt the exported keys against
        another key). When in doubt, use L{exportKey} instead.
    
        Keep your private keys safe at all times. You have been warned.
    
        Note also that the exported string is Base64-encoded, and safe for sending
        in email.
    
        Arguments:
         - None
        Keywords:
         - passphrase - default (None) to using existing passphrase. Set to '' to export
           without passphrase (if this is really what you want to do!)
        Returns:
         - a base64-encoded string containing an importable key
        """
    
        passphrase = kwds.get('passphrase', None)
        if passphrase == None:
            passphrase = self.passphrase
    
        # exported key is a pickle of the tuple:
        # (haspassphrase, keylen, keypickle)
        # if using passphrase, 'keypickle' is encrypted against blowfish, and 'keylen'
        # indicates the number of significant bytes.
    
        rawpriv = pickle.dumps((self.algoPname, self.k), True)
    
        # prepare the key tuple, depending on whether we're using passphrases
        if passphrase != '':
            blksiz = 8 # i'm getting lazy, assuming 8 for blowfish
    
            # encrypt this against passphrase
            ppCipher = Blowfish.new(passphrase,
                                    Blowfish.MODE_CFB,
                                    self._passIV[0:blksiz])
            keylen = len(rawpriv)
            extras = (blksiz - (keylen % blksiz)) % blksiz
            rawpriv += self.randfunc(extras) # padd with random bytes
            newlen = len(rawpriv)
            encpriv = ''
            #print "newlen = %d" % newlen
            #trace()
            i = 0
            while i < newlen:
                rawbit = rawpriv[i:i+blksiz]
                encbit = ppCipher.encrypt(rawpriv[i:i+blksiz])
                #print "i=%d rawbit len=%d, encbit len=%d" % (i, len(rawbit), len(encbit))
                encpriv += encbit
                i += blksiz
            #print "keylen=%d, newlen=%d, len(encpriv)=%d" % (keylen, newlen, len(encpriv))
            #trace()
            keytuple = (True, keylen, encpriv)
        else:
            keytuple = (False, None, rawpriv)
    
        # prepare final pickle, base64 encode, wrap
        keypickle = pickle.dumps(keytuple, True)
        return self._wrap("Key", keypickle)
    
    
    
    #@-body
    #@-node:6::exportKeyPrivate()
    #@+node:7::encString()
    #@+body
    def encString(self, raw):
        """
        Encrypt a string of data
    
        High-level func. encrypts an entire string of data, returning the encrypted
        string as binary.
    
        Arguments:
         - raw string to encrypt
        Returns:
         - encrypted string as binary
    
        Note - the encrypted string can be stored in files, but I'd suggest
        not emailing them - use L{encStringToAscii} instead. The sole advantage
        of this method is that it produces more compact data, and works a bit faster.
        """
    
        # All the work gets done by the stream level
        self.encStart()
    
        # carve up into segments, because Python gets really slow
        # at manipulating large strings
    
        size = len(raw)
        bits = []
        pos = 0
        chunklen = 1024
        while pos < size:
            bits.append(self.encNext(raw[pos:pos+chunklen]))
            pos += chunklen
        bits.append(self.encEnd())
    
        return "".join(bits)
    
    #@-body
    #@-node:7::encString()
    #@+node:8::encStringToAscii()
    #@+body
    def encStringToAscii(self, raw):
        """
        Encrypts a string of data to printable ASCII format
    
        Use this method instead of L{encString}, unless size and speed are
        major issues.
    
        This method returns encrypted data in bracketed  base64 format,
        safe for sending in email.
    
        Arguments:
         - raw - string to encrypt
        Returns:
         - enc - encrypted string, text-wrapped and Base-64 encoded, safe for
           mailing.
    
        There's an overhead with base64-encoding. It costs size, bandwidth and
        speed. Unless you need ascii-safety, use encString() instead.
        """
        enc = self.encString(raw)
        return self._wrap("Message", enc)
    
    #@-body
    #@-node:8::encStringToAscii()
    #@+node:9::decString()
    #@+body
    def decString(self, enc):
        """
        Decrypts a previously encrypted string.
    
        Arguments:
         - enc - string, previously encrypted in binary mode with encString
        Returns:
         - dec - raw decrypted string
        """
    
        chunklen = 1024
    
        size = len(enc)
        bits = []
        pos = 0
    
        self.decStart()
    
        # carve up into small chunks so we don't get any order n^2 on large strings
        while pos < size:
            bits.append(self.decNext(enc[pos:pos+chunklen]))
            pos += chunklen
    
        self.decEnd()
    
        dec = "".join(bits)
        return dec
    
    #@-body
    #@-node:9::decString()
    #@+node:10::decStringFromAscii()
    #@+body
    def decStringFromAscii(self, enc):
        """
        Decrypts a previously encrypted string in ASCII (base64)
        format, as created by encryptAscii()
    
        Arguments:
         - enc - ascii-encrypted string, as previously encrypted with
           encStringToAscii()
        Returns:
         - dec - decrypted string
    
        May generate an exception if the public key of the encrypted string
        doesn't match the public/private keypair in this key object.
    
        To work around this problem, either instantiate a key object with
        the saved keypair, or use the importKey() function.
    
        Exception will also occur if this object is not holding a private key
        (which can happen if you import a key which was previously exported
        via exportKey(). If you get this problem, use exportKeyPrivate() instead
        to export your keypair.
        """
        #trace()
        wrapped = self._unwrap("Message", enc)
        return self.decString(wrapped)
    
    #@-body
    #@-node:10::decStringFromAscii()
    #@+node:11::signString()
    #@+body
    def signString(self, raw):
        """
        Sign a string using private key
    
        Arguments:
         - raw - string to be signed
        Returns:
         - wrapped, base-64 encoded string of signature
    
        Note - private key must already be present in the key object.
        Call L{importKey} for the right private key first if needed.
        """
    
        # hash the key with MD5
        m = MD5.new()
        m.update(raw)
        d = m.digest()
        #print "sign: digest"
        #print repr(d)
    
        # sign the hash with our current public key cipher
        self.randpool.stir()
        k = getPrime(128, self.randfunc)
        self.randpool.stir()
        s = self.k.sign(d, k)
    
        # now wrap into a tuple with the public key cipher
        tup = (self.algoPname, s)
    
        # and pickle it
        p = pickle.dumps(tup, True)
    
        # lastly, wrap it into our base64
        w = self._wrap("Signature", p)
    
        return w
    
    #@-body
    #@-node:11::signString()
    #@+node:12::verifyString()
    #@+body
    def verifyString(self, raw, signature):
        """
        Verifies a string against a signature.
    
        Object must first have the correct public key loaded. (see
        L{importKey}). An exception will occur if this is not the case.
    
        Arguments:
         - raw - string to be verified
         - signature - as produced when key is signed with L{signString}
        Returns:
         - True if signature is authentic, or False if not
        """
    
        # unrwap the signature to a pickled tuple
        p = self._unwrap("Signature", signature)
    
        # unpickle
        algoname, rawsig = pickle.loads(p)
    
        # ensure we've got the right algorithm
        if algoname != self.algoPname:
            return False # wrong algorithm - automatic fail
    
        # hash the string
        m = MD5.new()
        m.update(raw)
        d = m.digest()
        #print "verify: digest"
        #print repr(d)
    
        # now verify the hash against sig
        if self.k.verify(d, rawsig):
            return True # signature valid, or very clever forgery
        else:
            return False # sorry
    
    #@-body
    #@-node:12::verifyString()
    #@+node:13::test()
    #@+body
    def test(self, raw):
        """
        Encrypts, then decrypts a string. What you get back should
        be the same as what you put in.
    
        This is totally useless - it just gives a way to test if this API
        is doing what it should.
        """
        enc = self.encString(raw)
        dec = self.decString(enc)
        return dec
    
    #@-body
    #@-node:13::test()
    #@+node:14::testAscii()
    #@+body
    def testAscii(self, raw):
        """
        Encrypts, then decrypts a string. What you get back should
        be the same as what you put in.
    
        This is totally useless - it just gives a way to test if this API
        is doing what it should.
        """
        enc = self.encStringToAscii(raw)
        dec = self.decStringFromAscii(enc)
        return dec
    
    #@-body
    #@-node:14::testAscii()
    #@+node:15::Stream Methods
    #@+body
    # ---------------------------------------------
    #
    # These methods provide stream-level encryption
    #
    # ---------------------------------------------
    
    
    #@-body
    #@+node:1::encStart()
    #@+body
    def encStart(self):
        """
        Starts a stream encryption session
        Sets up internal buffers for accepting ad-hoc data.
    
        No arguments needed, nothing returned.
        """
    
        # Create a header block of segments, each segment is
        # encrypted against recipient's public key, to enable
        # recipient to decrypt the rest of the stream.
    
        # format of header block is:
        #  - recipient public key
        #  - stream algorithm id
        #  - stream session key
        #  - stream cipher initial value
    
        # Take algorithm index and pad it to the max length
    
        # stick in pubkey
        pubkey = self._rawPubKey()
        pubkeyLen = len(pubkey)
    
        self._tstSessKey0 = ''
        self._tstSessKey1 = ''
        self._tstIV0 = ''
        self._tstIV1 = ''
        self._tstBlk0 = ''
        self._tstBlk1 = ''
    
        #print "pub key len=%d" % pubkeyLen
        
        len0 = pubkeyLen % 256
        len1 = pubkeyLen / 256
    
        # Create algorithms info blk. Structure is:
        #  1byte  - index into session ciphers table
        #  2bytes - session key len, LSB first
        #  1byte  - session IV len, LSB first
    
        while 1:
            self._encHdrs = chr(len0) + chr(len1) + pubkey
    
            # add algorithms index
            algInfo = chr(self._algosSes2.index(self.algoSes))
    
            # Create new session key
            self._genNewSessKey()
    
            # add session key length
            sessKeyLen = len(self.sessKey)
            sessKeyLenL = sessKeyLen % 256
            sessKeyLenH = sessKeyLen / 256
            algInfo += chr(sessKeyLenL) + chr(sessKeyLenH)
    
            # add session IV length
            sessIVLen = len(self.sessIV)
            algInfo += chr(sessIVLen)
            #alg += self.randfunc(self.pubBlkSize - 1) # add random chaff
            #encAlgNum = self._encRawPub(alg)
            encAlgEnc = self._encRawPub(self._padToPubBlkSize(algInfo))
            if encAlgEnc == None:
                continue
            #encAlgLen = len(encAlgNum)
            #self._encHdrs += chr(encAlgLen) + encAlgNum
            self._encHdrs += encAlgEnc
    
            # ensure we can encrypt session key in one hit
            if len(self.sessKey) > self.pubBlkSize:
                raise Exception(
                    "encStart: you need a bigger public key length")
    
            # encrypt and add session key
            sKeyEnc = self._encRawPub(self._padToPubBlkSize(self.sessKey))
            if sKeyEnc == None:
                continue
            # sKeyLen = len(sKeyEnc)
            # self._encHdrs += chr(sKeyLen) + sKeyEnc
            self._encHdrs += sKeyEnc
    
            # encrypt and add session cipher initial value
            sCipherInit = self._encRawPub(self._padToPubBlkSize(self.sessIV))
            if sCipherInit == None:
                continue
            # sCipherIVLen = len(sCipherInit)
            # self._encHdrs += chr(sCipherIVLen) + sCipherInit
            self._encHdrs += sCipherInit
    
            self._tstSessKey0 = self.sessKey
            self._tstIV0 = self.sessIV
    
            # Create a new block cipher object
            self._initBlkCipher()
    
            # ready to go!
            self._encBuf = ''
    
            # success
            break
    
    #@-body
    #@-node:1::encStart()
    #@+node:2::encNext()
    #@+body
    def encNext(self, raw=''):
        """
        Encrypt the next piece of data in a stream.
    
        Arguments:
         - raw - raw piece of data to encrypt
        Returns - one of:
         - '' - not enough data to encrypt yet - stored for later
         - encdata - string of encrypted data
        """
    
        if raw == '':
            return ''
    
        # grab any headers
        enc = self._encHdrs
        self._encHdrs = ''
    
        # add given string to our yet-to-be-encrypted buffer
        self._encBuf += raw
    
        # Loop on data, breaking it up and encrypting it in blocks. Don't
        # touch the last (n mod b) bytes in buffer, where n is total size and
        # b is blocksize
        size = len(self._encBuf)
        next = 0
        while next <= size - self.sesBlkSize: # skip trailing bytes for now
            # extract next block
            blk = self._encBuf[next:next+self.sesBlkSize]
    
            if self._tstBlk0 == '':
                self._tstBlk0 = blk
    
            # encrypt block against session key
            encpart = self.blkCipher.encrypt(blk)
    
            # add length byte and crypted block to internal buffer
            enc += chr(self.sesBlkSize) + encpart
    
            next += self.sesBlkSize
    
        # ditch what we've consumed from buffer
        self._encBuf = self._encBuf[next:]
        
        # return whatever we've encrypted so far
        return enc
    
    #@-body
    #@-node:2::encNext()
    #@+node:3::encEnd()
    #@+body
    def encEnd(self):
        """
        Called to terminate a stream session.
        Encrypts any remaining data in buffer.
    
        Arguments:
         - None
        Returns - one of:
         - last block of data, as a string
        """
    
        buf = ''
        if self._encBuf == '':
            # no trailing data - pass back empty packet
            return chr(0)
    
        # break up remaining data into packets, and encrypt
        while len(self._encBuf) > 0:
    
            # extract session blocksize worth of data from buf
            blk = self._encBuf[0:self.sesBlkSize]
            self._encBuf = self._encBuf[self.sesBlkSize:]
            blklen = len(blk)
    
            # pad if needed
            if blklen < self.sesBlkSize:
                blk += self.randfunc(self.sesBlkSize - blklen)
    
            # encrypt against session key, and add
            buf += chr(blklen)
            buf += self.blkCipher.encrypt(blk)
    
        # clean up and get out
        return buf
    
    #@-body
    #@-node:3::encEnd()
    #@+node:4::decStart()
    #@+body
    def decStart(self):
        """
        Start a stream decryption session.
    
        Call this method first, then feed in pieces of stream data into decNext until
        there's no more data to decrypt
    
        Arguments:
         - None
        Returns:
         - None
        """
    
        # Start with fresh buffer and initial state
        self._decBuf = ''
        self._decState = 'p'
        self._decEmpty = False
    
        self._tstSessKey1 = ''
        self._tstIV1 = ''
        self._tstBlk1 = ''
    
        # states - 'p'->awaiting public key
        #          'c'->awaiting cipher index
        #          'k'->awaiting session key
        #          'i'->awaiting cipher initial data
        #          'd'->awaiting data block
    
    #@-body
    #@-node:4::decStart()
    #@+node:5::decNext()
    #@+body
    def decNext(self, chunk):
        """
        Decrypt the next piece of incoming stream data.
    
        Arguments:
         - chunk - some more of the encrypted stream
        Returns (depending on state)
         - '' - no more decrypted data available just yet
         - data - the next available piece of decrypted data
         - None - session is complete - no more data available
        """
    
        if self._decEmpty:
            return None
    
        # add chunk to our buffer
        self._decBuf += chunk
    
        # bail out if nothing to do
        chunklen = len(self._decBuf)
        if chunklen < 2:
            return ''
    
        # start with empty decryption buffer
        decData = ''
    
        # loop around processing as much data as we can
        #print "decNext: started"
        while 1:
            if self._decState == 'p':
                size = ord(self._decBuf[0]) + 256 * ord(self._decBuf[1])
                if chunklen < size + 2:
                    # don't have full pubkey yet
                    return ''
                else:
                    pubkey = self._decBuf[2:size+2]
                    if not self._testPubKey(pubkey):
                        raise Exception("Can't decrypt - public key mismatch")
    
                    self._decBuf = self._decBuf[size+2:]
                    self._decState = 'c'
                    continue
    
            if self._decState == 'd':
    
                #trace()
    
                # awaiting next data chunk
                sizeReqd = self.sesBlkSize + 1
                size = len(self._decBuf)
                if size < sizeReqd:
                    return decData
                nbytes = ord(self._decBuf[0])
                if nbytes == 0:
                    self._decEmpty = True
                    return None
                blk = self._decBuf[1:sizeReqd]
                self._decBuf = self._decBuf[sizeReqd:]
                decBlk = self.blkCipher.decrypt(blk)
                if self._tstBlk1 == '':
                    self._tstBlk1 = decBlk
                decBlk = decBlk[0:nbytes]
                decData += decBlk
                if nbytes < self.sesBlkSize:
                    self._decEmpty = True
                    return decData
                continue
    
            if len(self._decBuf) < 2:
                return decData
    
            sizeReqd = ord(self._decBuf[0]) + 256 * ord(self._decBuf[1]) + 2
            size = len(self._decBuf)
    
            # bail if we have insufficient data
            if size < sizeReqd:
                return decData
    
            # extract length byte plus block
            #blksize = sizeReqd - 1
            #blk = self._decBuf[1:sizeReqd]
            #self._decBuf = self._decBuf[sizeReqd:]
            blk = self._decBuf[0:sizeReqd]
            self._decBuf = self._decBuf[sizeReqd:]
    
            # state-dependent processing
            if self._decState == 'c':
                #print "decrypting cipher info"
                # awaiting cipher info
                blk = self._decRawPub(blk)
    
                # session cipher index
                c = ord(blk[0])
                self.algoSes = self._algosSes2[c]
    
                # session key len
                self._tmpSessKeyLen = ord(blk[1]) + 256 * ord(blk[2])
    
                # session IV len
                self._tmpSessIVLen = ord(blk[3])
    
                # ignore the rest - it's just chaff
                self._decState = 'k'
                continue
    
            elif self._decState == 'k':
                # awaiting session key
                #print "decrypting session key"
                blk = self._decRawPub(blk)
                self.sessKey = blk[0:self._tmpSessKeyLen]
                self._tstSessKey1 = self.sessKey
                self._decState = 'i'
                continue
    
            elif self._decState == 'i':
                # awaiting cipher start value
                #print "decrypting IV"
                blk = self._decRawPub(blk)
                self.sessIV = blk[0:self._tmpSessIVLen]
                self._tstIV1 = self.sessIV
    
                # Create cipher object, now we have what we need
                self.blkCipher = self.algoSes.new(self.sessKey,
                                                  getattr(self.algoSes, "MODE_CFB"),
                                                  self.sessIV)
                self._calcSesBlkSize()
                self._decState = 'd'
                continue
    
            else:
                raise Exception(
                    "decNext: strange state '%s'" % self._decState[0])
    
    #@-body
    #@-node:5::decNext()
    #@+node:6::decEnd()
    #@+body
    def decEnd(self):
        """
        Ends a stream decryption session.
        """
        # nothing really to do here - decNext() has taken care of it
        # just reset internal state
        self._decBuf = ''
        self._decState = 'c'
    
    #@-body
    #@-node:6::decEnd()
    #@-node:15::Stream Methods
    #@+node:16::Low Level
    #@+node:1::_wrap()
    #@+body
    def _wrap(self, type, msg):
        """
        Encodes message as base64 and wraps with <StartPyCryptoname>/<EndPycryptoname>
        Args:
         - type - string to use in header/footer - eg 'Key', 'Message'
         - msg - binary string to wrap
        """
        return "<StartPycrypto%s>\n%s<EndPycrypto%s>\n" \
                 % (type, base64.encodestring(msg), type)
    
    #@-body
    #@-node:1::_wrap()
    #@+node:2::_unwrap()
    #@+body
    def _unwrap(self, type, msg):
        """
        Unwraps a previously _wrap()'ed message.
        """
        try:
            #trace()
            k1 = msg.split("<StartPycrypto%s>" % type, 1)
            k2 = k1[1].split("<EndPycrypto%s>" % type)
            k = k2[0]
            #print "raw = "
            #print k
            bin = base64.decodestring(k)
            return bin
        except:
            raise Exception("Tried to import Invalid %s" % type)
            self._calcBlkSize()
    
    #@-body
    #@-node:2::_unwrap()
    #@+node:3::_calcPubBlkSize()
    #@+body
    def _calcPubBlkSize(self):
        """
        Determine size of public key
        """
        self.pubBlkSize = (self.k.size() - 7) / 8
    
    #@-body
    #@-node:3::_calcPubBlkSize()
    #@+node:4::_encRawPub()
    #@+body
    def _encRawPub(self, raw):
        """
        Encrypt a small raw string using the public key
        algorithm. Input must not exceed the allowable
        block size.
    
        Arguments:
         - raw - small raw bit of string to encrypt
        Returns:
         - binary representation of encrypted chunk, or None if verify failed
        """
    
        if len(raw) > self.pubBlkSize:
            raise Exception(
                "_encraw: max len %d, passed %d bytes" % (self.pubBlkSize, len(raw)))
    
        self.randpool.stir()
        k = getPrime(128, self.randfunc)
        s = self.k.encrypt(raw, k)
        #d = self.k.decrypt(s)
        #if d != raw:
        #    #print "_encRawPub: decrypt verify fail"
        #    return None
    
        #trace()
    
        # format this tuple into <len><nitems><item1len><item1bytes><item2len><item2bytes>...
        enc = chr(len(s))
        for item in s:
            itemLen = len(item)
            itemLenL = itemLen % 256
            itemLenH = itemLen / 256
            #enc += chr(len(item))
            enc += chr(itemLenL) + chr(itemLenH)
            enc += item
        encLen = len(enc)
        encLenL = encLen % 256
        encLenH = encLen / 256
        #enc = chr(len(enc)) + enc
        enc = chr(encLenL) + chr(encLenH) + enc
    
        #d = self._decRawPub(enc)
        #if d != raw:
        #    print "panic:_encRawPub: decrypt verify fail!"
            
        return enc
    
    
    #@-body
    #@-node:4::_encRawPub()
    #@+node:5::_decRawPub()
    #@+body
    def _decRawPub(self, enc):
        """
        Decrypt a public-key encrypted block, and return the decrypted string
    
        Arguments:
         - enc - the encrypted string, in the format as created by _encRawPub()
        Returns:
         - decrypted block
        """
    
        #trace()
    
        blklen = ord(enc[0]) + 256 * ord(enc[1])
        nparts = ord(enc[2])
        enc = enc[3:]
    
        if blklen != len(enc)+1:
            raise Exception(
                "_decRawPub: bad block length %d, should be %d" % (len(enc), blklen))
        parts = []
        for i in range(nparts):
            partlen = ord(enc[0]) + 256 * ord(enc[1])
            part = enc[2:partlen+2]
            enc = enc[partlen+2:]
            parts.append(part)
        partsTuple = tuple(parts)
        dec = self.k.decrypt(partsTuple)
        return dec
    
    
    
    #@-body
    #@-node:5::_decRawPub()
    #@+node:6::_initBlkCipher()
    #@+body
    def _initBlkCipher(self):
        """
        Create a new block cipher object, set up with a new session key
        and IV
        """
    
        self.blkCipher = self.algoSes.new(self.sessKey,
                                          getattr(self.algoSes, "MODE_CFB"),
                                          self.sessIV)
        self._calcSesBlkSize()
    
    #@-body
    #@-node:6::_initBlkCipher()
    #@+node:7::_calcSesBlkSize()
    #@+body
    def _calcSesBlkSize(self):
        """
        Determine size of session blocks
        """
        self.sesBlkSize = (self.blkCipher.block_size)
    
    #@-body
    #@-node:7::_calcSesBlkSize()
    #@+node:8::_testPubKey()
    #@+body
    def _testPubKey(self, k):
        """
        Checks if binary-encoded key matches this object's pubkey
        """
    
        if k == self._rawPubKey():
            return True
        else:
            return False
    
    #@-body
    #@-node:8::_testPubKey()
    #@+node:9::_rawPubKey()
    #@+body
    def _rawPubKey(self):
        """
        Returns a binary-encoded string of public key
        """
        return pickle.dumps((self.algoPname, self.k.publickey()), True)
    
    #@-body
    #@-node:9::_rawPubKey()
    #@+node:10::_padToPubBlkSize()
    #@+body

    def _padToPubBlkSize(self, raw):
        """
        padToPubBlkSize - pad a string to max size encryptable by public key
    
        Defence against factoring attacks that can uplift a session key when
        that key is encrypted by itself against public key
    
        Arguments:
         - raw - string to pad with random bytes
        returns:
         - padded string. Note - it is the responsibility of the decryption
           code to know how much of the string to extract once decrypted.
        """
    
        rawlen = len(raw)
        extras = self.randfunc(self.pubBlkSize - rawlen)
        #print "padToPubBlkSize: len=%d, added %d bytes of chaff :)" \
        #      % (rawlen, len(extras))
        return raw + extras
    
    #@-body
    #@-node:10::_padToPubBlkSize()
    #@+node:11::_genNewSessKey()
    #@+body
    def _genNewSessKey(self):
        """
        Generate a new random session key
        """
        self.randpool.stir()
        self.sessKey = self.randfunc(32)
        self.randpool.stir()
        self.sessIV = self.randfunc(8)
    
    #@-body
    #@-node:11::_genNewSessKey()
    #@-node:16::Low Level
    #@-others


#@-body
#@-node:3::class key
#@-others



#@-body
#@-node:0::@file easy/ezPyCrypto.py
#@-leo
