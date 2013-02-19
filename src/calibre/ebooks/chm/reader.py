from __future__ import with_statement
''' CHM File decoding support '''
__license__ = 'GPL v3'
__copyright__  = '2008, Kovid Goyal <kovid at kovidgoyal.net>,' \
                 ' and Alex Bramley <a.bramley at gmail.com>.'

import os, re, codecs

from calibre import guess_type as guess_mimetype
from calibre.ebooks.BeautifulSoup import BeautifulSoup, NavigableString
from calibre.constants import iswindows, filesystem_encoding
from calibre.utils.chm.chm import CHMFile
from calibre.utils.chm.chmlib import (
  CHM_RESOLVE_SUCCESS, CHM_ENUMERATE_NORMAL,
  chm_enumerate,
)

from calibre.ebooks.metadata.toc import TOC
from calibre.ebooks.chardet import xml_to_unicode


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

def check_empty(s, rex = re.compile(r'\S')):
    return rex.search(s) is None


class CHMError(Exception):
    pass

class CHMReader(CHMFile):
    def __init__(self, input, log, input_encoding=None):
        CHMFile.__init__(self)
        if isinstance(input, unicode):
            input = input.encode(filesystem_encoding)
        if not self.LoadCHM(input):
            raise CHMError("Unable to open CHM file '%s'"%(input,))
        self.log = log
        self.input_encoding = input_encoding
        self._sourcechm = input
        self._contents = None
        self._playorder = 0
        self._metadata = False
        self._extracted = False

        # location of '.hhc' file, which is the CHM TOC.
        if self.topics is None:
            self.root, ext = os.path.splitext(self.home.lstrip('/'))
            self.hhc_path = self.root + ".hhc"
        else:
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

    def ExtractFiles(self, output_dir=os.getcwdu(), debug_dump=False):
        html_files = set([])
        try:
            x = self.get_encoding()
            codecs.lookup(x)
            enc = x
        except:
            enc = 'cp1252'
        for path in self.Contents():
            fpath = path
            if not isinstance(path, unicode):
                fpath = path.decode(enc)
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
            with open(lpath, 'r+b') as f:
                data = f.read()
                data = self._reformat(data, lpath)
                if isinstance(data, unicode):
                    data = data.encode('utf-8')
                f.seek(0)
                f.truncate()
                f.write(data)

        self._extracted = True
        files = [x for x in os.listdir(output_dir) if
                os.path.isfile(os.path.join(output_dir, x))]
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
        # remove forward and back nav bars from the top/bottom of each page
        # cos they really fuck with the flow of things and generally waste space
        # since we can't use [a,b] syntax to select arbitrary items from a list
        # we'll have to do this manually...
        # only remove the tables, if they have an image with an alt attribute
        # containing prev, next or team
        t = soup('table')
        if t:
            if (t[0].previousSibling is None
              or t[0].previousSibling.previousSibling is None):
                try:
                    alt = t[0].img['alt'].lower()
                    if alt.find('prev') != -1 or alt.find('next') != -1 or alt.find('team') != -1:
                        t[0].extract()
                except:
                    pass
            if (t[-1].nextSibling is None
              or t[-1].nextSibling.nextSibling is None):
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
            if not src: continue
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
            return str(soup)
        except RuntimeError:
            return data

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

    def extract_content(self, output_dir=os.getcwdu(), debug_dump=False):
        self.ExtractFiles(output_dir=output_dir, debug_dump=debug_dump)



