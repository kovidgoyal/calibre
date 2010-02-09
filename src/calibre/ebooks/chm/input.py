from __future__ import with_statement
''' CHM File decoding support '''
__license__ = 'GPL v3'
__copyright__  = '2008, Kovid Goyal <kovid at kovidgoyal.net>,' \
                 ' and Alex Bramley <a.bramley at gmail.com>.'

import sys, logging, os, re, shutil, subprocess, uuid
from shutil import rmtree
from tempfile import mkdtemp
from mimetypes import guess_type as guess_mimetype
from htmlentitydefs import name2codepoint
from pprint import PrettyPrinter

from BeautifulSoup import BeautifulSoup
from lxml import html, etree
from calibre.ebooks.chm.chm.chm import CHMFile
from calibre.ebooks.chm.chm.chmlib import (
  CHM_RESOLVE_SUCCESS, CHM_ENUMERATE_NORMAL,
  chm_enumerate, chm_retrieve_object,
)

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.utils.config import OptionParser
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf2 import OPFCreator, Guide
from calibre.ebooks.metadata.toc import TOC
from calibre.ebooks.lrf.html.convert_from import process_file as html_process_file
from calibre.utils.localization import get_lang
from calibre.utils.filenames import ascii_filename


def match_string(s1, s2_already_lowered):
    if s1 is not None and s2_already_lowered is not None:
        if s1.lower()==s2_already_lowered:
            return True
    return False

def option_parser():
    parser = OptionParser(usage=_('%prog [options] mybook.chm'))
    parser.add_option('--output-dir', '-d', default='.', help=_('Output directory. Defaults to current directory'), dest='output')
    parser.add_option('--verbose', default=False, action='store_true', dest='verbose')
    parser.add_option("-t", "--title", action="store", type="string", \
                    dest="title", help=_("Set the book title"))
    parser.add_option('--title-sort', action='store', type='string', default=None,
                      dest='title_sort', help=_('Set sort key for the title'))
    parser.add_option("-a", "--author", action="store", type="string", \
                    dest="author", help=_("Set the author"))
    parser.add_option('--author-sort', action='store', type='string', default=None,
                      dest='author_sort', help=_('Set sort key for the author'))
    parser.add_option("-c", "--category", action="store", type="string", \
                    dest="category", help=_("The category this book belongs"
                    " to. E.g.: History"))
    parser.add_option("--thumbnail", action="store", type="string", \
                    dest="thumbnail", help=_("Path to a graphic that will be"
                    " set as this files' thumbnail"))
    parser.add_option("--comment", action="store", type="string", \
                    dest="freetext", help=_("Path to a txt file containing a comment."))
    parser.add_option("--get-thumbnail", action="store_true", \
                    dest="get_thumbnail", default=False, \
                    help=_("Extract thumbnail from LRF file"))
    parser.add_option('--publisher', default=None, help=_('Set the publisher'))
    parser.add_option('--classification', default=None, help=_('Set the book classification'))
    parser.add_option('--creator', default=None, help=_('Set the book creator'))
    parser.add_option('--producer', default=None, help=_('Set the book producer'))
    parser.add_option('--get-cover', action='store_true', default=False,
                      help=_('Extract cover from LRF file. Note that the LRF format has no defined cover, so we use some heuristics to guess the cover.'))
    parser.add_option('--bookid', action='store', type='string', default=None,
                      dest='book_id', help=_('Set book ID'))
    parser.add_option('--font-delta', action='store', type='int', default=0,
                      dest='font_delta', help=_('Set font delta'))
    return parser

class CHMError(Exception):
    pass

class CHMReader(CHMFile):
    def __init__(self, input, log):
        CHMFile.__init__(self)
        if not self.LoadCHM(input):
            raise CHMError("Unable to open CHM file '%s'"%(input,))
        self.log = log
        self._sourcechm = input
        self._contents = None
        self._playorder = 0
        self._metadata = False
        self._extracted = False

        # location of '.hhc' file, which is the CHM TOC.
        self.root, ext = os.path.splitext(self.topics.lstrip('/'))
        self.hhc_path = self.root + ".hhc"


    def _parse_toc(self, ul, basedir=os.getcwdu()):
        toc = TOC(play_order=self._playorder, base_path=basedir, text='')
        self._playorder += 1
        for li in ul('li', recursive=False):
            href = li.object('param', {'name': 'Local'})[0]['value']
            if href.count('#'):
                href, frag = href.split('#')
            else:
                frag = None
            name = self._deentity(li.object('param', {'name': 'Name'})[0]['value'])
            #print "========>", name
            toc.add_item(href, frag, name, play_order=self._playorder)
            self._playorder += 1
            if li.ul:
               child = self._parse_toc(li.ul)
               child.parent = toc
               toc.append(child)
        #print toc
        return toc


    def GetFile(self, path):
        # have to have abs paths for ResolveObject, but Contents() deliberately
        # makes them relative. So we don't have to worry, re-add the leading /.
        # note this path refers to the internal CHM structure
        if path[0] != '/':
            path = '/' + path
        res, ui = self.ResolveObject(path)
        if res != CHM_RESOLVE_SUCCESS:
            raise CHMError("Unable to locate '%s' within CHM file '%s'"%(path, self.filename))
        size, data = self.RetrieveObject(ui)
        if size == 0:
            raise CHMError("'%s' is zero bytes in length!"%(path,))
        return data

    def ExtractFiles(self, output_dir=os.getcwdu()):
        for path in self.Contents():
            lpath = os.path.join(output_dir, path)
            self._ensure_dir(lpath)
            data = self.GetFile(path)
            with open(lpath, 'wb') as f:
                if guess_mimetype(path)[0] == ('text/html'):
                    data = self._reformat(data)
                f.write(data)
        #subprocess.call(['extract_chmLib.exe', self._sourcechm, output_dir])
        self._extracted = True

    def _reformat(self, data):
        try:
            html = BeautifulSoup(data)
        except UnicodeEncodeError:
            # hit some strange encoding problems...
            print "Unable to parse html for cleaning, leaving it :("
            return data
        # nuke javascript...
        [s.extract() for s in html('script')]
        # remove forward and back nav bars from the top/bottom of each page
        # cos they really fuck with the flow of things and generally waste space
        # since we can't use [a,b] syntax to select arbitrary items from a list
        # we'll have to do this manually...
        t = html('table')
        if t:
            if (t[0].previousSibling is None
              or t[0].previousSibling.previousSibling is None):
                t[0].extract()
            if (t[-1].nextSibling is None
              or t[-1].nextSibling.nextSibling is None):
                t[-1].extract()
        # for some very odd reason each page's content appears to be in a table
        # too. and this table has sub-tables for random asides... grr.

        # some images seem to be broken in some chm's :/
        for img in html('img'):
            try:
                # some are supposedly "relative"... lies.
                while img['src'].startswith('../'): img['src'] = img['src'][3:]
                # some have ";<junk>" at the end.
                img['src'] = img['src'].split(';')[0]
            except KeyError:
                # and some don't even have a src= ?!
                pass
        # now give back some pretty html.
        return html.prettify()

    def Contents(self):
        if self._contents is not None:
            return self._contents
        paths = []
        def get_paths(chm, ui, ctx):
            # skip directories
            # note this path refers to the internal CHM structure
            if ui.path[-1] != '/':
                # and make paths relative
                paths.append(ui.path.lstrip('/'))
        chm_enumerate(self.file, CHM_ENUMERATE_NORMAL, get_paths, None)
        self._contents = paths
        return self._contents

    def _ensure_dir(self, path):
        dir = os.path.dirname(path)
        if not os.path.isdir(dir):
            os.makedirs(dir)

    def extract_content(self, output_dir=os.getcwdu()):
        self.ExtractFiles(output_dir=output_dir)


class CHMInput(InputFormatPlugin):

    name        = 'CHM Input'
    author      = 'Kovid Goyal and Alex Bramley'
    description = 'Convert CHM files to OEB'
    file_types  = set(['chm'])

    options = set([
        OptionRecommendation(name='dummy_option', recommended_value=False,
            help=_('dummy option until real options are determined.')),
    ])

    def _chmtohtml(self, output_dir, chm_path, no_images, log):
        log.debug('Opening CHM file')
        rdr = CHMReader(chm_path, log)
        log.debug('Extracting CHM to %s' % output_dir)
        rdr.extract_content(output_dir)
        return rdr.hhc_path


    def convert(self, stream, options, file_ext, log, accelerators):
        from calibre.ebooks.metadata.chm import get_metadata_

        log.debug('Processing CHM...')
        tdir = mkdtemp(prefix='chm2oeb_')
        from calibre.customize.ui import plugin_for_input_format
        html_input = plugin_for_input_format('html')
        for opt in html_input.options:
            setattr(options, opt.option.name, opt.recommended_value)
        options.input_encoding = 'utf-8'
        no_images = False #options.no_images
        chm_name = stream.name
        #chm_data = stream.read()
        
        #closing stream so CHM can be opened by external library
        stream.close()
        log.debug('tdir=%s' % tdir)
        log.debug('stream.name=%s' % stream.name)
        mainname = self._chmtohtml(tdir, chm_name, no_images, log)
        mainpath = os.path.join(tdir, mainname)

        metadata = get_metadata_(tdir)

        cwd = os.getcwdu()
        odi = options.debug_pipeline
        options.debug_pipeline = None
        # try a custom conversion:
        #oeb = self._create_oebbook(mainpath, tdir, options, log, metadata)
        # try using html converter:
        htmlpath = self._create_html_root(mainpath, log)
        oeb = self._create_oebbook_html(htmlpath, tdir, options, log, metadata)
        options.debug_pipeline = odi
        #log.debug('DEBUG: Not removing tempdir %s' % tdir)
        shutil.rmtree(tdir)
        return oeb

    def _create_oebbook_html(self, htmlpath, basedir, opts, log, mi):
        # use HTMLInput plugin to generate book
        from calibre.ebooks.html.input import HTMLInput
        opts.breadth_first = True
        htmlinput = HTMLInput(None)
        oeb = htmlinput.create_oebbook(htmlpath, basedir, opts, log, mi)
        return oeb
        

    def _create_oebbook(self, hhcpath, basedir, opts, log, mi):
        from calibre.ebooks.conversion.plumber import create_oebbook
        from calibre.ebooks.oeb.base import DirContainer, \
            rewrite_links, urlnormalize, urldefrag, BINARY_MIME, OEB_STYLES, \
            xpath
        from calibre import guess_type
        import cssutils
        oeb = create_oebbook(log, None, opts, self,
                encoding=opts.input_encoding, populate=False)
        self.oeb = oeb

        metadata = oeb.metadata
        if mi.title:
            metadata.add('title', mi.title)
        if mi.authors:
            for a in mi.authors:
                metadata.add('creator', a, attrib={'role':'aut'})
        if mi.publisher:
            metadata.add('publisher', mi.publisher)
        if mi.isbn:
            metadata.add('identifier', mi.isbn, attrib={'scheme':'ISBN'})
        if not metadata.language:
            oeb.logger.warn(u'Language not specified')
            metadata.add('language', get_lang())
        if not metadata.creator:
            oeb.logger.warn('Creator not specified')
            metadata.add('creator', self.oeb.translate(__('Unknown')))
        if not metadata.title:
            oeb.logger.warn('Title not specified')
            metadata.add('title', self.oeb.translate(__('Unknown')))

        bookid = str(uuid.uuid4())
        metadata.add('identifier', bookid, id='uuid_id', scheme='uuid')
        for ident in metadata.identifier:
            if 'id' in ident.attrib:
                self.oeb.uid = metadata.identifier[0]
                break

        hhcdata = self._read_file(hhcpath)
        hhcroot = html.fromstring(hhcdata)
        chapters = self._process_nodes(hhcroot)
        #print "============================="
        #print "Printing hhcroot"
        #print etree.tostring(hhcroot, pretty_print=True)
        #print "============================="
        log.debug('Found %d section nodes' % len(chapters))
        
        if len(chapters) > 0:
            path0 = chapters[0][1]
            subpath = os.path.dirname(path0)
            htmlpath = os.path.join(basedir, subpath)

            oeb.container = DirContainer(htmlpath, log)
            for chapter in chapters:
                title = chapter[0]
                basename = os.path.basename(chapter[1])
                self._add_item(oeb, title, basename)

            oeb.container = DirContainer(htmlpath, oeb.log)
        return oeb

    def _create_html_root(self, hhcpath, log):
        hhcdata = self._read_file(hhcpath)
        hhcroot = html.fromstring(hhcdata)
        chapters = self._process_nodes(hhcroot)
        #print "============================="
        #print "Printing hhcroot"
        #print etree.tostring(hhcroot, pretty_print=True)
        #print "============================="
        log.debug('Found %d section nodes' % len(chapters))
        htmlpath = os.path.splitext(hhcpath)[0] + ".html"
        f = open(htmlpath, 'wb')
        f.write("<HTML><HEAD></HEAD><BODY>\r\n")

        if chapters:
            path0 = chapters[0][1]
            subpath = os.path.dirname(path0)

            for chapter in chapters:
                title = chapter[0]
                rsrcname = os.path.basename(chapter[1])
                rsrcpath = os.path.join(subpath, rsrcname)
                # title should already be url encoded
                url = "<br /><a href=" + rsrcpath + ">" + title + " </a>\r\n"
                f.write(url)

        f.write("</BODY></HTML>")
        f.close()
        return htmlpath


    def _read_file(self, name):
        f = open(name, 'rb')
        data = f.read()
        f.close()
        return data

    def _visit_node(self, node, chapters, depth):
        # check that node is a normal node (not a comment, DOCTYPE, etc.)
        # (normal nodes have string tags)
        if isinstance(node.tag, basestring):
            if match_string(node.tag, 'object') and match_string(node.attrib['type'], 'text/sitemap'):
                for child in node:
                    if match_string(child.tag,'param') and match_string(child.attrib['name'], 'name'):
                        chapter_title = child.attrib['value']
                    if match_string(child.tag,'param') and match_string(child.attrib['name'],'local'):
                        chapter_path = child.attrib['value']
                if chapter_title is not None and chapter_path is not None:
                    chapter = [chapter_title, chapter_path, depth]
                    chapters.append(chapter)
            if node.tag=="UL":
                depth = depth + 1
            if node.tag=="/UL":
                depth = depth - 1

    def _process_nodes(self, root):
        chapters = []
        depth = 0
        for node in root.iter():
            self._visit_node(node, chapters, depth)
        return chapters

    def _add_item(self, oeb, title, path):
        bname = os.path.basename(path)
        id, href = oeb.manifest.generate(id='html',
                href=ascii_filename(bname))
        item = oeb.manifest.add(id, href, 'text/html')
        item.html_input_href = bname
        oeb.spine.add(item, True)
        oeb.toc.add(title, item.href)

