#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os, glob, re
from urlparse import urlparse
from urllib import unquote

from calibre import __appname__
from calibre.ebooks.BeautifulSoup import BeautifulStoneSoup, BeautifulSoup
from calibre.ebooks.chardet import xml_to_unicode

class NCXSoup(BeautifulStoneSoup):

    NESTABLE_TAGS = {'navpoint':[]}

    def __init__(self, raw):
        BeautifulStoneSoup.__init__(self, raw,
                                  convertEntities=BeautifulSoup.HTML_ENTITIES,
                                  selfClosingTags=['meta', 'content'])

class TOC(list):

    def __init__(self, href=None, fragment=None, text=None, parent=None, play_order=0,
                 base_path=os.getcwd(), type='unknown', author=None,
                 description=None):
        self.href = href
        self.fragment = fragment
        if not self.fragment:
            self.fragment = None
        self.text = text
        self.parent = parent
        self.base_path = base_path
        self.play_order = play_order
        self.type = type
        self.author = author
        self.description = description

    def __str__(self):
        lines = ['TOC: %s#%s'%(self.href, self.fragment)]
        for child in self:
            c = str(child).splitlines()
            for l in c:
                lines.append('\t'+l)
        return '\n'.join(lines)

    def count(self, type):
        return len([i for i in self.flat() if i.type == type])

    def purge(self, types, max=0):
        remove = []
        for entry in self.flat():
            if entry.type in types:
                remove.append(entry)
        remove = remove[max:]
        for entry in remove:
            if entry.parent is None:
                continue
            entry.parent.remove(entry)
        return remove

    def remove(self, entry):
        list.remove(self, entry)
        entry.parent = None

    def add_item(self, href, fragment, text, play_order=None, type='unknown',
            author=None, description=None):
        if play_order is None:
            play_order = (self[-1].play_order if len(self) else self.play_order) + 1
        self.append(TOC(href=href, fragment=fragment, text=text, parent=self,
                        base_path=self.base_path, play_order=play_order,
                        type=type, author=author, description=description))
        return self[-1]

    def top_level_items(self):
        for item in self:
            if item.text is not None:
                yield item

    def depth(self):
        depth = 1
        for obj in self:
            c = obj.depth()
            if c > depth - 1:
                depth = c + 1
        return depth

    def flat(self):
        'Depth first iteration over the tree rooted at self'
        yield self
        for obj in self:
            for i in obj.flat():
                yield i

    @dynamic_property
    def abspath(self):
        doc='Return the file this toc entry points to as a absolute path to a file on the system.'
        def fget(self):
            if self.href is None:
                return None
            path = self.href.replace('/', os.sep)
            if not os.path.isabs(path):
                path = os.path.join(self.base_path, path)
            return path

        return property(fget=fget, doc=doc)

    def read_from_opf(self, opfreader):
        toc = opfreader.soup.find('spine', toc=True)
        if toc is not None:
            toc = toc['toc']
        if toc is None:
            try:
                toc = opfreader.soup.find('guide').find('reference', attrs={'type':'toc'})['href']
            except:
                for item in opfreader.manifest:
                    if 'toc' in item.href().lower():
                        toc = item.href()
                        break

        if toc is not None:
            if toc.lower() not in ('ncx', 'ncxtoc'):
                toc = urlparse(unquote(toc))[2]
                toc = toc.replace('/', os.sep)
                if not os.path.isabs(toc):
                    toc = os.path.join(self.base_path, toc)
                try:
                    if not os.path.exists(toc):
                        bn  = os.path.basename(toc)
                        bn  = bn.replace('_top.htm', '_toc.htm') # Bug in BAEN OPF files
                        toc = os.path.join(os.path.dirname(toc), bn)

                    self.read_html_toc(toc)
                except:
                    print 'WARNING: Could not read Table of Contents. Continuing anyway.'
            else:
                path = opfreader.manifest.item(toc.lower())
                path = getattr(path, 'path', path)
                if path and os.access(path, os.R_OK):
                    try:
                        self.read_ncx_toc(path)
                    except Exception, err:
                        print 'WARNING: Invalid NCX file:', err
                    return
                cwd = os.path.abspath(self.base_path)
                m = glob.glob(os.path.join(cwd, '*.ncx'))
                if m:
                    toc = m[0]
                    self.read_ncx_toc(toc)

    def read_ncx_toc(self, toc):
        self.base_path = os.path.dirname(toc)
        raw  = xml_to_unicode(open(toc, 'rb').read(), assume_utf8=True)[0]
        soup = NCXSoup(raw)

        def process_navpoint(np, dest):
            play_order = np.get('playOrder', None)
            if play_order is None:
                play_order = int(np.get('playorder', 1))
            href = fragment = text = None
            nl = np.find(re.compile('navlabel'))
            if nl is not None:
                text = u''
                for txt in nl.findAll(re.compile('text')):
                    text += u''.join([unicode(s) for s in txt.findAll(text=True)])
                content = np.find(re.compile('content'))
                if content is None or not content.has_key('src') or not txt:
                    return

                purl = urlparse(unquote(content['src']))
                href, fragment = purl[2], purl[5]
            nd = dest.add_item(href, fragment, text)
            nd.play_order = play_order

            for c in np:
                if 'navpoint' in getattr(c, 'name', ''):
                    process_navpoint(c, nd)

        nm = soup.find(re.compile('navmap'))
        if nm is None:
            raise ValueError('NCX files must have a <navmap> element.')

        for elem in nm:
            if 'navpoint' in getattr(elem, 'name', ''):
                process_navpoint(elem, self)


    def read_html_toc(self, toc):
        self.base_path = os.path.dirname(toc)
        soup = BeautifulSoup(open(toc, 'rb').read(), convertEntities=BeautifulSoup.HTML_ENTITIES)
        for a in soup.findAll('a'):
            if not a.has_key('href'):
                continue
            purl = urlparse(unquote(a['href']))
            href, fragment = purl[2], purl[5]
            if not fragment:
                fragment = None
            else:
                fragment = fragment.strip()
            href = href.strip()

            txt = ''.join([unicode(s).strip() for s in a.findAll(text=True)])
            add = True
            for i in self.flat():
                if i.href == href and i.fragment == fragment:
                    add = False
                    break
            if add:
                self.add_item(href, fragment, txt)

    def render(self, stream, uid):
        from calibre.utils.genshi.template import MarkupTemplate
        ncx_template = open(P('templates/ncx.xml'), 'rb').read()
        doctype = ('ncx', "-//NISO//DTD ncx 2005-1//EN", "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd")
        template = MarkupTemplate(ncx_template)
        raw = template.generate(uid=uid, toc=self, __appname__=__appname__)
        raw = raw.render(doctype=doctype)
        stream.write(raw)
