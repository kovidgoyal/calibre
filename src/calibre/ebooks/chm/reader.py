''' CHM File decoding support '''
__license__ = 'GPL v3'
__copyright__  = '2008, Kovid Goyal <kovid at kovidgoyal.net>,' \
                 ' and Alex Bramley <a.bramley at gmail.com>.'

import codecs
import os
import re

from calibre import guess_type as guess_mimetype
from calibre.constants import filesystem_encoding, iswindows
from calibre.ebooks.BeautifulSoup import BeautifulSoup, NavigableString
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata.toc import TOC
from chm.chm import CHMFile, chmlib
from polyglot.builtins import as_unicode


def match_string(s1, s2_already_lowered):
    if s1 is not None and s2_already_lowered is not None:
        if s1.lower()==s2_already_lowered:
            return True
    return False


def check_all_prev_empty(tag):
    if tag is None:
        return True
    if tag.__class__ == NavigableString and not check_empty(tag):
        return False
    return check_all_prev_empty(tag.previousSibling)


def check_empty(s, rex=re.compile(r'\S')):
    return rex.search(s) is None


class CHMError(Exception):
    pass


class CHMReader(CHMFile):

    def __init__(self, input, log, input_encoding=None):
        CHMFile.__init__(self)
        if isinstance(input, str):
            enc = 'mbcs' if iswindows else filesystem_encoding
            try:
                input = input.encode(enc)
            except UnicodeEncodeError:
                from calibre.ptempfile import PersistentTemporaryFile
                with PersistentTemporaryFile(suffix='.chm') as t:
                    t.write(open(input, 'rb').read())
                input = t.name
        if not self.LoadCHM(input):
            raise CHMError("Unable to open CHM file '%s'"%(input,))
        self.log = log
        self.input_encoding = input_encoding
        self._sourcechm = input
        self._contents = None
        self._playorder = 0
        self._metadata = False
        self._extracted = False
        self.re_encoded_files = set()
        self.get_encodings()
        if self.home:
            self.home = self.decode_hhp_filename(self.home)
        if self.topics:
            self.topics = self.decode_hhp_filename(self.topics)

        # location of '.hhc' file, which is the CHM TOC.
        base = self.topics or self.home
        self.root = os.path.splitext(base.lstrip('/'))[0]
        self.hhc_path = self.root + ".hhc"

    def decode_hhp_filename(self, path):
        if isinstance(path, str):
            return path
        for enc in (self.encoding_from_system_file, self.encoding_from_lcid, 'cp1252', 'cp1251', 'latin1', 'utf-8'):
            if enc:
                try:
                    q = path.decode(enc)
                except UnicodeDecodeError:
                    continue
                res, ui = self.ResolveObject(q)
                if res == chmlib.CHM_RESOLVE_SUCCESS:
                    return q

    def get_encodings(self):
        self.encoding_from_system_file = self.encoding_from_lcid = None
        q = self.GetEncoding()
        if q:
            try:
                if isinstance(q, bytes):
                    q = q.decode('ascii')
                    codecs.lookup(q)
                    self.encoding_from_system_file = q
            except Exception:
                pass

        lcid = self.GetLCID()
        if lcid is not None:
            q = lcid[0]
            if q:
                try:
                    if isinstance(q, bytes):
                        q = q.decode('ascii')
                        codecs.lookup(q)
                        self.encoding_from_lcid = q
                except Exception:
                    pass

    def get_encoding(self):
        return self.encoding_from_system_file or self.encoding_from_lcid or 'cp1252'

    def _parse_toc(self, ul, basedir=os.getcwd()):
        toc = TOC(play_order=self._playorder, base_path=basedir, text='')
        self._playorder += 1
        for li in ul('li', recursive=False):
            href = li.object('param', {'name': 'Local'})[0]['value']
            if href.count('#'):
                href, frag = href.split('#')
            else:
                frag = None
            name = self._deentity(li.object('param', {'name': 'Name'})[0]['value'])
            # print "========>", name
            toc.add_item(href, frag, name, play_order=self._playorder)
            self._playorder += 1
            if li.ul:
                child = self._parse_toc(li.ul)
                child.parent = toc
                toc.append(child)
        # print toc
        return toc

    def ResolveObject(self, path):
        # filenames are utf-8 encoded in the chm index as far as I can
        # determine, see https://tika.apache.org/1.11/api/org/apache/tika/parser/chm/accessor/ChmPmgiHeader.html
        if not isinstance(path, bytes):
            path = path.encode('utf-8')
        return CHMFile.ResolveObject(self, path)

    def GetFile(self, path):
        # have to have abs paths for ResolveObject, but Contents() deliberately
        # makes them relative. So we don't have to worry, re-add the leading /.
        # note this path refers to the internal CHM structure
        if path[0] != '/':
            path = '/' + path
        res, ui = self.ResolveObject(path)
        if res != chmlib.CHM_RESOLVE_SUCCESS:
            raise CHMError(f"Unable to locate {path!r} within CHM file {self.filename!r}")
        size, data = self.RetrieveObject(ui)
        if size == 0:
            raise CHMError(f"{path!r} is zero bytes in length!")
        return data

    def get_home(self):
        return self.GetFile(self.home)

    def ExtractFiles(self, output_dir=os.getcwd(), debug_dump=False):
        html_files = set()
        for path in self.Contents():
            fpath = path
            lpath = os.path.join(output_dir, fpath)
            self._ensure_dir(lpath)
            try:
                data = self.GetFile(path)
            except:
                self.log.exception('Failed to extract %s from CHM, ignoring'%path)
                continue
            if lpath.find(';') != -1:
                # fix file names with ";<junk>" at the end, see _reformat()
                lpath = lpath.split(';')[0]
            try:
                with open(lpath, 'wb') as f:
                    f.write(data)
                try:
                    if 'html' in guess_mimetype(path)[0]:
                        html_files.add(lpath)
                except:
                    pass
            except:
                if iswindows and len(lpath) > 250:
                    self.log.warn('%r filename too long, skipping'%path)
                    continue
                raise

        if debug_dump:
            import shutil
            shutil.copytree(output_dir, os.path.join(debug_dump, 'debug_dump'))
        for lpath in html_files:
            with lopen(lpath, 'r+b') as f:
                data = f.read()
                data = self._reformat(data, lpath)
                if isinstance(data, str):
                    data = data.encode('utf-8')
                f.seek(0)
                f.truncate()
                f.write(data)

        self._extracted = True
        files = [y for y in os.listdir(output_dir) if
                os.path.isfile(os.path.join(output_dir, y))]
        if self.hhc_path not in files:
            for f in files:
                if f.lower() == self.hhc_path.lower():
                    self.hhc_path = f
                    break
        if self.hhc_path not in files and files:
            for f in files:
                if f.partition('.')[-1].lower() in {'html', 'htm', 'xhtm',
                        'xhtml'}:
                    self.hhc_path = f
                    break

        if self.hhc_path == '.hhc' and self.hhc_path not in files:
            from calibre import walk
            for x in walk(output_dir):
                if os.path.basename(x).lower() in ('index.htm', 'index.html',
                        'contents.htm', 'contents.html'):
                    self.hhc_path = os.path.relpath(x, output_dir)
                    break

        if self.hhc_path not in files and files:
            self.hhc_path = files[0]

    def _reformat(self, data, htmlpath):
        if self.input_encoding:
            data = data.decode(self.input_encoding)
        try:
            data = xml_to_unicode(data, strip_encoding_pats=True)[0]
            soup = BeautifulSoup(data)
        except ValueError:
            # hit some strange encoding problems...
            self.log.exception("Unable to parse html for cleaning, leaving it")
            return data
        # nuke javascript...
        [s.extract() for s in soup('script')]
        # See if everything is inside a <head> tag
        # https://bugs.launchpad.net/bugs/1273512
        body = soup.find('body')
        if body is not None and body.parent.name == 'head':
            html = soup.find('html')
            html.insert(len(html), body)

        # remove forward and back nav bars from the top/bottom of each page
        # cos they really fuck with the flow of things and generally waste space
        # since we can't use [a,b] syntax to select arbitrary items from a list
        # we'll have to do this manually...
        # only remove the tables, if they have an image with an alt attribute
        # containing prev, next or team
        t = soup('table')
        if t:
            if (t[0].previousSibling is None or t[0].previousSibling.previousSibling is None):
                try:
                    alt = t[0].img['alt'].lower()
                    if alt.find('prev') != -1 or alt.find('next') != -1 or alt.find('team') != -1:
                        t[0].extract()
                except:
                    pass
            if (t[-1].nextSibling is None or t[-1].nextSibling.nextSibling is None):
                try:
                    alt = t[-1].img['alt'].lower()
                    if alt.find('prev') != -1 or alt.find('next') != -1 or alt.find('team') != -1:
                        t[-1].extract()
                except:
                    pass
        # for some very odd reason each page's content appears to be in a table
        # too. and this table has sub-tables for random asides... grr.

        # remove br at top of page if present after nav bars removed
        br = soup('br')
        if br:
            if check_all_prev_empty(br[0].previousSibling):
                br[0].extract()

        # some images seem to be broken in some chm's :/
        base = os.path.dirname(htmlpath)
        for img in soup('img', src=True):
            src = img['src']
            ipath = os.path.join(base, *src.split('/'))
            if os.path.exists(ipath):
                continue
            src = src.split(';')[0]
            if not src:
                continue
            ipath = os.path.join(base, *src.split('/'))
            if not os.path.exists(ipath):
                while src.startswith('../'):
                    src = src[3:]
            img['src'] = src
        try:
            # if there is only a single table with a single element
            # in the body, replace it by the contents of this single element
            tables = soup.body.findAll('table', recursive=False)
            if tables and len(tables) == 1:
                trs = tables[0].findAll('tr', recursive=False)
                if trs and len(trs) == 1:
                    tds = trs[0].findAll('td', recursive=False)
                    if tds and len(tds) == 1:
                        tdContents = tds[0].contents
                        tableIdx = soup.body.contents.index(tables[0])
                        tables[0].extract()
                        while tdContents:
                            soup.body.insert(tableIdx, tdContents.pop())
        except:
            pass
        # do not prettify, it would reformat the <pre> tags!
        try:
            ans = soup.decode_contents()
            self.re_encoded_files.add(os.path.abspath(htmlpath))
            return ans
        except RuntimeError:
            return data

    def Contents(self):
        if self._contents is not None:
            return self._contents
        paths = []

        def get_paths(chm, ui, ctx):
            # these are supposed to be UTF-8 in CHM as best as I can determine
            # see https://tika.apache.org/1.11/api/org/apache/tika/parser/chm/accessor/ChmPmgiHeader.html
            path = as_unicode(ui.path, 'utf-8')
            # skip directories
            # note this path refers to the internal CHM structure
            if path[-1] != '/':
                # and make paths relative
                paths.append(path.lstrip('/'))
        chmlib.chm_enumerate(self.file, chmlib.CHM_ENUMERATE_NORMAL, get_paths, None)
        self._contents = paths
        return self._contents

    def _ensure_dir(self, path):
        dir = os.path.dirname(path)
        if not os.path.isdir(dir):
            os.makedirs(dir)

    def extract_content(self, output_dir=os.getcwd(), debug_dump=False):
        self.ExtractFiles(output_dir=output_dir, debug_dump=debug_dump)
