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
import pkg_resources
import subprocess
from tempfile import mkdtemp
from optparse import OptionParser
from libprs500.lrf import ConversionError
from libprs500.lrf.meta import LRFException, LRFMetaFile
from libprs500.ptempfile import PersistentTemporaryFile

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

