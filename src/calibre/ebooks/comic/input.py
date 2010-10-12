from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Based on ideas from comiclrf created by FangornUK.
'''

import os, shutil, traceback, textwrap, time, codecs
from Queue import Empty

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre import extract, CurrentDir, prints
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.ipc.server import Server
from calibre.utils.ipc.job import ParallelJob

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
                wand.size = (newsizex, newsizey)
                wand.set_border_color(pw)
                wand.add_border(pw, deltax, deltay)
            else:
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


class ComicInput(InputFormatPlugin):

    name        = 'Comic Input'
    author      = 'Kovid Goyal'
    description = 'Optimize comic files (.cbz, .cbr, .cbc) for viewing on portable devices'
    file_types  = set(['cbz', 'cbr', 'cbc'])
    is_image_collection = True
    core_usage = -1

    options = set([
        OptionRecommendation(name='colors', recommended_value=256,
            help=_('Number of colors for grayscale image conversion. Default: '
                '%default. Values of less than 256 may result in blurred text '
                'on your device if you are creating your comics in EPUB format.')),
        OptionRecommendation(name='dont_normalize', recommended_value=False,
            help=_('Disable normalize (improve contrast) color range '
            'for pictures. Default: False')),
        OptionRecommendation(name='keep_aspect_ratio', recommended_value=False,
            help=_('Maintain picture aspect ratio. Default is to fill the screen.')),
        OptionRecommendation(name='dont_sharpen', recommended_value=False,
            help=_('Disable sharpening.')),
        OptionRecommendation(name='disable_trim', recommended_value=False,
            help=_('Disable trimming of comic pages. For some comics, '
                     'trimming might remove content as well as borders.')),
        OptionRecommendation(name='landscape', recommended_value=False,
            help=_("Don't split landscape images into two portrait images")),
        OptionRecommendation(name='wide', recommended_value=False,
            help=_("Keep aspect ratio and scale image using screen height as "
            "image width for viewing in landscape mode.")),
        OptionRecommendation(name='right2left', recommended_value=False,
              help=_('Used for right-to-left publications like manga. '
              'Causes landscape pages to be split into portrait pages '
              'from right to left.')),
        OptionRecommendation(name='despeckle', recommended_value=False,
              help=_('Enable Despeckle. Reduces speckle noise. '
              'May greatly increase processing time.')),
        OptionRecommendation(name='no_sort', recommended_value=False,
              help=_("Don't sort the files found in the comic "
              "alphabetically by name. Instead use the order they were "
              "added to the comic.")),
        OptionRecommendation(name='output_format', choices=['png', 'jpg'],
            recommended_value='png', help=_('The format that images in the created ebook '
                'are converted to. You can experiment to see which format gives '
                'you optimal size and look on your device.')),
        OptionRecommendation(name='no_process', recommended_value=False,
              help=_("Apply no processing to the image")),
        OptionRecommendation(name='dont_grayscale', recommended_value=False,
            help=_('Do not convert the image to grayscale (black and white)'))
        ])

    recommendations = set([
        ('margin_left', 0, OptionRecommendation.HIGH),
        ('margin_top',  0, OptionRecommendation.HIGH),
        ('margin_right', 0, OptionRecommendation.HIGH),
        ('margin_bottom', 0, OptionRecommendation.HIGH),
        ('insert_blank_line', False, OptionRecommendation.HIGH),
        ('remove_paragraph_spacing',  False, OptionRecommendation.HIGH),
        ('change_justification', 'left', OptionRecommendation.HIGH),
        ('dont_split_on_pagebreaks', True, OptionRecommendation.HIGH),
        ('chapter', None, OptionRecommendation.HIGH),
        ('page_breaks_brefore', None, OptionRecommendation.HIGH),
        ('use_auto_toc', False, OptionRecommendation.HIGH),
        ('page_breaks_before', None, OptionRecommendation.HIGH),
        ('disable_font_rescaling', True, OptionRecommendation.HIGH),
        ('linearize_tables', False, OptionRecommendation.HIGH),
        ])

    def get_comics_from_collection(self, stream):
        from calibre.libunzip import extract as zipextract
        tdir = PersistentTemporaryDirectory('_comic_collection')
        zipextract(stream, tdir)
        comics = []
        with CurrentDir(tdir):
            if not os.path.exists('comics.txt'):
                raise ValueError('%s is not a valid comic collection'
                        %stream.name)
            raw = open('comics.txt', 'rb').read()
            if raw.startswith(codecs.BOM_UTF16_BE):
                raw = raw.decode('utf-16-be')[1:]
            elif raw.startswith(codecs.BOM_UTF16_LE):
                raw = raw.decode('utf-16-le')[1:]
            elif raw.startswith(codecs.BOM_UTF8):
                raw = raw.decode('utf-8')[1:]
            else:
                raw = raw.decode('utf-8')
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                fname, title = line.partition(':')[0], line.partition(':')[-1]
                fname = os.path.join(tdir, *fname.split('/'))
                if not title:
                    title = os.path.basename(fname).rpartition('.')[0]
                if os.access(fname, os.R_OK):
                    comics.append([title, fname])
        if not comics:
            raise ValueError('%s has no comics'%stream.name)
        return comics

    def get_pages(self, comic, tdir2):
        tdir  = extract_comic(comic)
        new_pages = find_pages(tdir, sort_on_mtime=self.opts.no_sort,
                verbose=self.opts.verbose)
        thumbnail = None
        if not new_pages:
            raise ValueError('Could not find any pages in the comic: %s'
                    %comic)
        if self.opts.no_process:
            n2 = []
            for page in new_pages:
                n2.append(os.path.join(tdir2, os.path.basename(page)))
                shutil.copyfile(page, n2[-1])
            new_pages = n2
        else:
            new_pages, failures = process_pages(new_pages, self.opts,
                    self.report_progress, tdir2)
            if failures:
                self.log.warning('Could not process the following pages '
                '(run with --verbose to see why):')
                for f in failures:
                    self.log.warning('\t', f)
            if not new_pages:
                raise ValueError('Could not find any valid pages in comic: %s'
                        % comic)
            thumbnail = os.path.join(tdir2,
                    'thumbnail.'+self.opts.output_format.lower())
            if not os.access(thumbnail, os.R_OK):
                thumbnail = None
        return new_pages

    def get_images(self):
        return self._images

    def convert(self, stream, opts, file_ext, log, accelerators):
        from calibre.ebooks.metadata import MetaInformation
        from calibre.ebooks.metadata.opf2 import OPFCreator
        from calibre.ebooks.metadata.toc import TOC

        self.opts, self.log= opts, log
        if file_ext == 'cbc':
            comics_ = self.get_comics_from_collection(stream)
        else:
            comics_ = [['Comic', os.path.abspath(stream.name)]]
        stream.close()
        comics = []
        for i, x in enumerate(comics_):
            title, fname = x
            cdir = 'comic_%d'%(i+1) if len(comics_) > 1 else '.'
            cdir = os.path.abspath(cdir)
            if not os.path.exists(cdir):
                os.makedirs(cdir)
            pages = self.get_pages(fname, cdir)
            if not pages: continue
            wrappers = self.create_wrappers(pages)
            comics.append((title, pages, wrappers))

        if not comics:
            raise ValueError('No comic pages found in %s'%stream.name)

        mi  = MetaInformation(os.path.basename(stream.name).rpartition('.')[0],
            [_('Unknown')])
        opf = OPFCreator(os.path.abspath('.'), mi)
        entries = []

        def href(x):
            if len(comics) == 1: return os.path.basename(x)
            return '/'.join(x.split(os.sep)[-2:])

        for comic in comics:
            pages, wrappers = comic[1:]
            entries += [(w, None) for w in map(href, wrappers)] + \
                    [(x, None) for x in map(href, pages)]
        opf.create_manifest(entries)
        spine = []
        for comic in comics:
            spine.extend(map(href, comic[2]))
        self._images = []
        for comic in comics:
            self._images.extend(comic[1])
        opf.create_spine(spine)
        toc = TOC()
        if len(comics) == 1:
            wrappers = comics[0][2]
            for i, x in enumerate(wrappers):
                toc.add_item(href(x), None, _('Page')+' %d'%(i+1),
                        play_order=i)
        else:
            po = 0
            for comic in comics:
                po += 1
                wrappers = comic[2]
                stoc = toc.add_item(href(wrappers[0]),
                        None, comic[0], play_order=po)
                for i, x in enumerate(wrappers):
                    stoc.add_item(href(x), None,
                            _('Page')+' %d'%(i+1), play_order=po)
                    po += 1
        opf.set_toc(toc)
        m, n = open('metadata.opf', 'wb'), open('toc.ncx', 'wb')
        opf.render(m, n, 'toc.ncx')
        return os.path.abspath('metadata.opf')

    def create_wrappers(self, pages):
        from calibre.ebooks.oeb.base import XHTML_NS
        wrappers = []
        WRAPPER = textwrap.dedent('''\
        <html xmlns="%s">
            <head>
                <title>Page #%d</title>
                <style type="text/css">
                    @page { margin:0pt; padding: 0pt}
                    body { margin: 0pt; padding: 0pt}
                    div { text-align: center }
                </style>
            </head>
            <body>
                <div>
                    <img src="%s" alt="comic page #%d" />
                </div>
            </body>
        </html>
        ''')
        dir = os.path.dirname(pages[0])
        for i, page in enumerate(pages):
            wrapper = WRAPPER%(XHTML_NS, i+1, os.path.basename(page), i+1)
            page = os.path.join(dir, 'page_%d.xhtml'%(i+1))
            open(page, 'wb').write(wrapper)
            wrappers.append(page)
        return wrappers

