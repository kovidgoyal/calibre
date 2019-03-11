# -*- coding: utf-8 -*-

from __future__ import print_function
__license__   = 'GPL v3'
__copyright__ = '2010, Li Fanxi <lifanxi@freemindworld.com>'
__docformat__ = 'restructuredtext en'

import sys, struct, zlib, bz2, os

from calibre import guess_type
from polyglot.builtins import unicode_type


class FileStream:

    def IsBinary(self):
        return self.attr & 0x41000000 != 0x41000000


def compareFileStream(file1, file2):
    return cmp(file1.fileName, file2.fileName)


class BlockData:
    pass


class SNBFile:

    MAGIC = 'SNBP000B'
    REV80 = 0x00008000
    REVA3 = 0x00A3A3A3
    REVZ1 = 0x00000000
    REVZ2 = 0x00000000

    def __init__(self, inputFile=None):
        self.files = []
        self.blocks = []

        if inputFile is not None:
            self.Open(inputFile)

    def Open(self, inputFile):
        self.fileName = inputFile

        snbFile = open(self.fileName, "rb")
        snbFile.seek(0)
        self.Parse(snbFile)
        snbFile.close()

    def Parse(self, snbFile, metaOnly=False):
        # Read header
        vmbr = snbFile.read(44)
        (self.magic, self.rev80, self.revA3, self.revZ1,
         self.fileCount, self.vfatSize, self.vfatCompressed,
         self.binStreamSize, self.plainStreamSizeUncompressed,
         self.revZ2) = struct.unpack('>8siiiiiiiii', vmbr)

        # Read FAT
        self.vfat = zlib.decompress(snbFile.read(self.vfatCompressed))
        self.ParseFile(self.vfat, self.fileCount)

        # Read tail
        snbFile.seek(-16, os.SEEK_END)
        # plainStreamEnd = snbFile.tell()
        tailblock = snbFile.read(16)
        (self.tailSize, self.tailOffset, self.tailMagic) = struct.unpack('>ii8s', tailblock)
        snbFile.seek(self.tailOffset)
        self.vTailUncompressed = zlib.decompress(snbFile.read(self.tailSize))
        self.tailSizeUncompressed = len(self.vTailUncompressed)
        self.ParseTail(self.vTailUncompressed, self.fileCount)

        # Uncompress file data
        # Read files
        binPos = 0
        plainPos = 0
        uncompressedData = None
        for f in self.files:
            if f.attr & 0x41000000 == 0x41000000:
                # Compressed Files
                if uncompressedData is None:
                    uncompressedData = ""
                    for i in range(self.plainBlock):
                        bzdc = bz2.BZ2Decompressor()
                        if (i < self.plainBlock - 1):
                            bSize = self.blocks[self.binBlock + i + 1].Offset - self.blocks[self.binBlock + i].Offset
                        else:
                            bSize = self.tailOffset - self.blocks[self.binBlock + i].Offset
                        snbFile.seek(self.blocks[self.binBlock + i].Offset)
                        try:
                            data = snbFile.read(bSize)
                            if len(data) < 32768:
                                uncompressedData += bzdc.decompress(data)
                            else:
                                uncompressedData += data
                        except Exception as e:
                            print(e)
                if len(uncompressedData) != self.plainStreamSizeUncompressed:
                    raise Exception()
                f.fileBody = uncompressedData[plainPos:plainPos+f.fileSize]
                plainPos += f.fileSize
            elif f.attr & 0x01000000 == 0x01000000:
                # Binary Files
                snbFile.seek(44 + self.vfatCompressed + binPos)
                f.fileBody = snbFile.read(f.fileSize)
                binPos += f.fileSize
            else:
                print(f.attr, f.fileName)
                raise Exception("Invalid file")

    def ParseFile(self, vfat, fileCount):
        fileNames = vfat[fileCount*12:].split('\0')
        for i in range(fileCount):
            f = FileStream()
            (f.attr, f.fileNameOffset, f.fileSize) = struct.unpack('>iii', vfat[i * 12 : (i+1)*12])
            f.fileName = fileNames[i]
            self.files.append(f)

    def ParseTail(self, vtail, fileCount):
        self.binBlock = (self.binStreamSize + 0x8000 - 1) / 0x8000
        self.plainBlock = (self.plainStreamSizeUncompressed + 0x8000 - 1) / 0x8000
        for i in range(self.binBlock + self.plainBlock):
            block = BlockData()
            (block.Offset,) = struct.unpack('>i', vtail[i * 4 : (i+1) * 4])
            self.blocks.append(block)
        for i in range(fileCount):
            (self.files[i].blockIndex, self.files[i].contentOffset) = struct.unpack('>ii', vtail[
             (self.binBlock + self.plainBlock) * 4 + i * 8 : (self.binBlock + self.plainBlock) * 4 + (i+1) * 8])

    def IsValid(self):
        if self.magic != SNBFile.MAGIC:
            return False
        if self.rev80 != SNBFile.REV80:
            return False
#        if self.revA3 != SNBFile.REVA3:
#            return False
        if self.revZ1 != SNBFile.REVZ1:
            return False
        if self.revZ2 != SNBFile.REVZ2:
            return False
        if self.vfatSize != len(self.vfat):
            return False
        if self.fileCount != len(self.files):
            return False
        if (self.binBlock + self.plainBlock) * 4 + self.fileCount * 8 != self.tailSizeUncompressed:
            return False
        if self.tailMagic != SNBFile.MAGIC:
            print(self.tailMagic)
            return False
        return True

    def FromDir(self, tdir):
        for root, dirs, files in os.walk(tdir):
            for name in files:
                p, ext = os.path.splitext(name)
                if ext in [".snbf", ".snbc"]:
                    self.AppendPlain(os.path.relpath(os.path.join(root, name), tdir), tdir)
                else:
                    self.AppendBinary(os.path.relpath(os.path.join(root, name), tdir), tdir)

    def AppendPlain(self, fileName, tdir):
        f = FileStream()
        f.attr = 0x41000000
        f.fileSize = os.path.getsize(os.path.join(tdir,fileName))
        f.fileBody = open(os.path.join(tdir,fileName), 'rb').read()
        f.fileName = fileName.replace(os.sep, '/')
        if isinstance(f.fileName, unicode_type):
            f.fileName = f.fileName.encode("ascii", "ignore")
        self.files.append(f)

    def AppendBinary(self, fileName, tdir):
        f = FileStream()
        f.attr = 0x01000000
        f.fileSize = os.path.getsize(os.path.join(tdir,fileName))
        f.fileBody = open(os.path.join(tdir,fileName), 'rb').read()
        f.fileName = fileName.replace(os.sep, '/')
        if isinstance(f.fileName, unicode_type):
            f.fileName = f.fileName.encode("ascii", "ignore")
        self.files.append(f)

    def GetFileStream(self, fileName):
        for file in self.files:
            if file.fileName == fileName:
                return file.fileBody
        return None

    def OutputImageFiles(self, path):
        fileNames = []
        for f in self.files:
            fname = os.path.basename(f.fileName)
            root, ext = os.path.splitext(fname)
            if ext in ['.jpeg', '.jpg', '.gif', '.svg', '.png']:
                file = open(os.path.join(path, fname), 'wb')
                file.write(f.fileBody)
                file.close()
                fileNames.append((fname, guess_type('a'+ext)[0]))
        return fileNames

    def Output(self, outputFile):

        # Sort the files in file buffer,
        # requried by the SNB file format
        self.files.sort(compareFileStream)

        outputFile = open(outputFile, 'wb')
        # File header part 1
        vmbrp1 = struct.pack('>8siiii', SNBFile.MAGIC, SNBFile.REV80, SNBFile.REVA3, SNBFile.REVZ1, len(self.files))

        # Create VFAT & file stream
        vfat = ''
        fileNameTable = ''
        plainStream = ''
        binStream = ''
        for f in self.files:
            vfat += struct.pack('>iii', f.attr, len(fileNameTable), f.fileSize)
            fileNameTable += (f.fileName + '\0')

            if f.attr & 0x41000000 == 0x41000000:
                # Plain Files
                f.contentOffset = len(plainStream)
                plainStream += f.fileBody
            elif f.attr & 0x01000000 == 0x01000000:
                # Binary Files
                f.contentOffset = len(binStream)
                binStream += f.fileBody
            else:
                print(f.attr, f.fileName)
                raise Exception("Unknown file type")
        vfatCompressed = zlib.compress(vfat+fileNameTable)

        # File header part 2
        vmbrp2 = struct.pack('>iiiii', len(vfat+fileNameTable), len(vfatCompressed), len(binStream), len(plainStream), SNBFile.REVZ2)
        # Write header
        outputFile.write(vmbrp1 + vmbrp2)
        # Write vfat
        outputFile.write(vfatCompressed)

        # Generate block information
        binBlockOffset = 0x2C + len(vfatCompressed)
        plainBlockOffset = binBlockOffset + len(binStream)

        binBlock = (len(binStream) + 0x8000 - 1) / 0x8000
        # plainBlock = (len(plainStream) + 0x8000 - 1) / 0x8000

        offset = 0
        tailBlock = ''
        for i in range(binBlock):
            tailBlock += struct.pack('>i', binBlockOffset + offset)
            offset += 0x8000
        tailRec = ''
        for f in self.files:
            t = 0
            if f.IsBinary():
                t = 0
            else:
                t = binBlock
            tailRec += struct.pack('>ii', f.contentOffset / 0x8000 + t, f.contentOffset % 0x8000)

        # Write binary stream
        outputFile.write(binStream)

        # Write plain stream
        pos = 0
        offset = 0
        while pos < len(plainStream):
            tailBlock += struct.pack('>i', plainBlockOffset + offset)
            block = plainStream[pos:pos+0x8000]
            compressed = bz2.compress(block)
            outputFile.write(compressed)
            offset += len(compressed)
            pos += 0x8000

        # Write tail block
        compressedTail = zlib.compress(tailBlock + tailRec)
        outputFile.write(compressedTail)

        # Write tail pointer
        veom = struct.pack('>ii', len(compressedTail), plainBlockOffset + offset)
        outputFile.write(veom)

        # Write file end mark
        outputFile.write(SNBFile.MAGIC)

        # Close
        outputFile.close()
        return

    def Dump(self):
        if self.fileName:
            print("File Name:\t", self.fileName)
        print("File Count:\t", self.fileCount)
        print("VFAT Size(Compressed):\t%d(%d)" % (self.vfatSize, self.vfatCompressed))
        print("Binary Stream Size:\t", self.binStreamSize)
        print("Plain Stream Uncompressed Size:\t", self.plainStreamSizeUncompressed)
        print("Binary Block Count:\t", self.binBlock)
        print("Plain Block Count:\t", self.plainBlock)
        for i in range(self.fileCount):
            print("File ", i)
            f = self.files[i]
            print("File Name: ", f.fileName)
            print("File Attr: ", f.attr)
            print("File Size: ", f.fileSize)
            print("Block Index: ", f.blockIndex)
            print("Content Offset: ", f.contentOffset)
            tempFile = open("/tmp/" + f.fileName, 'wb')
            tempFile.write(f.fileBody)
            tempFile.close()


def usage():
    print("This unit test is for INTERNAL usage only!")
    print("This unit test accept two parameters.")
    print("python snbfile.py <INPUTFILE> <DESTFILE>")
    print("The input file will be extracted and write to dest file. ")
    print("Meta data of the file will be shown during this process.")


def main():
    if len(sys.argv) != 3:
        usage()
        sys.exit(0)
    inputFile = sys.argv[1]
    outputFile = sys.argv[2]

    print("Input file: ", inputFile)
    print("Output file: ", outputFile)

    snbFile = SNBFile(inputFile)
    if snbFile.IsValid():
        snbFile.Dump()
        snbFile.Output(outputFile)
    else:
        print("The input file is invalid.")
        return 1
    return 0


if __name__ == "__main__":
    """SNB file unit test"""
    sys.exit(main())
