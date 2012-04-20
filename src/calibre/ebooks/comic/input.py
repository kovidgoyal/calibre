from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Based on ideas from comiclrf created by FangornUK.
'''

import os, traceback, time
from Queue import Empty

from calibre import extract, prints, walk
from calibre.constants import filesystem_encoding
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.ipc.server import Server
from calibre.utils.ipc.job import ParallelJob

# If the specified screen has either dimension larger than this value, no image
# rescaling is done (we assume that it is a tablet output profile)
MAX_SCREEN_SIZE = 3000

def extract_comic(path_to_comic_file):
    '''
    Un-archive the comic file.
    '''
    tdir = PersistentTemporaryDirectory(suffix='_comic_extract')
    if not isinstance(tdir, unicode):
        # Needed in case the zip file has wrongly encoded unicode file/dir
        # names
        tdir = tdir.decode(filesystem_encoding)
    extract(path_to_comic_file, tdir)
    for x in walk(tdir):
        bn = os.path.basename(x)
        nbn = bn.replace('#', '_')
        if nbn != bn:
            os.rename(x, os.path.join(os.path.dirname(x), nbn))
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
            if '__MACOSX' in path: continue
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
        prints('Found comic pages...')
        prints('\t'+'\n\t'.join([os.path.basename(p) for p in pages]))
    return pages

class PageProcessor(list): # {{{
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
        from calibre.utils.magick import Image
        img = Image()
        img.open(self.path_to_page)
        width, height = img.size
        if self.num == 0: # First image so create a thumbnail from it
            thumb = img.clone
            thumb.thumbnail(60, 80)
            thumb.save(os.path.join(self.dest, 'thumbnail.png'))
        self.pages = [img]
        if width > height:
            if self.opts.landscape:
                self.rotate = True
            else:
                split1, split2 = img.clone, img.clone
                half = int(width/2)
                split1.crop(half-1, height, 0, 0)
                split2.crop(half-1, height, half, 0)
                self.pages = [split2, split1] if self.opts.right2left else [split1, split2]
        self.process_pages()

    def process_pages(self):
        from calibre.utils.magick import PixelWand
        for i, wand in enumerate(self.pages):
            pw = PixelWand()
            pw.color = '#ffffff'

            wand.set_border_color(pw)
            if self.rotate:
                wand.rotate(pw, -90)

            # 25 percent fuzzy trim?
            if not self.opts.disable_trim:
                wand.trim(25*65535/100)
            wand.set_page(0, 0, 0, 0)   #Clear page after trim, like a "+repage"
            # Do the Photoshop "Auto Levels" equivalent
            if not self.opts.dont_normalize:
                wand.normalize()
            sizex, sizey = wand.size

            SCRWIDTH, SCRHEIGHT = self.opts.output_profile.comic_screen_size

            try:
                if self.opts.comic_image_size:
                    SCRWIDTH, SCRHEIGHT = map(int, [x.strip() for x in
                        self.opts.comic_image_size.split('x')])
            except:
                pass # Ignore

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
                if newsizex < MAX_SCREEN_SIZE and newsizey < MAX_SCREEN_SIZE:
                    # Too large and resizing fails, so better
                    # to leave it as original size
                    wand.size = (newsizex, newsizey)
                    wand.set_border_color(pw)
                    wand.add_border(pw, deltax, deltay)
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
                if newsizex < MAX_SCREEN_SIZE and newsizey < MAX_SCREEN_SIZE:
                    # Too large and resizing fails, so better
                    # to leave it as original size
                    wand.size = (newsizex, newsizey)
                    wand.set_border_color(pw)
                    wand.add_border(pw, deltax, deltay)
            else:
                if SCRWIDTH < MAX_SCREEN_SIZE and SCRHEIGHT < MAX_SCREEN_SIZE:
                    wand.size = (SCRWIDTH, SCRHEIGHT)

            if not self.opts.dont_sharpen:
                wand.sharpen(0.0, 1.0)

            if not self.opts.dont_grayscale:
                wand.type = 'GrayscaleType'

            if self.opts.despeckle:
                wand.despeckle()

            wand.quantize(self.opts.colors)
            dest = '%d_%d.%s'%(self.num, i, self.opts.output_format)
            dest = os.path.join(self.dest, dest)
            if dest.lower().endswith('.png'):
                dest += '8'
            wand.save(dest)
            if dest.endswith('8'):
                dest = dest[:-1]
                os.rename(dest+'8', dest)
            self.append(dest)
# }}}

def render_pages(tasks, dest, opts, notification=lambda x, y: x):
    '''
    Entry point for the job server.
    '''
    failures, pages = [], []
    for num, path in tasks:
        try:
            pages.extend(PageProcessor(path, dest, opts, num))
            msg = _('Rendered %s')%path
        except:
            failures.append(path)
            msg = _('Failed %s')%path
            if opts.verbose:
                msg += '\n' + traceback.format_exc()
        prints(msg)
        notification(0.5, msg)

    return pages, failures


class Progress(object):

    def __init__(self, total, update):
        self.total  = total
        self.update = update
        self.done   = 0

    def __call__(self, percent, msg=''):
        self.done += 1
        #msg = msg%os.path.basename(job.args[0])
        self.update(float(self.done)/self.total, msg)

def process_pages(pages, opts, update, tdir):
    '''
    Render all identified comic pages.
    '''
    progress = Progress(len(pages), update)
    server = Server()
    jobs = []
    tasks = [(p, os.path.join(tdir, os.path.basename(p))) for p in pages]
    tasks = server.split(pages)
    for task in tasks:
        jobs.append(ParallelJob('render_pages', '', progress,
                                args=[task, tdir, opts]))
        server.add_job(jobs[-1])
    while True:
        time.sleep(1)
        running = False
        for job in jobs:
            while True:
                try:
                    x = job.notifications.get_nowait()
                    progress(*x)
                except Empty:
                    break
            job.update()
            if not job.is_finished:
                running = True
        if not running:
            break
    server.close()
    ans, failures = [], []

    for job in jobs:
        if job.failed or job.result is None:
            raise Exception(_('Failed to process comic: \n\n%s')%
                    job.log_file.read())
        pages, failures_ = job.result
        ans += pages
        failures += failures_
    return ans, failures



