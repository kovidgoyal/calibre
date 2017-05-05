#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os
from collections import defaultdict
from urlparse import urlparse
from future_builtins import map
from threading import Thread
from Queue import Queue, Empty

from calibre import browser
from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES, urlunquote
from calibre.ebooks.oeb.polish.container import OEB_FONTS
from calibre.ebooks.oeb.polish.replace import remove_links_to
from calibre.ebooks.oeb.polish.cover import get_raster_cover_name
from calibre.ebooks.oeb.polish.utils import guess_type, actual_case_for_name, corrected_case_for_name
from calibre.ebooks.oeb.polish.check.base import BaseError, WARN, INFO


class BadLink(BaseError):

    HELP = _('The resource pointed to by this link does not exist. You should'
             ' either fix, or remove the link.')
    level = WARN


class InvalidCharInLink(BadLink):

    HELP = _('Windows computers do not allow the : character in filenames. For maximum'
             ' compatibility it is best to not use these in filenames/links to files.')


class CaseMismatch(BadLink):

    def __init__(self, href, corrected_name, name, lnum, col):
        BadLink.__init__(self, _('The linked to resource {0} does not exist').format(href), name, line=lnum, col=col)
        self.HELP = _('The case of the link {0} and the case of the actual file it points to {1}'
                      ' do not agree. You should change either the case of the link or rename the file.').format(
                          href, corrected_name)
        self.INDIVIDUAL_FIX = _('Change the case of the link to match the actual file')
        self.corrected_name = corrected_name
        self.href = href

    def __call__(self, container):
        frag = urlparse(self.href).fragment
        nhref = container.name_to_href(self.corrected_name, self.name)
        if frag:
            nhref += '#' + frag
        orig_href = self.href

        class LinkReplacer(object):
            replaced = False

            def __call__(self, url):
                if url != orig_href:
                    return url
                self.replaced = True
                return nhref
        replacer = LinkReplacer()
        container.replace_links(self.name, replacer)
        return replacer.replaced


class BadDestinationType(BaseError):

    level = WARN

    def __init__(self, link_source, link_dest, link_elem):
        BaseError.__init__(self, _('Link points to a file that is not a text document'), link_source, line=link_elem.sourceline)
        self.HELP = _('The link "{0}" points to a file <i>{1}</i> that is not a text (HTML) document.'
                      ' Many e-book readers will be unable to follow such a link. You should'
                      ' either remove the link or change it to point to a text document.'
                      ' For example, if it points to an image, you can create small wrapper'
                      ' document that contains the image and change the link to point to that.').format(
                          link_elem.get('href'), link_dest)
        self.bad_href = link_elem.get('href')


class BadDestinationFragment(BaseError):

    level = WARN

    def __init__(self, link_source, link_dest, link_elem, fragment):
        BaseError.__init__(self, _('Link points to a location not present in the target file'), link_source, line=link_elem.sourceline)
        self.bad_href = link_elem.get('href')
        self.HELP = _('The link "{0}" points to a location <i>{1}</i> in the file {2} that does not exist.'
                      ' You should either remove the location so that the link points to the top of the file,'
                      ' or change the link to point to the correct location.').format(
                          self.bad_href, fragment, link_dest)


class FileLink(BadLink):

    HELP = _('This link uses the file:// URL scheme. This does not work with many e-book readers.'
             ' Remove the file:// prefix and make sure the link points to a file inside the book.')


class LocalLink(BadLink):

    HELP = _('This link points to a file outside the book. It will not work if the'
             ' book is read on any computer other than the one it was created on.'
             ' Either fix or remove the link.')


class EmptyLink(BadLink):

    HELP = _('This link is empty. This is almost always a mistake. Either fill in the link destination or remove the link tag.')


class UnreferencedResource(BadLink):

    HELP = _('This file is included in the book but not referred to by any document in the spine.'
             ' This means that the file will not be viewable on most e-book readers. You should '
             ' probably remove this file from the book or add a link to it somewhere.')

    def __init__(self, name):
        BadLink.__init__(self, _(
            'The file %s is not referenced') % name, name)


class UnreferencedDoc(UnreferencedResource):

    HELP = _('This file is not in the book spine. All content documents must be in the spine.'
             ' You should probably add it to the spine.')
    INDIVIDUAL_FIX = _('Append this file to the spine')

    def __call__(self, container):
        from calibre.ebooks.oeb.base import OPF
        rmap = {v:k for k, v in container.manifest_id_map.iteritems()}
        if self.name in rmap:
            manifest_id = rmap[self.name]
        else:
            manifest_id = container.add_name_to_manifest(self.name)
        spine = container.opf_xpath('//opf:spine')[0]
        si = spine.makeelement(OPF('itemref'), idref=manifest_id)
        container.insert_into_xml(spine, si)
        container.dirty(container.opf_name)
        return True


class Unmanifested(BadLink):

    HELP = _('This file is not listed in the book manifest. While not strictly necessary'
             ' it is good practice to list all files in the manifest. Either list this'
             ' file in the manifest or remove it from the book if it is an unnecessary file.')

    def __init__(self, name, unreferenced=None):
        BadLink.__init__(self, _(
            'The file %s is not listed in the manifest') % name, name)
        self.file_action = None
        if unreferenced is not None:
            self.INDIVIDUAL_FIX = _(
                'Remove %s from the book') % name if unreferenced else _(
                    'Add %s to the manifest') % name
            self.file_action = 'remove' if unreferenced else 'add'

    def __call__(self, container):
        if self.file_action == 'remove':
            container.remove_item(self.name)
        else:
            rmap = {v:k for k, v in container.manifest_id_map.iteritems()}
            if self.name not in rmap:
                container.add_name_to_manifest(self.name)
        return True


class DanglingLink(BadLink):

    def __init__(self, text, target_name, name, lnum, col):
        BadLink.__init__(self, text, name, lnum, col)
        self.INDIVIDUAL_FIX = _('Remove all references to %s from the HTML and CSS in the book') % target_name
        self.target_name = target_name

    def __call__(self, container):
        return bool(remove_links_to(container, lambda name, *a: name == self.target_name))


class Bookmarks(BadLink):

    HELP = _(
        'This file stores the bookmarks and last opened information from'
        ' the calibre E-book viewer. You can remove it if you do not'
        ' need that information, or don\'t want to share it with'
        ' other people you send this book to.')
    INDIVIDUAL_FIX = _('Remove this file')
    level = INFO

    def __init__(self, name):
        BadLink.__init__(self, _(
            'The bookmarks file used by the calibre E-book viewer is present'), name)

    def __call__(self, container):
        container.remove_item(self.name)
        return True


class MimetypeMismatch(BaseError):

    level = WARN

    def __init__(self, container, name, opf_mt, ext_mt):
        self.opf_mt, self.ext_mt = opf_mt, ext_mt
        self.file_name = name
        BaseError.__init__(self, _('The file %s has a mimetype that does not match its extension') % name, container.opf_name)
        ext = name.rpartition('.')[-1]
        self.HELP = _('The file {0} has its mimetype specified as {1} in the OPF file.'
                      ' The recommended mimetype for files with the extension "{2}" is {3}.'
                      ' You should change either the file extension or the mimetype in the OPF.').format(
                          name, opf_mt, ext, ext_mt)
        if opf_mt in OEB_DOCS and name in {n for n, l in container.spine_names}:
            self.INDIVIDUAL_FIX = _('Change the file extension to .xhtml')
            self.change_ext_to = 'xhtml'
        else:
            self.INDIVIDUAL_FIX = _('Change the mimetype for this file in the OPF to %s') % ext_mt
            self.change_ext_to = None

    def __call__(self, container):
        changed = False
        if self.change_ext_to is not None:
            from calibre.ebooks.oeb.polish.replace import rename_files
            new_name = self.file_name.rpartition('.')[0] + '.' + self.change_ext_to
            c = 0
            while container.has_name(new_name):
                c += 1
                new_name = self.file_name.rpartition('.')[0] + ('%d.' % c) + self.change_ext_to
            rename_files(container, {self.file_name:new_name})
            changed = True
        else:
            for item in container.opf_xpath('//opf:manifest/opf:item[@href and @media-type="%s"]' % self.opf_mt):
                name = container.href_to_name(item.get('href'), container.opf_name)
                if name == self.file_name:
                    changed = True
                    item.set('media-type', self.ext_mt)
                    container.mime_map[name] = self.ext_mt
            if changed:
                container.dirty(container.opf_name)
        return changed


def check_mimetypes(container):
    errors = []
    a = errors.append
    for name, mt in container.mime_map.iteritems():
        gt = container.guess_type(name)
        if mt != gt:
            if mt == 'application/oebps-page-map+xml' and name.lower().endswith('.xml'):
                continue
            a(MimetypeMismatch(container, name, mt, gt))
    return errors


def check_link_destination(container, dest_map, name, href, a, errors):
    if href.startswith('#'):
        tname = name
    else:
        try:
            tname = container.href_to_name(href, name)
        except ValueError:
            tname = None  # Absolute links to files on another drive in windows cause this
    if tname and tname in container.mime_map:
        if container.mime_map[tname] not in OEB_DOCS:
            errors.append(BadDestinationType(name, tname, a))
        else:
            root = container.parsed(tname)
            if hasattr(root, 'xpath'):
                if tname not in dest_map:
                    dest_map[tname] = set(root.xpath('//*/@id|//*/@name'))
                purl = urlparse(href)
                if purl.fragment and purl.fragment not in dest_map[tname]:
                    errors.append(BadDestinationFragment(name, tname, a, purl.fragment))
            else:
                errors.append(BadDestinationType(name, tname, a))


def check_link_destinations(container):
    ' Check destinations of links that point to HTML files '
    errors = []
    dest_map = {}
    opf_type = guess_type('a.opf')
    ncx_type = guess_type('a.ncx')
    for name, mt in container.mime_map.iteritems():
        if mt in OEB_DOCS:
            for a in container.parsed(name).xpath('//*[local-name()="a" and @href]'):
                href = a.get('href')
                check_link_destination(container, dest_map, name, href, a, errors)
        elif mt == opf_type:
            for a in container.opf_xpath('//opf:reference[@href]'):
                if container.book_type == 'azw3' and a.get('type') in {'cover', 'other.ms-coverimage-standard', 'other.ms-coverimage'}:
                    continue
                href = a.get('href')
                check_link_destination(container, dest_map, name, href, a, errors)
        elif mt == ncx_type:
            for a in container.parsed(name).xpath('//*[local-name() = "content" and @src]'):
                href = a.get('src')
                check_link_destination(container, dest_map, name, href, a, errors)

    return errors


def check_links(container):
    links_map = defaultdict(set)
    xml_types = {guess_type('a.opf'), guess_type('a.ncx')}
    errors = []
    a = errors.append

    def fl(x):
        x = repr(x)
        if x.startswith('u'):
            x = x[1:]
        return x

    for name, mt in container.mime_map.iteritems():
        if mt in OEB_DOCS or mt in OEB_STYLES or mt in xml_types:
            for href, lnum, col in container.iterlinks(name):
                if not href:
                    a(EmptyLink(_('The link is empty'), name, lnum, col))
                try:
                    tname = container.href_to_name(href, name)
                except ValueError:
                    tname = None  # Absolute paths to files on another drive in windows cause this
                if tname is not None:
                    if container.exists(tname):
                        if tname in container.mime_map:
                            links_map[name].add(tname)
                        else:
                            # Filesystem says the file exists, but it is not in
                            # the mime_map, so either there is a case mismatch
                            # or the link is a directory
                            apath = container.name_to_abspath(tname)
                            if os.path.isdir(apath):
                                a(BadLink(_('The linked resource %s is a directory') % fl(href), name, lnum, col))
                            else:
                                a(CaseMismatch(href, actual_case_for_name(container, tname), name, lnum, col))
                    else:
                        cname = corrected_case_for_name(container, tname)
                        if cname is not None:
                            a(CaseMismatch(href, cname, name, lnum, col))
                        else:
                            a(DanglingLink(_('The linked resource %s does not exist') % fl(href), tname, name, lnum, col))
                else:
                    purl = urlparse(href)
                    if purl.scheme == 'file':
                        a(FileLink(_('The link %s is a file:// URL') % fl(href), name, lnum, col))
                    elif purl.path and purl.path.startswith('/') and purl.scheme in {'', 'file'}:
                        a(LocalLink(_('The link %s points to a file outside the book') % fl(href), name, lnum, col))
                    elif purl.path and purl.scheme in {'', 'file'} and ':' in urlunquote(purl.path):
                        a(InvalidCharInLink(_('The link %s contains a : character, this will cause errors on windows computers') % fl(href), name, lnum, col))

    spine_docs = {name for name, linear in container.spine_names}
    spine_styles = {tname for name in spine_docs for tname in links_map[name] if container.mime_map.get(tname, None) in OEB_STYLES}
    num = -1
    while len(spine_styles) > num:
        # Handle import rules in stylesheets
        num = len(spine_styles)
        spine_styles |= {tname for name in spine_styles for tname in links_map[name] if container.mime_map.get(tname, None) in OEB_STYLES}
    seen = set(OEB_DOCS) | set(OEB_STYLES)
    spine_resources = {tname for name in spine_docs | spine_styles for tname in links_map[name] if container.mime_map[tname] not in seen}
    unreferenced = set()

    cover_name = container.guide_type_map.get('cover', None)

    for name, mt in container.mime_map.iteritems():
        if mt in OEB_STYLES and name not in spine_styles:
            a(UnreferencedResource(name))
        elif mt in OEB_DOCS and name not in spine_docs:
            a(UnreferencedDoc(name))
        elif (mt in OEB_FONTS or mt.partition('/')[0] in {'image', 'audio', 'video'}) and name not in spine_resources and name != cover_name:
            if mt.partition('/')[0] == 'image' and name == get_raster_cover_name(container):
                continue
            a(UnreferencedResource(name))
        else:
            continue
        unreferenced.add(name)

    manifest_names = set(container.manifest_id_map.itervalues())
    for name in container.mime_map:
        if name not in manifest_names and not container.ok_to_be_unmanifested(name):
            a(Unmanifested(name, unreferenced=name in unreferenced))
        if name == 'META-INF/calibre_bookmarks.txt':
            a(Bookmarks(name))

    return errors


def check_external_links(container, progress_callback=lambda num, total:None):
    progress_callback(0, 0)
    external_links = defaultdict(list)
    for name, mt in container.mime_map.iteritems():
        if mt in OEB_DOCS or mt in OEB_STYLES:
            for href, lnum, col in container.iterlinks(name):
                purl = urlparse(href)
                if purl.scheme in ('http', 'https'):
                    key = href.partition('#')[0]
                    external_links[key].append((name, href, lnum, col))
    if not external_links:
        return []
    items = Queue()
    ans = []
    tuple(map(items.put, external_links.iteritems()))
    progress_callback(0, len(external_links))
    done = []

    def check_links():
        br = browser(honor_time=False, verify_ssl_certificates=False)
        while True:
            try:
                href, locations = items.get_nowait()
            except Empty:
                return
            try:
                br.open(href, timeout=10).close()
            except Exception as e:
                ans.append((locations, e, href))
            finally:
                done.append(None)
                progress_callback(len(done), len(external_links))

    workers = [Thread(name="CheckLinks", target=check_links) for i in xrange(min(10, len(external_links)))]
    for w in workers:
        w.daemon = True
        w.start()

    for w in workers:
        w.join()
    return ans
