__license__   = 'GPL v3'
__copyright__ = '2013, Jellby <jellby at yahoo.com>'
'''
Write a t4b file to disk.
'''

import StringIO

DEFAULT_T4B_DATA = ''

def reduce_color(c):
    if (c < 0):
        return 0
    elif (c > 255):
        return 15
    else:
        return c//16

def write_t4b(t4bfile, coverdata=None):
    '''
    t4bfile is a file handle ready to write binary data to disk.
    coverdata is a string representation of a JPEG file.
    '''
    from PIL import Image
    if coverdata != None:
        coverdata = StringIO.StringIO(coverdata)
        cover = Image.open(coverdata).convert("L")
        cover.thumbnail((96, 144), Image.ANTIALIAS)
        t4bcover = Image.new('L', (96, 144), 'white')

        x, y = cover.size
        t4bcover.paste(cover, ((96-x)/2, (144-y)/2))

        pxs = t4bcover.getdata()
        t4bfile.write('t4bp')
        for i in range(0,len(pxs),2):
            byte = reduce_color(pxs[i])
            byte = 16*byte + reduce_color(pxs[i+1])
            t4bfile.write(chr(byte))
    else:
        t4bfile.write(DEFAULT_T4B_DATA)

