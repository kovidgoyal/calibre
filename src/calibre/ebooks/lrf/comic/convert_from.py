from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Based on ideas from comiclrf created by FangornUK.
'''

import os, sys, shutil, traceback, textwrap,  glob, fnmatch
from uuid import uuid4




from calibre import extract, terminal_controller, __appname__, __version__
from calibre.utils.config import Config, StringConfig
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.parallel import Server, ParallelJob
from calibre.utils.terminfo import ProgressBar
from calibre.ebooks.lrf.pylrs.pylrs import Book, BookSetting, ImageStream, ImageBlock
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf import OPFCreator
from calibre.ebooks.epub.from_html import config as html2epub_config, convert as html2epub
from calibre.customize.ui import run_plugins_on_preprocess
try:
    from calibre.utils.PythonMagickWand import \
            NewMagickWand, NewPixelWand, \
            MagickSetImageBorderColor, \
            MagickReadImage, MagickRotateImage, \
            MagickTrimImage, PixelSetColor,\
            MagickNormalizeImage, MagickGetImageWidth, \
            MagickGetImageHeight, \
            MagickResizeImage, MagickSetImageType, \
            GrayscaleType, CatromFilter,  MagickSetImagePage, \
            MagickBorderImage, MagickSharpenImage, MagickDespeckleImage, \
            MagickQuantizeImage, RGBColorspace, \
            MagickWriteImage, DestroyPixelWand, \
            DestroyMagickWand, CloneMagickWand, \
            MagickThumbnailImage, MagickCropImage, ImageMagick
    _imagemagick_loaded = True
except:
    _imagemagick_loaded = False

PROFILES = {
            # Name : (width, height) in pixels
            'prs500':(584, 754),
            # The SONY's LRF renderer (on the PRS500) only uses the first 800x600 block of the image 
            'prs500-landscape': (784, 1012)
            }

def extract_comic(path_to_comic_file):
    '''
    Un-archive the comic file.
    '''
    tdir = PersistentTemporaryDirectory(suffix='_comic_extract')
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
    Contains the actual image rendering logic. See :method:`render` and 
    :method:`process_pages`.
    '''
    
    def __init__(self, path_to_page, dest, opts, num):
        list.__init__(self)
        self.path_to_page = path_to_page
        self.opts         = opts
        self.num          = num
        self.dest         = dest
        self.rotate       = False
        self.render()
        
        
    def render(self):
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
                DestroyMagickWand(img)
                if split1 < 0 or split2 < 0:
                    raise RuntimeError('Cannot create wand.')
                MagickCropImage(split1, (width/2)-1, height, 0, 0)
                MagickCropImage(split2, (width/2)-1, height, width/2, 0 )
                self.pages = [split2, split1] if self.opts.right2left else [split1, split2]
        self.process_pages()
        
    def process_pages(self):
        for i, wand in enumerate(self.pages):
            pw = NewPixelWand()
            try:
                if pw < 0:
                    raise RuntimeError('Cannot create wand.')
                PixelSetColor(pw, 'white')
                
                MagickSetImageBorderColor(wand, pw)
                if self.rotate:
                    MagickRotateImage(wand, pw, -90)
                    
                # 25 percent fuzzy trim?
                MagickTrimImage(wand, 25*65535/100)
                MagickSetImagePage(wand, 0,0,0,0)   #Clear page after trim, like a "+repage"
                # Do the Photoshop "Auto Levels" equivalent
                if not self.opts.dont_normalize:
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
                elif self.opts.wide:
                    # Keep aspect and Use device height as scaled image width so landscape mode is clean
                    aspect = float(sizex) / float(sizey)
                    screen_aspect = float(SCRWIDTH) / float(SCRHEIGHT)
                    # Get dimensions of the landscape mode screen
                    # Add 25px back to height for the battery bar.
                    wscreenx = SCRHEIGHT + 25
                    wscreeny = int(wscreenx / screen_aspect)
                    if aspect <= screen_aspect:
                        newsizey = wscreeny
                        newsizex = int(newsizey * aspect)
                        deltax = (wscreenx - newsizex) / 2
                        deltay = 0
                    else:
                        newsizex = wscreenx
                        newsizey = int(newsizex / aspect)
                        deltax = 0
                        deltay = (wscreeny - newsizey) / 2
                    MagickResizeImage(wand, newsizex, newsizey, CatromFilter, 1.0)
                    MagickSetImageBorderColor(wand, pw)
                    MagickBorderImage(wand, pw, deltax, deltay)
                else:
                    MagickResizeImage(wand, SCRWIDTH, SCRHEIGHT, CatromFilter, 1.0)
                    
                if not self.opts.dont_sharpen:
                    MagickSharpenImage(wand, 0.0, 1.0)
                    
                MagickSetImageType(wand, GrayscaleType)
                
                if self.opts.despeckle:
                    MagickDespeckleImage(wand)
                
                MagickQuantizeImage(wand, self.opts.colors, RGBColorspace, 0, 1, 0)
                dest = '%d_%d.png'%(self.num, i)
                dest = os.path.join(self.dest, dest)
                MagickWriteImage(wand, dest+'8')
                os.rename(dest+'8', dest)
                self.append(dest)
            finally:
                if pw > 0:
                    DestroyPixelWand(pw)
                DestroyMagickWand(wand)
            
def render_pages(tasks, dest, opts, notification=None):
    '''
    Entry point for the job server.
    '''
    failures, pages = [], []
    with ImageMagick():
        for num, path in tasks:
            try:
                pages.extend(PageProcessor(path, dest, opts, num))
                msg = _('Rendered %s') 
            except:
                failures.append(path)
                msg = _('Failed %s')
                if opts.verbose:
                    msg += '\n' + traceback.format_exc() 
            msg = msg%path
            if notification is not None:
                notification(0.5, msg)
    
    return pages, failures
        
            
class JobManager(object):
    '''
    Simple job manager responsible for keeping track of overall progress.
    '''
    
    def __init__(self, total, update):
        self.total  = total
        self.update = update
        self.done   = 0
        self.add_job        = lambda j: j
        self.output         = lambda j: j
        self.start_work     = lambda j: j
        self.job_done       = lambda j: j
        
    def status_update(self, job):
        self.done += 1
        #msg = msg%os.path.basename(job.args[0])
        self.update(float(self.done)/self.total, job.msg)
        
def process_pages(pages, opts, update):
    '''
    Render all identified comic pages.
    '''
    if not _imagemagick_loaded:
        raise RuntimeError('Failed to load ImageMagick')
    
    tdir = PersistentTemporaryDirectory('_comic2lrf_pp')
    job_manager = JobManager(len(pages), update)
    server = Server()
    jobs = []
    tasks = server.split(pages)
    for task in tasks:
        jobs.append(ParallelJob('render_pages', lambda s:s, job_manager=job_manager,
                                args=[task, tdir, opts]))
        server.add_job(jobs[-1])
    server.wait()
    server.killall()
    server.close()
    ans, failures = [], []
        
    for job in jobs:
        if job.result is None:
            raise Exception(_('Failed to process comic: %s\n\n%s')%(job.exception, job.traceback))
        pages, failures_ = job.result
        ans += pages
        failures += failures_
    return ans, failures, tdir
    
def config(defaults=None,output_format='lrf'):
    desc = _('Options to control the conversion of comics (CBR, CBZ) files into ebooks')
    if defaults is None:
        c = Config('comic', desc)
    else:
        c = StringConfig(defaults, desc)
    c.add_opt('title', ['-t', '--title'],
              help=_('Title for generated ebook. Default is to use the filename.'))
    c.add_opt('author', ['-a', '--author'],
              help=_('Set the author in the metadata of the generated ebook. Default is %default'),
              default=_('Unknown'))
    c.add_opt('output', ['-o', '--output'],
              help=_('Path to output file. By default a file is created in the current directory.'))
    c.add_opt('colors', ['-c', '--colors'], type='int', default=64,
              help=_('Number of colors for grayscale image conversion. Default: %default'))
    c.add_opt('dont_normalize', ['-n', '--disable-normalize'], default=False,
              help=_('Disable normalize (improve contrast) color range for pictures. Default: False'))
    c.add_opt('keep_aspect_ratio', ['-r', '--keep-aspect-ratio'], default=False,
              help=_('Maintain picture aspect ratio. Default is to fill the screen.'))
    c.add_opt('dont_sharpen', ['-s', '--disable-sharpen'], default=False,
              help=_('Disable sharpening.'))
    c.add_opt('landscape', ['-l', '--landscape'], default=False,
              help=_("Don't split landscape images into two portrait images"))
    c.add_opt('wide', ['-w', '--wide-aspect'], default=False,
              help=_("Keep aspect ratio and scale image using screen height as image width for viewing in landscape mode."))
    c.add_opt('right2left', ['--right2left'], default=False, action='store_true',
              help=_('Used for right-to-left publications like manga. Causes landscape pages to be split into portrait pages from right to left.'))
    c.add_opt('despeckle', ['-d', '--despeckle'], default=False,
              help=_('Enable Despeckle. Reduces speckle noise. May greatly increase processing time.'))
    c.add_opt('no_sort', ['--no-sort'], default=False,
              help=_("Don't sort the files found in the comic alphabetically by name. Instead use the order they were added to the comic."))
    c.add_opt('profile', ['-p', '--profile'], default='prs500', choices=PROFILES.keys(),
              help=_('Choose a profile for the device you are generating this file for. The default is the SONY PRS-500 with a screen size of 584x754 pixels. This is suitable for any reader with the same screen size. Choices are %s')%PROFILES.keys())
    c.add_opt('verbose', ['-v', '--verbose'], default=0, action='count',
              help=_('Be verbose, useful for debugging. Can be specified multiple times for greater verbosity.'))
    c.add_opt('no_progress_bar', ['--no-progress-bar'], default=False,
                      help=_("Don't show progress bar."))
    if output_format == 'pdf':
        c.add_opt('no_process',['--no_process'], default=False,
    		      help=_("Apply no processing to the image"))
    return c

def option_parser(output_format='lrf'):
    c = config(output_format=output_format)
    return c.option_parser(usage=_('''\
%prog [options] comic.cb[z|r]

Convert a comic in a CBZ or CBR file to an ebook. 
'''))

def create_epub(pages, profile, opts, thumbnail=None):
    wrappers = []
    WRAPPER = textwrap.dedent('''\
    <html>
        <head>
            <title>Page #%d</title>
            <style type="text/css">@page {margin:0pt; padding: 0pt;}</style>
        </head>
        <body style="margin: 0pt; padding: 0pt">
            <div style="text-align:center">
                <img src="%s" alt="comic page #%d" />
            </div>
        </body>
    </html>        
    ''')
    dir = os.path.dirname(pages[0])
    for i, page in enumerate(pages):
        wrapper = WRAPPER%(i+1, os.path.basename(page), i+1)
        page = os.path.join(dir, 'page_%d.html'%(i+1))
        open(page, 'wb').write(wrapper)
        wrappers.append(page)
        
    mi  = MetaInformation(opts.title, [opts.author])
    opf = OPFCreator(dir, mi)
    opf.create_manifest([(w, None) for w in wrappers])
    opf.create_spine(wrappers)
    metadata = os.path.join(dir, 'metadata.opf')
    opf.render(open(metadata, 'wb'))
    opts2 = html2epub_config('margin_left=0\nmargin_right=0\nmargin_top=0\nmargin_bottom=0').parse()
    opts2.output = opts.output
    html2epub(metadata, opts2)

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
    print _('Output written to'), opts.output
    

def create_pdf(pages, profile, opts, thumbnail=None,toc=None):
    width, height = PROFILES[profile]
    
    from reportlab.pdfgen import canvas

    cur_page=0
    heading = []
    if toc != None:
        if len(toc) == 1:
            toc = None
        else:
            toc_index = 0
            base_cur = 0
            rem = 0
            breaker = False
            while True:
                letter=toc[0][0][base_cur]
                for i in range(len(toc)):
                    if letter != toc[i][0][base_cur]:
                        breaker = True
                if breaker:
                    break
                if letter == os.sep:
                    rem=base_cur
                base_cur += 1
            toc.append(("Not seen",-1))
            toc_last=''

    
    pdf = canvas.Canvas(filename=opts.output, pagesize=(width,height+15))
    pdf.setAuthor(opts.author)
    pdf.setTitle(opts.title)


    for page in pages:
        if opts.keep_aspect_ratio:
            img = NewMagickWand()
            if img < 0:
                raise RuntimeError('Cannot create wand.')
            if not MagickReadImage(img, page):
                raise IOError('Failed to read image from: %'%self.path_to_page)
            sizex  = MagickGetImageWidth(img)
            sizey = MagickGetImageHeight(img)
            if opts.keep_aspect_ratio:
                # Preserve the aspect ratio by adding border
                aspect = float(sizex) / float(sizey)
                if aspect <= (float(width) / float(height)):
                    newsizey = height 
                    newsizex = int(newsizey * aspect)
                    deltax = (width - newsizex) / 2
                    deltay = 0
                else:
                    newsizex = width 
                    newsizey = int(newsizex / aspect)
                    deltax = 0
                    deltay = (height - newsizey) / 2
            pdf.drawImage(page, x=deltax,y=deltay,width=newsizex, height=newsizey)
        else:
            pdf.drawImage(page, x=0,y=0,width=width, height=height) 
        if toc != None:
            if toc[toc_index][1] == cur_page:
                tmp=toc[toc_index][0]
                toc_current=tmp[rem:len(tmp)-4]
                index=0
                while True:
                    key = 'page%d-%d' % (cur_page, index)
                    pdf.bookmarkPage(key)
                    (head,dummy,list)=toc_current.partition(os.sep)
                    try:
                        if heading[index] != head:
                            heading[index] = head
                            pdf.addOutlineEntry(title=head,key=key,level=index)
                    except:
                        heading.append(head)
                        pdf.addOutlineEntry(title=head,key=key,level=index)
                    index += 1
                    toc_current=list
                    if dummy == "":
                        break
                toc_index += 1
            cur_page += 1
        pdf.showPage()
    # Write the document to disk
    pdf.save() 

    
def do_convert(path_to_file, opts, notification=lambda m, p: p, output_format='lrf'):
    path_to_file = run_plugins_on_preprocess(path_to_file)
    source = path_to_file
    to_delete = []
    toc = []
    list = [] 
    pages = []

    
    if not opts.title:
        opts.title = os.path.splitext(os.path.basename(source))[0]
    if not opts.output:
        opts.output = os.path.abspath(os.path.splitext(os.path.basename(source))[0]+'.'+output_format)
    if os.path.isdir(source):
        for path in all_files( source , '*.cbr|*.cbz' ):
            list.append( path )
    else:
            list= [ os.path.abspath(source) ]

    for source in list:
        tdir  = extract_comic(source)
        new_pages = find_pages(tdir, sort_on_mtime=opts.no_sort, verbose=opts.verbose)
        thumbnail = None
        if not new_pages:
            raise ValueError('Could not find any pages in the comic: %s'%source)
        if not getattr(opts, 'no_process', False):
            new_pages, failures, tdir2 = process_pages(new_pages, opts, notification)
            if not new_pages:
                 raise ValueError('Could not find any valid pages in the comic: %s'%source)
            if failures:
            	print 'Could not process the following pages (run with --verbose to see why):'
            	for f in failures:
                	print '\t', f
            thumbnail = os.path.join(tdir2, 'thumbnail.png')
            if not os.access(thumbnail, os.R_OK):
                thumbnail = None
        toc.append((source,len(pages)))
        pages.extend(new_pages)
        to_delete.append(tdir)


    if output_format == 'lrf':
        create_lrf(pages, opts.profile, opts, thumbnail=thumbnail)
    if output_format == 'epub':
        create_epub(pages, opts.profile, opts, thumbnail=thumbnail)
    if output_format == 'pdf':
        create_pdf(pages, opts.profile, opts, thumbnail=thumbnail,toc=toc)
    for tdir in to_delete:
        shutil.rmtree(tdir)


def all_files(root, patterns='*'):
    # Expand patterns from semicolon-separated string to list
    patterns = patterns.split('|')
    for path, subdirs, files in os.walk(root):
        files.sort( )
        for name in files:
            for pattern in patterns:
                if fnmatch.fnmatch(name, pattern):
                    yield os.path.join(path, name)
                    break


def main(args=sys.argv, notification=None, output_format='lrf'):
    parser = option_parser(output_format=output_format)
    opts, args = parser.parse_args(args)
    if len(args) < 2:
        parser.print_help()
        print '\nYou must specify a file to convert'
        return 1
    
    if not callable(notification):
        pb = ProgressBar(terminal_controller, _('Rendering comic pages...'), 
                         no_progress_bar=opts.no_progress_bar or getattr(opts, 'no_process', False))
        notification = pb.update
    
    source = os.path.abspath(args[1])
    do_convert(source, opts, notification, output_format=output_format)
    return 0

if __name__ == '__main__':
    sys.exit(main())
