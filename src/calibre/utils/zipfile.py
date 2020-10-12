
"""
Read and write ZIP files. Modified by Kovid Goyal to support replacing files in
a zip archive, detecting filename encoding, updating zip files, etc.
"""
import binascii
import io
import os
import re
import shutil
import stat
import struct
import sys
import time
from contextlib import closing

from calibre import sanitize_file_name
from calibre.constants import filesystem_encoding
from calibre.ebooks.chardet import detect
from calibre.ptempfile import SpooledTemporaryFile
from polyglot.builtins import getcwd, map, string_or_bytes, unicode_type, as_bytes

try:
    import zlib  # We may need its compression method
    crc32 = zlib.crc32
except ImportError:
    zlib = None
    crc32 = binascii.crc32

__all__ = ["BadZipfile", "error", "ZIP_STORED", "ZIP_DEFLATED", "is_zipfile",
           "ZipInfo", "ZipFile", "PyZipFile", "LargeZipFile"]


def decode_zip_internal_file_name(fname, flags):
    codec = 'utf-8' if flags & 0x800 else 'cp437'
    return fname.decode(codec, 'replace')


class BadZipfile(Exception):
    pass


class LargeZipFile(Exception):

    """
    Raised when writing a zipfile, the zipfile requires ZIP64 extensions
    and those extensions are disabled.
    """


error = BadZipfile      # The exception raised by this module

ZIP64_LIMIT = (1 << 31) - 1
ZIP_FILECOUNT_LIMIT = (1 << 16) - 1
ZIP_MAX_COMMENT = (1 << 16) - 1

# constants for Zip file compression methods
ZIP_STORED = 0
ZIP_DEFLATED = 8
# Other ZIP compression methods not supported
# For a list see: http://www.winzip.com/wz54.htm

# Below are some formats and associated data for reading/writing headers using
# the struct module.  The names and structures of headers/records are those used
# in the PKWARE description of the ZIP file format:
#     http://www.pkware.com/documents/casestudies/APPNOTE.TXT
# (URL valid as of January 2008)

# The "end of central directory" structure, magic number, size, and indices
# (section V.I in the format document)
structEndArchive = "<4s4H2LH"
stringEndArchive = b"PK\005\006"
sizeEndCentDir = struct.calcsize(structEndArchive)

_ECD_SIGNATURE = 0
_ECD_DISK_NUMBER = 1
_ECD_DISK_START = 2
_ECD_ENTRIES_THIS_DISK = 3
_ECD_ENTRIES_TOTAL = 4
_ECD_SIZE = 5
_ECD_OFFSET = 6
_ECD_COMMENT_SIZE = 7
# These last two indices are not part of the structure as defined in the
# spec, but they are used internally by this module as a convenience
_ECD_COMMENT = 8
_ECD_LOCATION = 9

# The "central directory" structure, magic number, size, and indices
# of entries in the structure (section V.F in the format document)
structCentralDir = "<4s4B4HL2L5H2L"
stringCentralDir = b"PK\001\002"
sizeCentralDir = struct.calcsize(structCentralDir)

# indexes of entries in the central directory structure
_CD_SIGNATURE = 0
_CD_CREATE_VERSION = 1
_CD_CREATE_SYSTEM = 2
_CD_EXTRACT_VERSION = 3
_CD_EXTRACT_SYSTEM = 4
_CD_FLAG_BITS = 5
_CD_COMPRESS_TYPE = 6
_CD_TIME = 7
_CD_DATE = 8
_CD_CRC = 9
_CD_COMPRESSED_SIZE = 10
_CD_UNCOMPRESSED_SIZE = 11
_CD_FILENAME_LENGTH = 12
_CD_EXTRA_FIELD_LENGTH = 13
_CD_COMMENT_LENGTH = 14
_CD_DISK_NUMBER_START = 15
_CD_INTERNAL_FILE_ATTRIBUTES = 16
_CD_EXTERNAL_FILE_ATTRIBUTES = 17
_CD_LOCAL_HEADER_OFFSET = 18

# The "local file header" structure, magic number, size, and indices
# (section V.A in the format document)
structFileHeader = "<4s2B4HL2L2H"
stringFileHeader = b"PK\003\004"
sizeFileHeader = struct.calcsize(structFileHeader)

_FH_SIGNATURE = 0
_FH_EXTRACT_VERSION = 1
_FH_EXTRACT_SYSTEM = 2
_FH_GENERAL_PURPOSE_FLAG_BITS = 3
_FH_COMPRESSION_METHOD = 4
_FH_LAST_MOD_TIME = 5
_FH_LAST_MOD_DATE = 6
_FH_CRC = 7
_FH_COMPRESSED_SIZE = 8
_FH_UNCOMPRESSED_SIZE = 9
_FH_FILENAME_LENGTH = 10
_FH_EXTRA_FIELD_LENGTH = 11

# The "Zip64 end of central directory locator" structure, magic number, and size
structEndArchive64Locator = "<4sLQL"
stringEndArchive64Locator = b"PK\x06\x07"
sizeEndCentDir64Locator = struct.calcsize(structEndArchive64Locator)

# The "Zip64 end of central directory" record, magic number, size, and indices
# (section V.G in the format document)
structEndArchive64 = "<4sQ2H2L4Q"
stringEndArchive64 = b"PK\x06\x06"
sizeEndCentDir64 = struct.calcsize(structEndArchive64)

_CD64_SIGNATURE = 0
_CD64_DIRECTORY_RECSIZE = 1
_CD64_CREATE_VERSION = 2
_CD64_EXTRACT_VERSION = 3
_CD64_DISK_NUMBER = 4
_CD64_DISK_NUMBER_START = 5
_CD64_NUMBER_ENTRIES_THIS_DISK = 6
_CD64_NUMBER_ENTRIES_TOTAL = 7
_CD64_DIRECTORY_SIZE = 8
_CD64_OFFSET_START_CENTDIR = 9


def decode_arcname(name):
    if not isinstance(name, unicode_type):
        try:
            name = name.decode('utf-8')
        except Exception:
            res = detect(name)
            encoding = res['encoding']
            try:
                name = name.decode(encoding)
            except Exception:
                name = name.decode('utf-8', 'replace')
    return name

# Added by Kovid to reset timestamp to default if it overflows the DOS
# limits


def fixtimevar(val):
    if val < 0 or val > 0xffff:
        val = 0
    return val


def _check_zipfile(fp):
    try:
        if _EndRecData(fp):
            return True         # file has correct magic number
    except IOError:
        pass
    return False


def is_zipfile(filename):
    """Quickly see if a file is a ZIP file by checking the magic number.

    The filename argument may be a file or file-like object too.
    """
    result = False
    try:
        if hasattr(filename, "read"):
            result = _check_zipfile(filename)
        else:
            with open(filename, "rb") as fp:
                result = _check_zipfile(fp)
    except IOError:
        pass
    return result


def _EndRecData64(fpin, offset, endrec):
    """
    Read the ZIP64 end-of-archive records and use that to update endrec
    """
    try:
        fpin.seek(offset - sizeEndCentDir64Locator, 2)
    except IOError:
        # If the seek fails, the file is not large enough to contain a ZIP64
        # end-of-archive record, so just return the end record we were given.
        return endrec

    data = fpin.read(sizeEndCentDir64Locator)
    sig, diskno, reloff, disks = struct.unpack(structEndArchive64Locator, data)
    if sig != stringEndArchive64Locator:
        return endrec

    if diskno != 0 or disks != 1:
        raise BadZipfile("zipfiles that span multiple disks are not supported")

    # Assume no 'zip64 extensible data'
    fpin.seek(offset - sizeEndCentDir64Locator - sizeEndCentDir64, 2)
    data = fpin.read(sizeEndCentDir64)
    sig, sz, create_version, read_version, disk_num, disk_dir, \
            dircount, dircount2, dirsize, diroffset = \
            struct.unpack(structEndArchive64, data)
    if sig != stringEndArchive64:
        return endrec

    # Update the original endrec using data from the ZIP64 record
    endrec[_ECD_SIGNATURE] = sig
    endrec[_ECD_DISK_NUMBER] = disk_num
    endrec[_ECD_DISK_START] = disk_dir
    endrec[_ECD_ENTRIES_THIS_DISK] = dircount
    endrec[_ECD_ENTRIES_TOTAL] = dircount2
    endrec[_ECD_SIZE] = dirsize
    endrec[_ECD_OFFSET] = diroffset
    return endrec


def _EndRecData(fpin):
    """Return data from the "End of Central Directory" record, or None.

    The data is a list of the nine items in the ZIP "End of central dir"
    record followed by a tenth item, the file seek offset of this record."""

    # Determine file size
    fpin.seek(0, 2)
    filesize = fpin.tell()

    # Check to see if this is ZIP file with no archive comment (the
    # "end of central directory" structure should be the last item in the
    # file if this is the case).
    try:
        fpin.seek(-sizeEndCentDir, 2)
    except IOError:
        return None
    data = fpin.read()
    if data[0:4] == stringEndArchive and data[-2:] == b"\000\000":
        # the signature is correct and there's no comment, unpack structure
        endrec = struct.unpack(structEndArchive, data)
        endrec=list(endrec)

        # Append a blank comment and record start offset
        endrec.append(b"")
        endrec.append(filesize - sizeEndCentDir)

        # Try to read the "Zip64 end of central directory" structure
        return _EndRecData64(fpin, -sizeEndCentDir, endrec)

    # Either this is not a ZIP file, or it is a ZIP file with an archive
    # comment.  Search the end of the file for the "end of central directory"
    # record signature. The comment is the last item in the ZIP file and may be
    # up to 64K long.  It is assumed that the "end of central directory" magic
    # number does not appear in the comment.
    maxCommentStart = max(filesize - (1 << 16) - sizeEndCentDir, 0)
    fpin.seek(maxCommentStart, 0)
    data = fpin.read()
    start = data.rfind(stringEndArchive)
    if start >= 0:
        # found the magic number; attempt to unpack and interpret
        recData = data[start:start+sizeEndCentDir]
        endrec = list(struct.unpack(structEndArchive, recData))
        comment = data[start+sizeEndCentDir:]
        # check that comment length is correct
        # Kovid: Added == 0 check as some zip files apparently dont set this
        if endrec[_ECD_COMMENT_SIZE] == 0 or endrec[_ECD_COMMENT_SIZE] == len(comment):
            # Append the archive comment and start offset
            endrec.append(comment)
            endrec.append(maxCommentStart + start)

            # Try to read the "Zip64 end of central directory" structure
            return _EndRecData64(fpin, maxCommentStart + start - filesize,
                                 endrec)

    # Unable to find a valid end of central directory structure
    return


class ZipInfo (object):

    """Class with attributes describing each file in the ZIP archive."""

    __slots__ = (
            'orig_filename',
            'filename',
            'date_time',
            'compress_type',
            'comment',
            'extra',
            'create_system',
            'create_version',
            'extract_version',
            'reserved',
            'flag_bits',
            'volume',
            'internal_attr',
            'external_attr',
            'header_offset',
            'CRC',
            'compress_size',
            'file_size',
            '_raw_time',
            'file_offset',
        )

    def __init__(self, filename="NoName", date_time=(1980,1,1,0,0,0)):
        self.orig_filename = filename   # Original file name in archive

        # Terminate the file name at the first null byte.  Null bytes in file
        # names are used as tricks by viruses in archives.
        null_byte = filename.find(b'\0' if isinstance(filename, bytes) else '\0')
        if null_byte >= 0:
            filename = filename[0:null_byte]
        # This is used to ensure paths in generated ZIP files always use
        # forward slashes as the directory separator, as required by the
        # ZIP format specification.
        if os.sep != '/':
            os_sep, sep = os.sep, '/'
            if isinstance(filename, bytes):
                os_sep, sep = as_bytes(os_sep), b'/'
            if os_sep in filename:
                filename = filename.replace(os_sep, sep)

        self.filename = filename        # Normalized file name
        self.date_time = date_time      # year, month, day, hour, min, sec
        # Standard values:
        self.compress_type = ZIP_STORED  # Type of compression for the file
        self.comment = b""               # Comment for each file
        self.extra = b""                 # ZIP extra data
        if sys.platform == 'win32':
            self.create_system = 0          # System which created ZIP archive
        else:
            # Assume everything else is unix-y
            self.create_system = 3          # System which created ZIP archive
        self.create_version = 20        # Version which created ZIP archive
        self.extract_version = 20       # Version needed to extract archive
        self.reserved = 0               # Must be zero
        self.flag_bits = 0              # ZIP flag bits
        self.volume = 0                 # Volume number of file header
        self.internal_attr = 0          # Internal attributes
        self.external_attr = 0          # External file attributes
        self.file_offset   = 0
        # Other attributes are set by class ZipFile:
        # header_offset         Byte offset to the file header
        # CRC                   CRC-32 of the uncompressed file
        # compress_size         Size of the compressed file
        # file_size             Size of the uncompressed file

    def FileHeader(self):
        """Return the per-file header as a string."""
        dt = self.date_time
        dosdate = (dt[0] - 1980) << 9 | dt[1] << 5 | dt[2]
        dostime = dt[3] << 11 | dt[4] << 5 | (dt[5] // 2)

        if self.flag_bits & 0x08:
            # Set these to zero because we write them after the file data
            CRC = compress_size = file_size = 0
        else:
            CRC = self.CRC
            compress_size = self.compress_size
            file_size = self.file_size

        extra = self.extra

        if file_size > ZIP64_LIMIT or compress_size > ZIP64_LIMIT:
            # File is larger than what fits into a 4 byte integer,
            # fall back to the ZIP64 extension
            fmt = '<HHQQ'
            extra = extra + struct.pack(fmt,
                    1, struct.calcsize(fmt)-4, file_size, compress_size)
            file_size = 0xffffffff
            compress_size = 0xffffffff
            self.extract_version = max(45, self.extract_version)
            self.create_version = max(45, self.extract_version)

        filename, flag_bits = self._encodeFilenameFlags()
        header = struct.pack(structFileHeader, stringFileHeader,
                 self.extract_version, self.reserved, flag_bits,
                 self.compress_type, fixtimevar(dostime), fixtimevar(dosdate), CRC,
                 compress_size, file_size,
                 len(filename), len(extra))
        return header + filename + extra

    def _encodeFilenameFlags(self):
        if isinstance(self.filename, unicode_type):
            return self.filename.encode('utf-8'), self.flag_bits | 0x800
        else:
            return self.filename, self.flag_bits

    def _decodeExtra(self):
        # Try to decode the extra field.
        extra = self.extra
        unpack = struct.unpack
        while extra:
            tp, ln = unpack('<HH', extra[:4])
            if tp == 1:
                if ln >= 24:
                    counts = unpack('<QQQ', extra[4:28])
                elif ln == 16:
                    counts = unpack('<QQ', extra[4:20])
                elif ln == 8:
                    counts = unpack('<Q', extra[4:12])
                elif ln == 0:
                    counts = ()
                else:
                    raise RuntimeError("Corrupt extra field %s"%(ln,))

                idx = 0

                # ZIP64 extension (large files and/or large archives)
                if self.file_size in (0xffffffffffffffff, 0xffffffff):
                    self.file_size = counts[idx]
                    idx += 1

                if self.compress_size == 0xFFFFFFFF:
                    self.compress_size = counts[idx]
                    idx += 1

                if self.header_offset == 0xffffffff:
                    self.header_offset = counts[idx]
                    idx+=1

            extra = extra[ln+4:]


class _ZipDecrypter:

    """Class to handle decryption of files stored within a ZIP archive.

    ZIP supports a password-based form of encryption. Even though known
    plaintext attacks have been found against it, it is still useful
    to be able to get data out of such a file.

    Usage:
        zd = _ZipDecrypter(mypwd)
        plain_char = zd(cypher_char)
        plain_text = map(zd, cypher_text)
    """

    def _GenerateCRCTable():
        """Generate a CRC-32 table.

        ZIP encryption uses the CRC32 one-byte primitive for scrambling some
        internal keys. We noticed that a direct implementation is faster than
        relying on binascii.crc32().
        """
        poly = 0xedb88320
        table = [0] * 256
        for i in range(256):
            crc = i
            for j in range(8):
                if crc & 1:
                    crc = ((crc >> 1) & 0x7FFFFFFF) ^ poly
                else:
                    crc = ((crc >> 1) & 0x7FFFFFFF)
            table[i] = crc
        return table
    crctable = _GenerateCRCTable()

    def _crc32(self, ch, crc):
        """Compute the CRC32 primitive on one byte."""
        return ((crc >> 8) & 0xffffff) ^ self.crctable[(crc ^ ch) & 0xff]

    def __init__(self, pwd):
        self.key0 = 305419896
        self.key1 = 591751049
        self.key2 = 878082192
        for p in pwd:
            self._UpdateKeys(p)

    def _UpdateKeys(self, c):
        self.key0 = self._crc32(c, self.key0)
        self.key1 = (self.key1 + (self.key0 & 255)) & 4294967295
        self.key1 = (self.key1 * 134775813 + 1) & 4294967295
        self.key2 = self._crc32(((self.key1 >> 24) & 255), self.key2)

    def __call__(self, c):
        """Decrypt a single byte."""
        k = self.key2 | 2
        c = c ^ (((k * (k^1)) >> 8) & 255)
        self._UpdateKeys(c)
        return c


class ZipExtFile(io.BufferedIOBase):

    """File-like object for reading an archive member.
       Is returned by ZipFile.open().
    """

    # Max size supported by decompressor.
    MAX_N = 1 << 31 - 1

    # Read from compressed files in 4k blocks.
    MIN_READ_SIZE = 4096

    # Search for universal newlines or line chunks.
    PATTERN = re.compile(br'^(?P<chunk>[^\r\n]+)|(?P<newline>\n|\r\n?)')

    def __init__(self, fileobj, mode, zipinfo, decrypter=None):
        self._fileobj = fileobj
        self._decrypter = decrypter
        self._orig_pos = fileobj.tell()

        self._compress_type = zipinfo.compress_type
        self._compress_size = zipinfo.compress_size
        self._compress_left = zipinfo.compress_size

        if self._compress_type == ZIP_DEFLATED:
            self._decompressor = zlib.decompressobj(-15)
        self._unconsumed = b''

        self._readbuffer = b''
        self._offset = 0

        self._universal = 'U' in mode
        self.newlines = None

        # Adjust read size for encrypted files since the first 12 bytes
        # are for the encryption/password information.
        if self._decrypter is not None:
            self._compress_left -= 12

        self.mode = mode
        self.name = zipinfo.filename

        if hasattr(zipinfo, 'CRC'):
            self._expected_crc = zipinfo.CRC
            self._running_crc = crc32(b'') & 0xffffffff
        else:
            self._expected_crc = None

    def readline(self, limit=-1):
        """Read and return a line from the stream.

        If limit is specified, at most limit bytes will be read.
        """

        if not self._universal and limit < 0:
            # Shortcut common case - newline found in buffer.
            i = self._readbuffer.find(b'\n', self._offset) + 1
            if i > 0:
                line = self._readbuffer[self._offset: i]
                self._offset = i
                return line

        if not self._universal:
            return io.BufferedIOBase.readline(self, limit)

        line = b''
        while limit < 0 or len(line) < limit:
            readahead = self.peek(2)
            if not readahead:
                return line

            #
            # Search for universal newlines or line chunks.
            #
            # The pattern returns either a line chunk or a newline, but not
            # both. Combined with peek(2), we are assured that the sequence
            # '\r\n' is always retrieved completely and never split into
            # separate newlines - '\r', '\n' due to coincidental readaheads.
            #
            match = self.PATTERN.search(readahead)
            newline = match.group('newline')
            if newline is not None:
                if self.newlines is None:
                    self.newlines = []
                if newline not in self.newlines:
                    self.newlines.append(newline)
                self._offset += len(newline)
                return line + b'\n'

            chunk = match.group('chunk')
            if limit >= 0:
                chunk = chunk[: limit - len(line)]

            self._offset += len(chunk)
            line += chunk

        return line

    def peek(self, n=1):
        """Returns buffered bytes without advancing the position."""
        if n > len(self._readbuffer) - self._offset:
            chunk = self.read(n)
            self._offset -= len(chunk)

        # Return up to 512 bytes to reduce allocation overhead for tight loops.
        return self._readbuffer[self._offset: self._offset + 512]

    def readable(self):
        return True

    def read(self, n=-1):
        """Read and return up to n bytes.
        If the argument is omitted, None, or negative, data is read and returned until EOF is reached..
        """
        buf = b''
        if n is None:
            n = -1
        while True:
            if n < 0:
                data = self.read1(n)
            elif n > len(buf):
                data = self.read1(n - len(buf))
            else:
                return buf
            if len(data) == 0:
                return buf
            buf += data

    def _update_crc(self, newdata, eof):
        # Update the CRC using the given data.
        if self._expected_crc is None:
            # No need to compute the CRC if we don't have a reference value
            return
        self._running_crc = crc32(newdata, self._running_crc) & 0xffffffff
        # Check the CRC if we're at the end of the file
        if eof and self._running_crc != self._expected_crc:
            raise BadZipfile("Bad CRC-32 for file %r" % self.name)

    def read1(self, n):
        """Read up to n bytes with at most one read() system call."""

        # Simplify algorithm (branching) by transforming negative n to large n.
        if n < 0 or n is None:
            n = self.MAX_N

        # Bytes available in read buffer.
        len_readbuffer = len(self._readbuffer) - self._offset

        # Read from file.
        if self._compress_left > 0 and n > len_readbuffer + len(self._unconsumed):
            nbytes = n - len_readbuffer - len(self._unconsumed)
            nbytes = max(nbytes, self.MIN_READ_SIZE)
            nbytes = min(nbytes, self._compress_left)

            data = self._fileobj.read(nbytes)
            self._compress_left -= len(data)

            if data and self._decrypter is not None:
                data = b''.join(bytes(bytearray(map(self._decrypter, bytearray(data)))))

            if self._compress_type == ZIP_STORED:
                self._update_crc(data, eof=(self._compress_left==0))
                self._readbuffer = self._readbuffer[self._offset:] + data
                self._offset = 0
            else:
                # Prepare deflated bytes for decompression.
                self._unconsumed += data

        # Handle unconsumed data.
        if (len(self._unconsumed) > 0 and n > len_readbuffer and
            self._compress_type == ZIP_DEFLATED):
            data = self._decompressor.decompress(
                self._unconsumed,
                max(n - len_readbuffer, self.MIN_READ_SIZE)
            )

            self._unconsumed = self._decompressor.unconsumed_tail
            eof = len(self._unconsumed) == 0 and self._compress_left == 0
            if eof:
                data += self._decompressor.flush()

            self._update_crc(data, eof=eof)
            self._readbuffer = self._readbuffer[self._offset:] + data
            self._offset = 0

        # Read from buffer.
        data = self._readbuffer[self._offset: self._offset + n]
        self._offset += len(data)
        return data

    def read_raw(self):
        pos = self._fileobj.tell()
        self._fileobj.seek(self._orig_pos)
        bytes_to_read = self._compress_size
        if self._decrypter is not None:
            bytes_to_read -= 12
        raw = b''

        if bytes_to_read > 0:
            raw = self._fileobj.read(bytes_to_read)
        self._fileobj.seek(pos)
        return raw


class ZipFile:

    """ Class with methods to open, read, write, close, list and update zip files.

    z = ZipFile(file, mode="r", compression=ZIP_STORED, allowZip64=False)

    file: Either the path to the file, or a file-like object.
          If it is a path, the file will be opened and closed by ZipFile.
    mode: The mode can be either read "r", write "w" or append "a".
    compression: ZIP_STORED (no compression) or ZIP_DEFLATED (requires zlib).
    allowZip64: if True ZipFile will create files with ZIP64 extensions when
                needed, otherwise it will raise an exception when this would
                be necessary.

    """

    fp = None                   # Set here since __del__ checks it

    def __init__(self, file, mode="r", compression=ZIP_DEFLATED, allowZip64=True):
        """Open the ZIP file with mode read "r", write "w" or append "a"."""
        if mode not in ("r", "w", "a"):
            raise RuntimeError('ZipFile() requires mode "r", "w", or "a" not %s'%mode)

        if compression == ZIP_STORED:
            pass
        elif compression == ZIP_DEFLATED:
            if not zlib:
                raise RuntimeError(
                      "Compression requires the (missing) zlib module")
        else:
            raise RuntimeError("The compression method %s is not supported" % compression)

        self._allowZip64 = allowZip64
        self._didModify = False
        self.debug = 0  # Level of printing: 0 through 3
        self.NameToInfo = {}    # Find file info given name
        self.filelist = []      # List of ZipInfo instances for archive
        self.extract_mapping = {}
        self.compression = compression  # Method of compression
        self.mode = key = mode.replace('b', '')[0]
        self.pwd = None
        self.comment = b''

        # Check if we were passed a file-like object
        if isinstance(file, string_or_bytes):
            self._filePassed = 0
            self.filename = file
            modeDict = {'r' : 'rb', 'w': 'wb', 'a' : 'r+b'}
            try:
                self.fp = open(file, modeDict[mode])
            except IOError:
                if mode == 'a':
                    mode = key = 'w'
                    self.fp = open(file, modeDict[mode])
                else:
                    raise
        else:
            self._filePassed = 1
            self.fp = file
            self.filename = getattr(file, 'name', None)

        if key == 'r':
            self._GetContents()
        elif key == 'w':
            # set the modified flag so central directory gets written
            # even if no files are added to the archive
            self._didModify = True
        elif key == 'a':
            try:
                # See if file is a zip file
                self._RealGetContents()
                self._calculate_file_offsets()
                # seek to start of directory and overwrite
                self.fp.seek(self.start_dir, 0)
            except BadZipfile:
                # file is not a zip file, just append
                self.fp.seek(0, 2)

                # set the modified flag so central directory gets written
                # even if no files are added to the archive
                self._didModify = True
        else:
            if not self._filePassed:
                self.fp.close()
                self.fp = None
            raise RuntimeError('Mode must be "r", "w" or "a"')

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def _GetContents(self):
        """Read the directory, making sure we close the file if the format
        is bad."""
        try:
            self._RealGetContents()
        except BadZipfile:
            if not self._filePassed:
                self.fp.close()
                self.fp = None
            raise

    def _RealGetContents(self):
        """Read in the table of contents for the ZIP file."""
        fp = self.fp
        try:
            endrec = _EndRecData(fp)
        except IOError:
            raise BadZipfile("File is not a zip file")
        if not endrec:
            raise BadZipfile("File is not a zip file")
        if self.debug > 1:
            print(endrec)
        size_cd = endrec[_ECD_SIZE]             # bytes in central directory
        offset_cd = endrec[_ECD_OFFSET]         # offset of central directory
        self.comment = endrec[_ECD_COMMENT]     # archive comment

        # "concat" is zero, unless zip was concatenated to another file
        concat = endrec[_ECD_LOCATION] - size_cd - offset_cd
        if endrec[_ECD_SIGNATURE] == stringEndArchive64:
            # If Zip64 extension structures are present, account for them
            concat -= (sizeEndCentDir64 + sizeEndCentDir64Locator)

        if self.debug > 2:
            inferred = concat + offset_cd
            print("given, inferred, offset", offset_cd, inferred, concat)
        # self.start_dir:  Position of start of central directory
        self.start_dir = offset_cd + concat
        fp.seek(self.start_dir, 0)
        data = fp.read(size_cd)
        fp = io.BytesIO(data)
        total = 0
        while total < size_cd:
            centdir = fp.read(sizeCentralDir)
            if centdir[0:4] != stringCentralDir:
                raise BadZipfile("Bad magic number for central directory")
            centdir = struct.unpack(structCentralDir, centdir)
            if self.debug > 2:
                print(centdir)
            filename = fp.read(centdir[_CD_FILENAME_LENGTH])
            flags = centdir[5]
            filename = decode_zip_internal_file_name(filename, flags)
            # Create ZipInfo instance to store file information
            x = ZipInfo(filename)
            x.extra = fp.read(centdir[_CD_EXTRA_FIELD_LENGTH])
            x.comment = fp.read(centdir[_CD_COMMENT_LENGTH])
            x.header_offset = centdir[_CD_LOCAL_HEADER_OFFSET]
            (x.create_version, x.create_system, x.extract_version, x.reserved,
                x.flag_bits, x.compress_type, t, d,
                x.CRC, x.compress_size, x.file_size) = centdir[1:12]
            x.volume, x.internal_attr, x.external_attr = centdir[15:18]
            # Convert date/time code to (year, month, day, hour, min, sec)
            x._raw_time = t
            x.date_time = ((d>>9)+1980, (d>>5)&0xF, d&0x1F,
                                     t>>11, (t>>5)&0x3F, (t&0x1F) * 2)

            x._decodeExtra()
            x.header_offset = x.header_offset + concat
            self.filelist.append(x)
            self.NameToInfo[x.filename] = x

            # update total bytes read from central directory
            total = (total + sizeCentralDir + centdir[_CD_FILENAME_LENGTH] +
                     centdir[_CD_EXTRA_FIELD_LENGTH] +
                     centdir[_CD_COMMENT_LENGTH])

            if self.debug > 2:
                print("total", total)

    def _calculate_file_offsets(self):
        for zip_info in self.filelist:
            self.fp.seek(zip_info.header_offset, 0)
            fheader = self.fp.read(30)
            if fheader[0:4] != stringFileHeader:
                raise BadZipfile("Bad magic number for file header")
            fheader = struct.unpack(structFileHeader, fheader)
            # file_offset is computed here, since the extra field for
            # the central directory and for the local file header
            # refer to different fields, and they can have different
            # lengths
            file_offset = (zip_info.header_offset + 30 +
                           fheader[_FH_FILENAME_LENGTH] +
                           fheader[_FH_EXTRA_FIELD_LENGTH])
            fname = self.fp.read(fheader[_FH_FILENAME_LENGTH])
            fname = decode_zip_internal_file_name(fname, zip_info.flag_bits)
            if fname != zip_info.orig_filename:
                raise RuntimeError(
                      'File name in directory "%s" and header "%s" differ.' % (
                          zip_info.orig_filename, fname))

            zip_info.file_offset = file_offset

    def replace(self, filename, arcname=None, compress_type=None):
        """Delete arcname, and put the bytes from filename into the
        archive under the name arcname."""
        deleteName = arcname
        if deleteName is None:
            deleteName = filename
        self.delete(deleteName)
        self.write(filename, arcname, compress_type)

    def replacestr(self, zinfo, byts):
        """Delete zinfo.filename, and write a new file into the archive. The
        contents is the string 'bytes'."""
        self.delete(zinfo.filename)
        self.writestr(zinfo, byts)

    def delete(self, name):
        """Delete the file from the archive. If it appears multiple
        times only the first instance will be deleted."""
        for i in range(0, len(self.filelist)):
            if self.filelist[i].filename == name:
                if self.debug:
                    print("Removing", name)
                deleted_offset = self.filelist[i].header_offset
                deleted_size   = (self.filelist[i].file_offset - self.filelist[i].header_offset) + self.filelist[i].compress_size
                zinfo_size = struct.calcsize(structCentralDir) + len(self.filelist[i].filename) + len(self.filelist[i].extra)
                # Remove the file's data from the archive.
                current_offset = self.fp.tell()
                self.fp.seek(0, 2)
                archive_size = self.fp.tell()
                self.fp.seek(deleted_offset + deleted_size)
                buf = self.fp.read()
                self.fp.seek(deleted_offset)
                self.fp.write(buf)
                self.fp.truncate(archive_size - deleted_size - zinfo_size)
                if current_offset > deleted_offset + deleted_size:
                    current_offset -= deleted_size
                elif current_offset > deleted_offset:
                    current_offset = deleted_offset
                self.fp.seek(current_offset, 0)
                # Remove file from central directory.
                del self.filelist[i]
                # Adjust the remaining offsets in the central directory.
                for j in range(i, len(self.filelist)):
                    if self.filelist[j].header_offset > deleted_offset:
                        self.filelist[j].header_offset -= deleted_size
                    if self.filelist[j].file_offset > deleted_offset:
                        self.filelist[j].file_offset -= deleted_size
                self._didModify = True
                return
        if self.debug:
            print(name, "not in archive")

    def namelist(self):
        """Return a list of file names in the archive."""
        l = []
        for data in self.filelist:
            l.append(data.filename)
        return l

    def infolist(self):
        """Return a list of class ZipInfo instances for files in the
        archive."""
        return self.filelist

    def printdir(self):
        """Print a table of contents for the zip file."""
        print("%-46s %19s %12s" % ("File Name", "Modified    ", "Size"))
        for zinfo in self.filelist:
            date = "%d-%02d-%02d %02d:%02d:%02d" % zinfo.date_time[:6]
            print("%-46s %s %12d" % (zinfo.filename, date, zinfo.file_size))

    def testzip(self):
        """Read all the files and check the CRC."""
        chunk_size = 2 ** 20
        for zinfo in self.filelist:
            try:
                # Read by chunks, to avoid an OverflowError or a
                # MemoryError with very large embedded files.
                f = self.open(zinfo.filename, "r")
                while f.read(chunk_size):     # Check CRC-32
                    pass
            except BadZipfile:
                return zinfo.filename

    def getinfo(self, name):
        """Return the instance of ZipInfo given 'name'."""
        info = self.NameToInfo.get(name)
        if info is None:
            raise KeyError(
                'There is no item named %r in the archive' % name)

        return info

    def setpassword(self, pwd):
        """Set default password for encrypted files."""
        self.pwd = pwd

    def read(self, name, pwd=None):
        """Return file bytes (as a string) for name."""
        return self.open(name, "r", pwd).read()

    def read_raw(self, name, mode="r", pwd=None):
        """Return the raw bytes in the zipfile corresponding to name."""
        zef = self.open(name, mode=mode, pwd=pwd)
        return zef.read_raw()

    def open(self, name, mode="r", pwd=None):
        """Return file-like object for 'name'."""
        if mode not in ("r", "U", "rU"):
            raise RuntimeError('open() requires mode "r", "U", or "rU"')
        if not self.fp:
            raise RuntimeError(
                  "Attempt to read ZIP archive that was already closed")

        # Only open a new file for instances where we were not
        # given a file object in the constructor
        if self._filePassed:
            zef_file = self.fp
        else:
            zef_file = open(self.filename, 'rb')

        # Make sure we have an info object
        if isinstance(name, ZipInfo):
            # 'name' is already an info object
            zinfo = name
        else:
            # Get info object for name
            zinfo = self.getinfo(name)

        zef_file.seek(zinfo.header_offset, 0)

        # Skip the file header:
        fheader = zef_file.read(sizeFileHeader)
        if fheader[0:4] != stringFileHeader:
            raise BadZipfile("Bad magic number for file header")

        fheader = struct.unpack(structFileHeader, fheader)
        fname = zef_file.read(fheader[_FH_FILENAME_LENGTH])
        fname = decode_zip_internal_file_name(fname, zinfo.flag_bits)
        if fheader[_FH_EXTRA_FIELD_LENGTH]:
            zef_file.read(fheader[_FH_EXTRA_FIELD_LENGTH])

        if fname != zinfo.orig_filename:
            print(('WARNING: Header (%r) and directory (%r) filenames do not'
                    ' match inside ZipFile')%(fname, zinfo.orig_filename))
            print('Using directory filename %r'%zinfo.orig_filename)
            # raise BadZipfile, \
            #          'File name in directory "%r" and header "%r" differ.' % (
            #              zinfo.orig_filename, fname)

        # check for encrypted flag & handle password
        is_encrypted = zinfo.flag_bits & 0x1
        zd = None
        if is_encrypted:
            if not pwd:
                pwd = self.pwd
            if not pwd:
                raise RuntimeError(("File %s is encrypted, "
                      "password required for extraction") % name)

            zd = _ZipDecrypter(pwd)
            # The first 12 bytes in the cypher stream is an encryption header
            #  used to strengthen the algorithm. The first 11 bytes are
            #  completely random, while the 12th contains the MSB of the CRC,
            #  or the MSB of the file time depending on the header type
            #  and is used to check the correctness of the password.
            byts = zef_file.read(12)
            h = list(map(zd, bytearray(byts[0:12])))
            if zinfo.flag_bits & 0x8:
                # compare against the file type from extended local headers
                check_byte = (zinfo._raw_time >> 8) & 0xff
            else:
                # compare against the CRC otherwise
                check_byte = (zinfo.CRC >> 24) & 0xff
            if h[11] != check_byte:
                raise RuntimeError("Bad password for file", name)

        return ZipExtFile(zef_file, mode, zinfo, zd)

    def extract(self, member, path=None, pwd=None):
        """Extract a member from the archive to the current working directory,
           using its full name. Its file information is extracted as accurately
           as possible. `member' may be a filename or a ZipInfo object. You can
           specify a different directory using `path'.
        """
        if not isinstance(member, ZipInfo):
            member = self.getinfo(member)

        if path is None:
            path = getcwd()

        return self._extract_member(member, path, pwd)

    def extractall(self, path=None, members=None, pwd=None):
        """Extract all members from the archive to the current working
           directory. `path' specifies a different directory to extract to.
           `members' is optional and must be a subset of the list returned
           by namelist().
        """
        if members is None:
            members = self.namelist()

        # Kovid: Extract longer names first, just in case the zip file has
        # an entry for a directory without a trailing slash
        members.sort(key=len, reverse=True)

        for zipinfo in members:
            self.extract(zipinfo, path, pwd)

    def _extract_member(self, member, targetpath, pwd):
        """Extract the ZipInfo object 'member' to a physical
           file on the path targetpath.
        """
        # build the destination pathname, replacing
        # forward slashes to platform specific separators.
        # Strip trailing path separator, unless it represents the root.
        if (targetpath[-1:] in (os.path.sep, os.path.altsep) and
                len(os.path.splitdrive(targetpath)[1]) > 1):
            targetpath = targetpath[:-1]

        base_target = targetpath  # Added by Kovid

        # Sanitize path, changing absolute paths to relative paths
        # and removing .. and . (changed by Kovid)
        fname = member.filename.replace(os.sep, '/')
        fname = os.path.splitdrive(fname)[1]
        fname = '/'.join(x for x in fname.split('/') if x not in {'', os.path.curdir, os.path.pardir})
        if not fname:
            raise BadZipfile('The member %r has an invalid name'%member.filename)

        targetpath = os.path.normpath(os.path.join(base_target, fname))
        # Added by Kovid as normpath fails to convert forward slashes for UNC
        # paths, i.e. paths of the form \\?\C:\some/path
        if os.sep != '/':
            targetpath = targetpath.replace('/', os.sep)

        # Create all upper directories if necessary.
        upperdirs = os.path.dirname(targetpath)
        if upperdirs and not os.path.exists(upperdirs):
            try:
                os.makedirs(upperdirs)
            except:  # Added by Kovid
                targetpath = os.path.join(base_target,
                        sanitize_file_name(fname))
                upperdirs = os.path.dirname(targetpath)
                if upperdirs and not os.path.exists(upperdirs):
                    os.makedirs(upperdirs)

        if member.filename[-1] == '/':
            if not os.path.isdir(targetpath):
                os.mkdir(targetpath)
            self.extract_mapping[member.filename] = targetpath
            return targetpath

        if not os.path.exists(targetpath):
            # Kovid: Could be a previously automatically created directory
            # in which case it is ignored
            with closing(self.open(member, pwd=pwd)) as source:
                try:
                    with open(targetpath, 'wb') as target:
                        shutil.copyfileobj(source, target)
                except:
                    # Try sanitizing the file name to remove invalid characters
                    components = list(os.path.split(targetpath))
                    components[-1] = sanitize_file_name(components[-1])
                    targetpath = os.sep.join(components)
                    with open(targetpath, 'wb') as target:
                        shutil.copyfileobj(source, target)
        # Kovid: Try to preserve the timestamps in the ZIP file
        try:
            mtime = time.localtime()
            mtime = time.mktime(member.date_time + (0, 0) + (mtime.tm_isdst,))
            os.utime(targetpath, (mtime, mtime))
        except:
            pass
        self.extract_mapping[member.filename] = targetpath
        return targetpath

    def _writecheck(self, zinfo):
        """Check for errors before writing a file to the archive."""
        if zinfo.filename in self.NameToInfo:
            if self.debug:      # Warning for duplicate names
                print("Duplicate name:", zinfo.filename)
        if self.mode not in ("w", "a"):
            raise RuntimeError('write() requires mode "w" or "a"')
        if not self.fp:
            raise RuntimeError(
                  "Attempt to write ZIP archive that was already closed")
        if zinfo.compress_type == ZIP_DEFLATED and not zlib:
            raise RuntimeError(
                  "Compression requires the (missing) zlib module")
        if zinfo.compress_type not in (ZIP_STORED, ZIP_DEFLATED):
            raise RuntimeError(
                  "The compression method %s is not supported" % zinfo.compress_type)
        if zinfo.file_size > ZIP64_LIMIT:
            if not self._allowZip64:
                raise LargeZipFile("Filesize would require ZIP64 extensions")
        if zinfo.header_offset > ZIP64_LIMIT:
            if not self._allowZip64:
                raise LargeZipFile("Zipfile size would require ZIP64 extensions")

    def write(self, filename, arcname=None, compress_type=None):
        """Put the bytes from filename into the archive under the name
        arcname."""
        if not self.fp:
            raise RuntimeError(
                  "Attempt to write to ZIP archive that was already closed")

        st = os.stat(filename)
        isdir = stat.S_ISDIR(st.st_mode)
        mtime = time.localtime(st.st_mtime)
        date_time = mtime[0:6]
        # Create ZipInfo instance to store file information
        if arcname is None:
            arcname = filename
        arcname = os.path.normpath(os.path.splitdrive(arcname)[1])
        while arcname[0] in (os.sep, os.altsep):
            arcname = arcname[1:]
        if not isinstance(arcname, unicode_type):
            arcname = arcname.decode(filesystem_encoding)
        if isdir and not arcname.endswith('/'):
            arcname += '/'
        zinfo = ZipInfo(arcname, date_time)
        zinfo.external_attr = (st[0] & 0xFFFF) << 16      # Unix attributes
        if isdir:
            zinfo.compress_type = ZIP_STORED
        if compress_type is None:
            zinfo.compress_type = self.compression
        else:
            zinfo.compress_type = compress_type

        zinfo.file_size = st.st_size
        zinfo.flag_bits = 0x00
        zinfo.header_offset = self.fp.tell()    # Start of header bytes

        self._writecheck(zinfo)
        self._didModify = True

        if isdir:
            zinfo.file_size = 0
            zinfo.compress_size = 0
            zinfo.CRC = 0
            self.filelist.append(zinfo)
            self.NameToInfo[zinfo.filename] = zinfo
            self.fp.write(zinfo.FileHeader())
            return

        with open(filename, "rb") as fp:
            # Must overwrite CRC and sizes with correct data later
            zinfo.CRC = CRC = 0
            zinfo.compress_size = compress_size = 0
            zinfo.file_size = file_size = 0
            self.fp.write(zinfo.FileHeader())
            if zinfo.compress_type == ZIP_DEFLATED:
                cmpr = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION,
                    zlib.DEFLATED, -15)
            else:
                cmpr = None
            while 1:
                buf = fp.read(1024 * 8)
                if not buf:
                    break
                file_size = file_size + len(buf)
                CRC = crc32(buf, CRC) & 0xffffffff
                if cmpr:
                    buf = cmpr.compress(buf)
                    compress_size = compress_size + len(buf)
                self.fp.write(buf)
        if cmpr:
            buf = cmpr.flush()
            compress_size = compress_size + len(buf)
            self.fp.write(buf)
            zinfo.compress_size = compress_size
        else:
            zinfo.compress_size = file_size
        zinfo.CRC = CRC
        zinfo.file_size = file_size
        # Seek backwards and write CRC and file sizes
        position = self.fp.tell()       # Preserve current position in file
        self.fp.seek(zinfo.header_offset + 14, 0)
        self.fp.write(struct.pack("<LLL", zinfo.CRC, zinfo.compress_size,
              zinfo.file_size))
        self.fp.seek(position, 0)
        self.filelist.append(zinfo)
        self.NameToInfo[zinfo.filename] = zinfo

    def writestr(self, zinfo_or_arcname, byts, permissions=0o600,
            compression=ZIP_DEFLATED, raw_bytes=False):
        """Write a file into the archive.  The contents is the string
        'byts'.  'zinfo_or_arcname' is either a ZipInfo instance or
        the name of the file in the archive."""
        assert not raw_bytes or (raw_bytes and
                isinstance(zinfo_or_arcname, ZipInfo))
        if not isinstance(byts, bytes):
            byts = byts.encode('utf-8')
        if not isinstance(zinfo_or_arcname, ZipInfo):
            if not isinstance(zinfo_or_arcname, unicode_type):
                zinfo_or_arcname = zinfo_or_arcname.decode(filesystem_encoding)
            zinfo = ZipInfo(filename=zinfo_or_arcname,
                            date_time=time.localtime(time.time())[:6])
            zinfo.compress_type = compression
            zinfo.external_attr = permissions << 16
        else:
            zinfo = zinfo_or_arcname

        if not self.fp:
            raise RuntimeError(
                  "Attempt to write to ZIP archive that was already closed")

        if not raw_bytes:
            zinfo.file_size = len(byts)            # Uncompressed size
        zinfo.header_offset = self.fp.tell()    # Start of header bytes
        self._writecheck(zinfo)
        self._didModify = True
        if not raw_bytes:
            zinfo.CRC = crc32(byts) & 0xffffffff       # CRC-32 checksum
            if zinfo.compress_type == ZIP_DEFLATED:
                co = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION,
                    zlib.DEFLATED, -15)
                byts = co.compress(byts) + co.flush()
                zinfo.compress_size = len(byts)    # Compressed size
            else:
                zinfo.compress_size = zinfo.file_size
        zinfo.header_offset = self.fp.tell()    # Start of header bytes
        self.fp.write(zinfo.FileHeader())
        self.fp.write(byts)
        self.fp.flush()
        if zinfo.flag_bits & 0x08:
            # Write CRC and file sizes after the file data
            self.fp.write(struct.pack("<LLL", zinfo.CRC, zinfo.compress_size,
                  zinfo.file_size))
        self.filelist.append(zinfo)
        self.NameToInfo[zinfo.filename] = zinfo

    def add_dir(self, path, prefix='', simple_filter=lambda x:False):
        '''
        Add a directory recursively to the zip file with an optional prefix.
        '''
        if prefix:
            self.writestr(prefix+'/', b'', 0o755)
        fp = (prefix + ('/' if prefix else '')).replace('//', '/')
        for f in os.listdir(path):
            if simple_filter(f):  # Added by Kovid
                continue
            arcname = fp + f
            f = os.path.join(path, f)
            if os.path.isdir(f):
                self.add_dir(f, prefix=arcname, simple_filter=simple_filter)
            else:
                self.write(f, arcname)

    def __del__(self):
        """Call the "close()" method in case the user forgot."""
        self.close()

    def close(self):
        """Close the file, and for mode "w" and "a" write the ending
        records."""
        if self.fp is None:
            return

        if self.mode in ("w", "a") and self._didModify:  # write ending records
            count = 0
            pos1 = self.fp.tell()
            for zinfo in self.filelist:         # write central directory
                count = count + 1
                dt = zinfo.date_time
                dosdate = fixtimevar((dt[0] - 1980) << 9 | dt[1] << 5 | dt[2])
                dostime = fixtimevar(dt[3] << 11 | dt[4] << 5 | (dt[5] // 2))
                extra = []
                if zinfo.file_size > ZIP64_LIMIT \
                        or zinfo.compress_size > ZIP64_LIMIT:
                    extra.append(zinfo.file_size)
                    extra.append(zinfo.compress_size)
                    file_size = 0xffffffff
                    compress_size = 0xffffffff
                else:
                    file_size = zinfo.file_size
                    compress_size = zinfo.compress_size

                if zinfo.header_offset > ZIP64_LIMIT:
                    extra.append(zinfo.header_offset)
                    header_offset = 0xffffffff
                else:
                    header_offset = zinfo.header_offset

                extra_data = zinfo.extra
                if extra:
                    # Append a ZIP64 field to the extra's
                    extra_data = struct.pack(
                            '<HH' + 'Q'*len(extra),
                            1, 8*len(extra), *extra) + extra_data

                    extract_version = max(45, zinfo.extract_version)
                    create_version = max(45, zinfo.create_version)
                else:
                    extract_version = zinfo.extract_version
                    create_version = zinfo.create_version

                try:
                    filename, flag_bits = zinfo._encodeFilenameFlags()
                    centdir = struct.pack(structCentralDir,
                     stringCentralDir, create_version,
                     zinfo.create_system, extract_version, zinfo.reserved,
                     flag_bits, zinfo.compress_type, dostime, dosdate,
                     zinfo.CRC, compress_size, file_size,
                     len(filename), len(extra_data), len(zinfo.comment),
                     0, zinfo.internal_attr, zinfo.external_attr,
                     header_offset)
                except DeprecationWarning:
                    print((structCentralDir,
                     stringCentralDir, create_version,
                     zinfo.create_system, extract_version, zinfo.reserved,
                     zinfo.flag_bits, zinfo.compress_type, dostime, dosdate,
                     zinfo.CRC, compress_size, file_size,
                     len(zinfo.filename), len(extra_data), len(zinfo.comment),
                     0, zinfo.internal_attr, zinfo.external_attr,
                     header_offset), file=sys.stderr)
                    raise
                self.fp.write(centdir)
                self.fp.write(filename)
                self.fp.write(extra_data)
                self.fp.write(zinfo.comment)

            pos2 = self.fp.tell()
            # Write end-of-zip-archive record
            centDirCount = count
            centDirSize = pos2 - pos1
            centDirOffset = pos1
            if (centDirCount >= ZIP_FILECOUNT_LIMIT or
                centDirOffset > ZIP64_LIMIT or
                centDirSize > ZIP64_LIMIT):
                # Need to write the ZIP64 end-of-archive records
                zip64endrec = struct.pack(
                        structEndArchive64, stringEndArchive64,
                        44, 45, 45, 0, 0, centDirCount, centDirCount,
                        centDirSize, centDirOffset)
                self.fp.write(zip64endrec)

                zip64locrec = struct.pack(
                        structEndArchive64Locator,
                        stringEndArchive64Locator, 0, pos2, 1)
                self.fp.write(zip64locrec)
                centDirCount = min(centDirCount, 0xFFFF)
                centDirSize = min(centDirSize, 0xFFFFFFFF)
                centDirOffset = min(centDirOffset, 0xFFFFFFFF)

            # check for valid comment length
            if len(self.comment) >= ZIP_MAX_COMMENT:
                if self.debug > 0:
                    msg = 'Archive comment is too long; truncating to %d bytes' \
                          % ZIP_MAX_COMMENT
                    print(msg)
                self.comment = self.comment[:ZIP_MAX_COMMENT]

            endrec = struct.pack(structEndArchive, stringEndArchive,
                                 0, 0, centDirCount, centDirCount,
                                 centDirSize, centDirOffset, len(self.comment))
            self.fp.write(endrec)
            self.fp.write(self.comment)
            self.fp.flush()

        if not self._filePassed:
            self.fp.close()
        self.fp = None


def safe_replace(zipstream, name, datastream, extra_replacements={},
        add_missing=False):
    '''
    Replace a file in a zip file in a safe manner. This proceeds by extracting
    and re-creating the zipfile. This is necessary because :method:`ZipFile.replace`
    sometimes created corrupted zip files.


    :param zipstream:  Stream from a zip file
    :param name:       The name of the file to replace
    :param datastream: The data to replace the file with.
    :param extra_replacements: Extra replacements. Mapping of name to file-like
                               objects
    :param add_missing: If a replacement does not exist in the zip file, it is
                        added. Use with care as currently parent directories
                        are not created.

    '''
    z = ZipFile(zipstream, 'r')
    replacements = {name:datastream}
    replacements.update(extra_replacements)
    names = frozenset(replacements.keys())
    found = set()

    def rbytes(name):
        r = replacements[name]
        if not isinstance(r, bytes):
            r = r.read()
        return r

    with SpooledTemporaryFile(max_size=100*1024*1024) as temp:
        ztemp = ZipFile(temp, 'w')
        for obj in z.infolist():
            if isinstance(obj.filename, unicode_type):
                obj.flag_bits |= 0x16  # Set isUTF-8 bit
            if obj.filename in names:
                ztemp.writestr(obj, rbytes(obj.filename))
                found.add(obj.filename)
            else:
                ztemp.writestr(obj, z.read_raw(obj), raw_bytes=True)
        if add_missing:
            for name in names - found:
                ztemp.writestr(name, rbytes(name))
        ztemp.close()
        z.close()
        temp.seek(0)
        zipstream.seek(0)
        zipstream.truncate()
        shutil.copyfileobj(temp, zipstream)
        zipstream.flush()


class PyZipFile(ZipFile):

    """Class to create ZIP archives with Python library files and packages."""

    def writepy(self, pathname, basename=""):
        """Add all files from "pathname" to the ZIP archive.

        If pathname is a package directory, search the directory and
        all package subdirectories recursively for all *.py and enter
        the modules into the archive.  If pathname is a plain
        directory, listdir *.py and enter all modules.  Else, pathname
        must be a Python *.py file and the module will be put into the
        archive.  Added modules are always module.pyo or module.pyc.
        This method will compile the module.py into module.pyc if
        necessary.
        """
        dir, name = os.path.split(pathname)
        if os.path.isdir(pathname):
            initname = os.path.join(pathname, "__init__.py")
            if os.path.isfile(initname):
                # This is a package directory, add it
                if basename:
                    basename = "%s/%s" % (basename, name)
                else:
                    basename = name
                if self.debug:
                    print("Adding package in", pathname, "as", basename)
                fname, arcname = self._get_codename(initname[0:-3], basename)
                if self.debug:
                    print("Adding", arcname)
                self.write(fname, arcname)
                dirlist = os.listdir(pathname)
                dirlist.remove("__init__.py")
                # Add all *.py files and package subdirectories
                for filename in dirlist:
                    path = os.path.join(pathname, filename)
                    ext = os.path.splitext(filename)[-1]
                    if os.path.isdir(path):
                        if os.path.isfile(os.path.join(path, "__init__.py")):
                            # This is a package directory, add it
                            self.writepy(path, basename)  # Recursive call
                    elif ext == ".py":
                        fname, arcname = self._get_codename(path[0:-3],
                                         basename)
                        if self.debug:
                            print("Adding", arcname)
                        self.write(fname, arcname)
            else:
                # This is NOT a package directory, add its files at top level
                if self.debug:
                    print("Adding files from directory", pathname)
                for filename in os.listdir(pathname):
                    path = os.path.join(pathname, filename)
                    ext = os.path.splitext(filename)[-1]
                    if ext == ".py":
                        fname, arcname = self._get_codename(path[0:-3],
                                         basename)
                        if self.debug:
                            print("Adding", arcname)
                        self.write(fname, arcname)
        else:
            if pathname[-3:] != ".py":
                raise RuntimeError(
                      'Files added with writepy() must end with ".py"')
            fname, arcname = self._get_codename(pathname[0:-3], basename)
            if self.debug:
                print("Adding file", arcname)
            self.write(fname, arcname)

    def _get_codename(self, pathname, basename):
        """Return (filename, archivename) for the path.

        Given a module name path, return the correct file path and
        archive name, compiling if necessary.  For example, given
        /python/lib/string, return (/python/lib/string.pyc, string).
        """
        file_py  = pathname + ".py"
        file_pyc = pathname + ".pyc"
        file_pyo = pathname + ".pyo"
        if os.path.isfile(file_pyo) and \
                            os.stat(file_pyo).st_mtime >= os.stat(file_py).st_mtime:
            fname = file_pyo    # Use .pyo file
        elif not os.path.isfile(file_pyc) or \
             os.stat(file_pyc).st_mtime < os.stat(file_py).st_mtime:
            import py_compile
            if self.debug:
                print("Compiling", file_py)
            try:
                py_compile.compile(file_py, file_pyc, None, True)
            except py_compile.PyCompileError as err:
                print(err.msg)
            fname = file_pyc
        else:
            fname = file_pyc
        archivename = os.path.split(fname)[1]
        if basename:
            archivename = "%s/%s" % (basename, archivename)
        return (fname, archivename)


def main(args=None):
    import textwrap
    USAGE=textwrap.dedent("""\
        Usage:
            zipfile.py -l zipfile.zip        # Show listing of a zipfile
            zipfile.py -t zipfile.zip        # Test if a zipfile is valid
            zipfile.py -e zipfile.zip target # Extract zipfile into target dir
            zipfile.py -c zipfile.zip src ... # Create zipfile from sources
        """)
    if args is None:
        args = sys.argv[1:]

    if not args or args[0] not in ('-l', '-c', '-e', '-t'):
        print(USAGE)
        sys.exit(1)

    if args[0] == '-l':
        if len(args) != 2:
            print(USAGE)
            sys.exit(1)
        zf = ZipFile(args[1], 'r')
        zf.printdir()
        zf.close()

    elif args[0] == '-t':
        if len(args) != 2:
            print(USAGE)
            sys.exit(1)
        zf = ZipFile(args[1], 'r')
        badfile = zf.testzip()
        if badfile:
            print("The following enclosed file is corrupted: {!r}".format(badfile))
        print("Done testing")

    elif args[0] == '-e':
        if len(args) != 3:
            print(USAGE)
            sys.exit(1)

        zf = ZipFile(args[1], 'r')
        out = args[2]
        for path in zf.namelist():
            if path.startswith('./'):
                tgt = os.path.join(out, path[2:])
            else:
                tgt = os.path.join(out, path)

            tgtdir = os.path.dirname(tgt)
            if not os.path.exists(tgtdir):
                os.makedirs(tgtdir)
            with open(tgt, 'wb') as fp:
                fp.write(zf.read(path))
        zf.close()

    elif args[0] == '-c':
        if len(args) < 3:
            print(USAGE)
            sys.exit(1)

        def addToZip(zf, path, zippath):
            if os.path.isfile(path):
                zf.write(path, zippath, ZIP_DEFLATED)
            elif os.path.isdir(path):
                for nm in os.listdir(path):
                    addToZip(zf,
                            os.path.join(path, nm), os.path.join(zippath, nm))
            # else: ignore

        zf = ZipFile(args[1], 'w', allowZip64=True)
        for src in args[2:]:
            addToZip(zf, src, os.path.basename(src))

        zf.close()


if __name__ == "__main__":
    main()
