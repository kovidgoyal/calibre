#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Based on ideas from comiclrf created by FangornUK.
'''

import os, sys, traceback, shutil
from uuid import uuid4

from calibre import extract, OptionParser, detect_ncpus, terminal_controller, \
                    __appname__, __version__
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.threadpool import ThreadPool, WorkRequest
from calibre.utils.terminfo import ProgressBar
from calibre.ebooks.lrf.pylrs.pylrs import Book, BookSetting, ImageStream, ImageBlock
from calibre.utils.PythonMagickWand import \
    NewMagickWand, NewPixelWand, \
    MagickSetImageBorderColor, \
    MagickReadImage, MagickRotateImage, \
    MagickTrimImage, \
    MagickNormalizeImage, MagickGetImageWidth, \
    MagickGetImageHeight, \
    MagickResizeImage, MagickSetImageType, \
    GrayscaleType, CatromFilter,  MagickSetImagePage, \
    MagickBorderImage, MagickSharpenImage, \
    MagickQuantizeImage, RGBColorspace, \
    MagickWriteImage, DestroyPixelWand, \
    DestroyMagickWand, CloneMagickWand, \
    MagickThumbnailImage, MagickCropImage, initialize, finalize

PROFILES = {
            'prs500':(584, 754),            
            }

def extract_comic(path_to_comic_file):
    '''
    Un-archive the comic file.
    '''
    tdir = PersistentTemporaryDirectory(suffix='comic_extract')
    extract(path_to_comic_file, tdir)
    return tdir

def find_pages(dir, sort_on_mtime=False, verbose=False):
    '''
    Find valid comic pages in a previously un-archived comic. 
    
    :param dir: Directory in which extracted comic lives
    :param sort_on_mtime: If True sort pages based on their last modified time.
                          Otherwise, sort alphabetically.
    '''
    extensions = ['jpeg', 'jpg', 'gif', 'png']
    pages = []
    for datum in os.walk(dir):
        for name in datum[-1]:
            path = os.path.join(datum[0], name)
            for ext in extensions:
                if path.lower().endswith('.'+ext):
                    pages.append(path)
                    break
    if sort_on_mtime:
        comparator = lambda x, y : cmp(os.stat(x).st_mtime, os.stat(y).st_mtime)
    else:
        comparator = lambda x, y : cmp(os.path.basename(x), os.path.basename(y))

    pages.sort(cmp=comparator)
    if verbose:
        print 'Found comic pages...'
        print '\t'+'\n\t'.join([os.path.basename(p) for p in pages])
    return pages

class PageProcessor(list):
    '''
    Contains the actual image rendering logic. See :method:`__call__` and 
    :method:`process_pages`.
    '''
    
    def __init__(self, path_to_page, dest, opts, num):
        self.path_to_page = path_to_page
        self.opts = opts
        self.num = num
        self.dest = dest
        self.rotate = False
        list.__init__(self)
        
    def __call__(self):
        try:
            img = NewMagickWand()
            if img < 0:
                raise RuntimeError('Cannot create wand.')
            if not MagickReadImage(img, self.path_to_page):
                raise IOError('Failed to read image from: %'%self.path_to_page)
            width  = MagickGetImageWidth(img)
            height = MagickGetImageHeight(img)
            
            if self.num == 0: # First image so create a thumbnail from it
                thumb = CloneMagickWand(img)
                if thumb < 0:
                    raise RuntimeError('Cannot create wand.')
                MagickThumbnailImage(thumb, 60, 80)
                MagickWriteImage(thumb, os.path.join(self.dest, 'thumbnail.png'))
                DestroyMagickWand(thumb)
            
            self.pages = [img]
            
            if width > height:
                if self.opts.landscape:
                    self.rotate = True
                else: 
                    split1, split2 = map(CloneMagickWand, (img, img))
                    if split1 < 0 or split2 < 0:
                        raise RuntimeError('Cannot create wand.')
                    DestroyMagickWand(img)
                    MagickCropImage(split1, (width/2)-1, height, 0, 0)
                    MagickCropImage(split2, (width/2)-1, height, width/2, 0 )
                    self.pages = [split1, split2]
                
            self.process_pages()
        except Exception, err:
            print 'Failed to process page: %s'%os.path.basename(self.path_to_page)
            print 'Error:', err
            if self.opts.verbose:
                traceback.print_exc()
        
    def process_pages(self):
        for i, wand in enumerate(self.pages):
            pw = NewPixelWand()
            if pw < 0:
                raise RuntimeError('Cannot create wand.')
            #flag = PixelSetColor(pw, 'white')
            
            MagickSetImageBorderColor(wand, pw)
            
            if self.rotate:
                MagickRotateImage(wand, pw, -90)
                
            # 25 percent fuzzy trim?
            MagickTrimImage(wand, 25*65535/100)
            MagickSetImagePage(wand, 0,0,0,0)   #Clear page after trim, like a "+repage"
            
            # Do the Photoshop "Auto Levels" equivalent
            if self.opts.normalize:
                MagickNormalizeImage(wand)
        
            sizex = MagickGetImageWidth(wand)
            sizey = MagickGetImageHeight(wand)
            
            SCRWIDTH, SCRHEIGHT = PROFILES[self.opts.profile]
            
            if self.opts.keep_aspect_ratio: 
                # Preserve the aspect ratio by adding border
                aspect = float(sizex) / float(sizey)
                if aspect <= (float(SCRWIDTH) / float(SCRHEIGHT)):
                    newsizey = SCRHEIGHT
                    newsizex = int(newsizey * aspect)
                    deltax = (SCRWIDTH - newsizex) / 2
                    deltay = 0
                else:
                    newsizex = SCRWIDTH
                    newsizey = int(newsizex / aspect)
                    deltax = 0
                    deltay = (SCRHEIGHT - newsizey) / 2
        
                MagickResizeImage(wand, newsizex, newsizey, CatromFilter, 1.0)
                MagickSetImageBorderColor(wand, pw)
                MagickBorderImage(wand, pw, deltax, deltay)
            else:
                MagickResizeImage(wand, SCRWIDTH, SCRHEIGHT, CatromFilter, 1.0)
                
            if self.opts.sharpen:
                MagickSharpenImage(wand, 0.0, 1.0)
                
            MagickSetImageType(wand, GrayscaleType)
            MagickQuantizeImage(wand, self.opts.colors, RGBColorspace, 0, 1, 0)
            dest = '%d_%d%s'%(self.num, i, os.path.splitext(self.path_to_page)[-1])
            dest = os.path.join(self.dest, dest)
            MagickWriteImage(wand, dest)
            self.append(dest)
        
            DestroyPixelWand(pw)
            wand = DestroyMagickWand(wand)
            
class Progress(object):
    
    def __init__(self, total, update):
        self.total  = total
        self.update = update
        self.done   = 0
        
    def __call__(self, req, res):
        self.done += 1
        self.update(float(self.done)/self.total, 
                    _('Rendered %s')%os.path.basename(req.callable.path_to_page))

def process_pages(pages, opts, update):
    '''
    Render all identified comic pages.
    '''
    initialize()
    try:
        tdir = PersistentTemporaryDirectory('_comic2lrf_pp')
        processed_pages = [PageProcessor(path, tdir, opts, i) for i, path in enumerate(pages)]
        tp = ThreadPool(detect_ncpus())
        update(0, '')
        notify = Progress(len(pages), update)
        for pp in processed_pages:
            tp.putRequest(WorkRequest(pp, callback=notify))
            tp.wait()
        ans, failures = [], []
        
        for pp in processed_pages:
            if len(pp) == 0:
                failures.append(os.path.basename(pp.path_to_page()))
            else:
                ans += pp
        return ans, failures, tdir
    finally:
        finalize()

def option_parser():
    parser = OptionParser(_('''\
%prog [options] comic.cb[z|r]

Convert a comic in a CBZ or CBR file to an LRF ebook. 
	'''))
    parser.add_option('-t', '--title', help=_('Title for generated ebook. Default is to use the filename.'), default=None)
    parser.add_option('-a', '--author', help=_('Set the author in the metadata of the generated ebook. Default is %default'), default=_('Unknown'))
    parser.add_option('-o', '--output', help=_('Path to output LRF file. By default a file is created in the current directory.'), default=None)
    parser.add_option('-c', '--colors', type='int', default=64,
    				  help=_('Number of colors for Grayscale image conversion. Default: %default'))
    parser.add_option('-n', '--disable-normalize', dest='normalize', default=True, action='store_false',
    				  help=_('Disable normalize (improve contrast) color range for pictures. Default: False'))
    parser.add_option('-r', '--keep-aspect-ratio', action='store_true', default=False,
    				  help=_('Maintain picture aspect ratio. Default is to fill the screen.'))
    parser.add_option('-s', '--disable-sharpen', default=True, action='store_false', dest='sharpen',
    				  help=_('Disable sharpening.'))
    parser.add_option('-l', '--landscape', default=False, action='store_true',
    				  help=_("Don't split landscape images into two portrait images"))
    parser.add_option('--no-sort', default=False, action='store_true',
                      help=_("Don't sort the files found in the comic alphabetically by name. Instead use the order they were added to the comic."))
    parser.add_option('-p', '--profile', default='prs500', dest='profile', type='choice',
                      choices=PROFILES.keys(), help=_('Choose a profile for the device you are generating this LRF for. The default is the SONY PRS-500 with a screen size of 584x754 pixels. Choices are %s')%PROFILES.keys())
    parser.add_option('--verbose', default=False, action='store_true', 
                      help=_('Be verbose, useful for debugging'))
    parser.add_option('--no-progress-bar', default=False, action='store_true',
                      help=_("Don't show progress bar."))
    return parser

def create_lrf(pages, profile, opts, thumbnail=None):
    width, height = PROFILES[profile]
    ps = {}
    ps['topmargin']      = 0
    ps['evensidemargin'] = 0
    ps['oddsidemargin']  = 0
    ps['textwidth']      = width
    ps['textheight']     = height
    book = Book(title=opts.title, author=opts.author,
            bookid=uuid4().hex,
            publisher='%s %s'%(__appname__, __version__), thumbnail=thumbnail,
            category='Comic', pagestyledefault=ps, 
            booksetting=BookSetting(screenwidth=width, screenheight=height))
    for page in pages:
        imageStream = ImageStream(page)
        _page = book.create_page()
        _page.append(ImageBlock(refstream=imageStream, 
                    blockwidth=width, blockheight=height, xsize=width, 
                    ysize=height, x1=width, y1=height))
        book.append(_page)
        
    book.renderLrf(open(opts.output, 'wb'))
    


def main(args=sys.argv, notification=None):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) < 2:
        parser.print_help()
        print '\nYou must specify a file to convert'
        return 1
    
    if not callable(notification):
        pb = ProgressBar(terminal_controller, _('Rendering comic pages...'), 
                         no_progress_bar=opts.no_progress_bar)
        notification = pb.update
    
    source = os.path.abspath(args[1])
    if not opts.title:
        opts.title = os.path.splitext(os.path.basename(source))
    if not opts.output:
        opts.output = os.path.abspath(os.path.splitext(os.path.basename(source))[0]+'.lrf')
        
    tdir  = extract_comic(source)
    pages = find_pages(tdir, sort_on_mtime=opts.no_sort, verbose=opts.verbose)
    if not pages:
        raise ValueError('Could not find any pages in the comic: %s'%source)
    pages, failures, tdir2 = process_pages(pages, opts, notification)
    if not pages:
        raise ValueError('Could not find any valid pages in the comic: %s'%source)
    if failures:
        print 'Could not process the following pages (run with --verbose to see why):'
        for f in failures:
            print '\t', f
    thumbnail = os.path.join(tdir2, 'thumbnail.png')
    if not os.access(thumbnail, os.R_OK):
        thumbnail = None
    create_lrf(pages, opts.profile, opts, thumbnail=thumbnail)
    shutil.rmtree(tdir)
    shutil.rmtree(tdir2)
    return 0

if __name__ == '__main__':
    sys.exit(main())