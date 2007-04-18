##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
import os
import shutil
import sys
import hashlib
import re
import time
import pkg_resources
import subprocess
from tempfile import mkdtemp
from optparse import OptionParser
import xml.dom.minidom as dom

from libprs500.lrf import ConversionError
from libprs500.lrf.meta import LRFException, LRFMetaFile
from libprs500.ptempfile import PersistentTemporaryFile

_bbebook = 'BBeBook-0.2.jar'

def generate_thumbnail(path):
    """ Generate a JPEG thumbnail of size ~ 128x128 (aspect ratio preserved)"""
    try:
        from PIL import Image
    except ImportError:
        raise LRFException("Unable to initialize Python Imaging Library." \
                "Thumbnail generation is disabled")
    im = Image.open(path)    
    im.thumbnail((128, 128), Image.ANTIALIAS)
    thumb = PersistentTemporaryFile(prefix="makelrf_", suffix=".jpeg")
    thumb.close()
    im = im.convert()
    im.save(thumb.name)
    return thumb
    
def create_xml(cfg):
    doc = dom.getDOMImplementation().createDocument(None, None, None)
    def add_field(parent, tag, value):
        elem = doc.createElement(tag)
        elem.appendChild(doc.createTextNode(value))
        parent.appendChild(elem)
    
    info = doc.createElement('Info')
    info.setAttribute('version', '1.0')
    book_info = doc.createElement('BookInfo')
    doc_info  = doc.createElement('DocInfo')
    info.appendChild(book_info)
    info.appendChild(doc_info)
    add_field(book_info, 'File', cfg['File'])
    add_field(doc_info, 'Output', cfg['Output'])
    for field in ['Title', 'Author', 'BookID', 'Publisher', 'Label', \
                  'Category', 'Classification', 'Icon', 'Cover', 'FreeText']:
        if cfg.has_key(field):
            add_field(book_info, field, cfg[field])
    add_field(doc_info, 'Language', 'en')
    add_field(doc_info, 'Creator', _bbebook)
    add_field(doc_info, 'CreationDate', time.strftime('%Y-%m-%d', time.gmtime()))
    doc.appendChild(info)
    return doc.toxml()

def makelrf(author=None, title=None, \
            thumbnail=None, src=None, odir=".",\
            rasterize=True, cover=None):
    src = os.path.normpath(os.path.abspath(src))
    bbebook = pkg_resources.resource_filename(__name__, _bbebook)
    if not os.access(src, os.R_OK):
        raise LRFException("Unable to read from file: " + src)
    if thumbnail:
            thumb = os.path.abspath(thumbnail)
            if not os.access(thumb, os.R_OK):
                raise LRFException("Unable to read from " + thumb)
    else:
        thumb = pkg_resources.resource_filename(__name__, 'cover.jpg')
            
    if not author:
        author = "Unknown"    
    if not title:
        title = os.path.basename(src)
    label = os.path.basename(src)
    id = 'FB' + hashlib.md5(os.path.basename(label)).hexdigest()[:14]
    name, ext = os.path.splitext(label)
    cwd = os.path.dirname(src)    
    dirpath = None
    try:
        if ext == ".rar":
            dirpath = mkdtemp('','makelrf')
            cwd = dirpath            
            cmd = " ".join(["unrar", "e", '"'+src+'"'])
            proc = subprocess.Popen(cmd, cwd=cwd, shell=True, stderr=subprocess.PIPE)
            if proc.wait():
                raise LRFException("unrar failed with error:\n\n" + \
                        proc.stderr.read())
            path, msize = None, 0
            for root, dirs, files in os.walk(dirpath):
                for name in files:
                    if os.path.splitext(name)[1] == ".html":
                        size = os.stat(os.path.join(root, name)).st_size                        
                        if size > msize:
                            msize, path = size, os.path.join(root, name)
            if not path:
                raise LRFException("Could not find .html file in rar archive")
            src = path
        
        name = re.sub("\s", "_", name)
        name = os.path.abspath(os.path.join(odir, name)) + ".lrf"
        cfg = { 'File' : src, 'Output' : name, 'Label' : label, 'BookID' : id, \
                'Author' : author, 'Title' : title, 'Publisher' : 'Unknown' \
              }        
        
        
        if cover:
            cover = os.path.normpath(os.path.abspath(cover))
            try:
                thumbf = generate_thumbnail(cover)
                thumb = thumbf.name
            except Exception, e:
                print >> sys.stderr, "WARNING: Unable to generate thumbnail:\n", \
                         str(e)
                thumb = cover
            cfg['Cover'] = cover
        cfg['Icon'] = thumb
        config = PersistentTemporaryFile(prefix='makelrf_', suffix='.xml')
        config.write(create_xml(cfg))
        config.close()
        jar = '-jar "' + bbebook + '"'
        cmd = " ".join(["java", jar, "-r" if rasterize else "", '"'+config.name+'"'])
        proc = subprocess.Popen(cmd, \
               cwd=cwd, shell=True, stderr=subprocess.PIPE)
        if proc.wait():
            raise LRFException("BBeBook failed with error:\n\n" + \
                    proc.stderr.read())
        # Needed as BBeBook-0.2 doesn't handle non GIF thumbnails correctly.
        lrf = open(name, "r+b")
        LRFMetaFile(lrf).fix_thumbnail_type()
        lrf.close()
        return name
    finally:
        if dirpath: 
            shutil.rmtree(dirpath, True)

def txt():
    """ CLI for txt -> lrf conversions """
    parser = OptionParser(usage=\
        """usage: %prog [options] mybook.txt
        
        %prog converts mybook.txt to mybook.lrf
        """\
        )
    parser.add_option("-t", "--title", action="store", type="string", \
                    dest="title", help="Set the title")
    parser.add_option("-a", "--author", action="store", type="string", \
                    dest="author", help="Set the author", default='Unknown')
    defenc = 'cp1252'
    enchelp = 'Set the encoding used to decode ' + \
              'the text in mybook.txt. Default encoding is ' + defenc
    parser.add_option('-e', '--encoding', action='store', type='string', \
                      dest='encoding', help=enchelp, default=defenc)
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.print_help()
        sys.exit(1)
    src = args[0]
    if options.title == None:
        options.title = os.path.splitext(os.path.basename(src))[0]
    try:
        convert_txt(src, options)
    except ConversionError, err:
        print >>sys.stderr, err
        sys.exit(1)
        
    
def convert_txt(path, options):
    """
    Convert the text file at C{path} into an lrf file.
    @param options: Object with the following attributes:
                    C{author}, C{title}, C{encoding} (the assumed encoding of 
                    the text in C{path}.)
    """
    import fileinput
    from libprs500.lrf.pylrs.pylrs import Book
    book = Book(title=options.title, author=options.author, \
                sourceencoding=options.encoding)
    buffer = ''
    block = book.Page().TextBlock()
    for line in fileinput.input(path):
        line = line.strip()
        if line:
            buffer += line
        else:
            block.Paragraph(buffer)            
            buffer = ''
    basename = os.path.basename(path)
    name = os.path.splitext(basename)[0]+'.lrf'
    try: 
        book.renderLrf(name)
    except UnicodeDecodeError:
        raise ConversionError(path + ' is not encoded in ' + \
                              options.encoding +'. Specify the '+ \
                              'correct encoding with the -e option.')
    return os.path.abspath(name)
    

def html():
    """ CLI for html -> lrf conversions """
    parser = OptionParser(usage=\
        """usage: %prog [options] mybook.txt
        
        %prog converts mybook.txt to mybook.lrf
        """\
        )
    parser.add_option("-t", "--title", action="store", type="string", \
                    dest="title", help="Set the title")
    parser.add_option("-a", "--author", action="store", type="string", \
                    dest="author", help="Set the author", default='Unknown')
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.print_help()
        sys.exit(1)
    src = args[0]
    if options.title == None:
        options.title = os.path.splitext(os.path.basename(src))[0]
    from libprs500.lrf.html.convert import process_file
    process_file(src, options)

def main(cargs=None):
    parser = OptionParser(usage=\
        """usage: %prog [options] mybook.[html|pdf|rar]
        
        %prog converts mybook to mybook.lrf
        If you specify a rar file you must have the unrar command line client
        installed. makelrf assumes the rar file is an archive containing the
        html file you want converted."""\
        )
    
    parser.add_option("-t", "--title", action="store", type="string", \
                    dest="title", help="Set the book title")
    parser.add_option("-a", "--author", action="store", type="string", \
                    dest="author", help="Set the author")
    parser.add_option('-r', '--rasterize', action='store_false', \
                    dest="rasterize", 
                    help="Convert pdfs into image files.")
    parser.add_option('-c', '--cover', action='store', dest='cover',\
                    help="Path to a graphic that will be set as the cover. "\
                    "If it is specified the thumbnail is automatically "\
                    "generated from it")
    parser.add_option("--thumbnail", action="store", type="string", \
                    dest="thumbnail", \
                    help="Path to a graphic that will be set as the thumbnail")
    if not cargs:
        cargs = sys.argv
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.print_help()
        sys.exit(1)
    src = args[0]
    root, ext = os.path.splitext(src)
    if ext not in ['.html', '.pdf', '.rar']:
        print >> sys.stderr, "Can only convert files ending in .html|.pdf|.rar"
        parser.print_help()
        sys.exit(1)
    name = makelrf(author=options.author, title=options.title, \
        thumbnail=options.thumbnail, src=src, cover=options.cover, \
        rasterize=options.rasterize)
    print "LRF generated:", name
