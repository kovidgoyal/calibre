#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from lxml import etree

from calibre import prepare_string_for_xml as xml
from calibre.ebooks.oeb.polish.check.base import BaseError, WARN
from calibre.ebooks.oeb.polish.toc import find_existing_nav_toc, parse_nav
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.ebooks.oeb.base import OPF, OPF2_NS, DC, DC11_NS, XHTML_MIME


class MissingSection(BaseError):

    def __init__(self, name, section_name):
        BaseError.__init__(self, _('The <%s> section is missing from the OPF') % section_name, name)
        self.HELP = xml(_(
            'The <%s> section is required in the OPF file. You have to create one.') % section_name)


class IncorrectIdref(BaseError):

    def __init__(self, name, idref, lnum):
        BaseError.__init__(self, _('idref="%s" points to unknown id') % idref, name, lnum)
        self.HELP = xml(_(
            'The idref="%s" points to an id that does not exist in the OPF') % idref)


class IncorrectCover(BaseError):

    def __init__(self, name, lnum, cover):
        BaseError.__init__(self, _('The meta cover tag points to an non-existent item'), name, lnum)
        self.HELP = xml(_(
            'The meta cover tag points to an item with id="%s" which does not exist in the manifest') % cover)


class NookCover(BaseError):

    HELP = _(
            'Some e-book readers such as the Nook fail to recognize covers if'
            ' the content attribute comes before the name attribute.'
            ' For maximum compatibility move the name attribute before the content attribute.')
    INDIVIDUAL_FIX = _('Move the name attribute before the content attribute')

    def __init__(self, name, lnum):
        BaseError.__init__(self, _('The meta cover tag has content before name'), name, lnum)

    def __call__(self, container):
        for cover in container.opf_xpath('//opf:meta[@name="cover" and @content]'):
            cover.set('content', cover.attrib.pop('content'))
        container.dirty(container.opf_name)
        return True


class IncorrectToc(BaseError):

    def __init__(self, name, lnum, bad_idref=None, bad_mimetype=None):
        if bad_idref is not None:
            msg = _('The item identified as the Table of Contents (%s) does not exist') % bad_idref
            self.HELP = _('There is no item with id="%s" in the manifest.') % bad_idref
        else:
            msg = _('The item identified as the Table of Contents has an incorrect media-type (%s)') % bad_mimetype
            self.HELP = _('The media type for the Table of Contents must be %s') % guess_type('a.ncx')
        BaseError.__init__(self, msg, name, lnum)


class NoHref(BaseError):

    HELP = _('This manifest entry has no href attribute. Either add the href attribute or remove the entry.')
    INDIVIDUAL_FIX = _('Remove this manifest entry')

    def __init__(self, name, item_id, lnum):
        BaseError.__init__(self, _('Item in manifest has no href attribute'), name, lnum)
        self.item_id = item_id

    def __call__(self, container):
        changed = False
        for item in container.opf_xpath('/opf:package/opf:manifest/opf:item'):
            if item.get('id', None) == self.item_id:
                changed = True
                container.remove_from_xml(item)
                container.dirty(container.opf_name)
        return changed


class MissingNCXRef(BaseError):

    HELP = _('The <spine> tag has no reference to the NCX table of contents file.'
             ' Without this reference, the table of contents will not work in most'
             ' readers. The reference should look like <spine toc="id of manifest item for the ncx file">.')
    INDIVIDUAL_FIX = _('Add the reference to the NCX file')

    def __init__(self, name, lnum, ncx_id):
        BaseError.__init__(self, _('Missing reference to the NCX Table of Contents'), name, lnum)
        self.ncx_id = ncx_id

    def __call__(self, container):
        changed = False
        for item in container.opf_xpath('/opf:package/opf:spine'):
            if item.get('toc') is None:
                item.set('toc', self.ncx_id)
                changed = True
                container.dirty(container.opf_name)
        return changed


class MissingNav(BaseError):

    HELP = _('This book has no Navigation document. According to the EPUB 3 specification, a navigation document'
             ' is required. The Navigation document contains the Table of Contents. Use the Table of Contents'
             ' tool to add a Table of Contents to this book.')

    def __init__(self, name, lnum):
        BaseError.__init__(self, _('Missing navigation document'), name, lnum)


class EmptyNav(BaseError):

    HELP = _('The nav document for this book contains no table of contents, or an empty table of contents.'
             ' Use the Table of Contents tool to add a Table of Contents to this book.')
    LEVEL = WARN

    def __init__(self, name, lnum):
        BaseError.__init__(self, _('Missing ToC in navigation document'), name, lnum)


class MissingHref(BaseError):

    HELP = _('A file listed in the manifest is missing, you should either remove'
             ' it from the manifest or add the missing file to the book.')

    def __init__(self, name, href, lnum):
        BaseError.__init__(self, _('Item (%s) in manifest is missing') % href, name, lnum)
        self.bad_href = href
        self.INDIVIDUAL_FIX = _('Remove the entry for %s from the manifest') % href

    def __call__(self, container):
        [container.remove_from_xml(elem) for elem in container.opf_xpath('/opf:package/opf:manifest/opf:item[@href]')
         if elem.get('href') == self.bad_href]
        container.dirty(container.opf_name)
        return True


class NonLinearItems(BaseError):

    level = WARN
    has_multiple_locations = True

    HELP = xml(_('There are items marked as non-linear in the <spine>.'
                 ' These will be displayed in random order by different e-book readers.'
                 ' Some will ignore the non-linear attribute, some will display'
                 ' them at the end or the beginning of the book and some will'
                 ' fail to display them at all. Instead of using non-linear items'
                 ' simply place the items in the order you want them to be displayed.'))

    INDIVIDUAL_FIX = _('Mark all non-linear items as linear')

    def __init__(self, name, locs):
        BaseError.__init__(self, _('Non-linear items in the spine'), name)
        self.all_locations = [(name, x, None) for x in locs]

    def __call__(self, container):
        [elem.attrib.pop('linear') for elem in container.opf_xpath('//opf:spine/opf:itemref[@linear]')]
        container.dirty(container.opf_name)
        return True


class DuplicateHref(BaseError):

    has_multiple_locations = True

    INDIVIDUAL_FIX = _(
        'Remove all but the first duplicate item')

    def __init__(self, name, eid, locs, for_spine=False):
        loc = 'spine' if for_spine else 'manifest'
        BaseError.__init__(self, _('Duplicate item in {0}: {1}').format(loc, eid), name)
        self.HELP = _(
            'The item {0} is present more than once in the {2} in {1}. This is'
            ' not allowed.').format(eid, name, loc)
        self.all_locations = [(name, lnum, None) for lnum in sorted(locs)]
        self.duplicate_href = eid
        self.xpath = '/opf:package/opf:' + ('spine/opf:itemref[@idref]' if for_spine else 'manifest/opf:item[@href]')
        self.attr = 'idref' if for_spine else 'href'

    def __call__(self, container):
        items = [e for e in container.opf_xpath(self.xpath) if e.get(self.attr) == self.duplicate_href]
        [container.remove_from_xml(e) for e in items[1:]]
        container.dirty(self.name)
        return True


class MultipleCovers(BaseError):

    has_multiple_locations = True
    HELP = xml(_(
        'There is more than one <meta name="cover"> tag defined. There should be only one.'))
    INDIVIDUAL_FIX = _('Remove all but the first meta cover tag')

    def __init__(self, name, locs):
        BaseError.__init__(self, _('There is more than one cover defined'), name)
        self.all_locations = [(name, lnum, None) for lnum in sorted(locs)]

    def __call__(self, container):
        items = [e for e in container.opf_xpath('/opf:package/opf:metadata/opf:meta[@name="cover"]')]
        [container.remove_from_xml(e) for e in items[1:]]
        container.dirty(self.name)
        return True


class NoUID(BaseError):

    HELP = xml(_(
        'The OPF must have a unique identifier, i.e. a <dc:identifier> element whose id is referenced'
        ' by the <package> element'))
    INDIVIDUAL_FIX = _('Auto-generate a unique identifier')

    def __init__(self, name):
        BaseError.__init__(self, _('The OPF has no unique identifier'), name)

    def __call__(self, container):
        from calibre.ebooks.oeb.base import uuid_id
        opf = container.opf
        uid = uuid_id()
        opf.set('unique-identifier', uid)
        m = container.opf_xpath('/opf:package/opf:metadata')
        if not m:
            m = [container.opf.makeelement(OPF('metadata'), nsmap={'dc':DC11_NS})]
            container.insert_into_xml(container.opf, m[0], 0)
        m = m[0]
        dc = m.makeelement(DC('identifier'), id=uid, nsmap={'opf':OPF2_NS})
        dc.set(OPF('scheme'), 'uuid')
        dc.text = uid
        container.insert_into_xml(m, dc)
        container.dirty(container.opf_name)
        return True


class EmptyIdentifier(BaseError):

    HELP = xml(_('The <dc:identifier> element must not be empty.'))

    def __init__(self, name, lnum):
        BaseError.__init__(self, _('Empty identifier element'), name, lnum)


class BadSpineMime(BaseError):

    def __init__(self, name, iid, mt, lnum, opf_name):
        BaseError.__init__(self, _('Incorrect media-type for spine item'), opf_name, lnum)
        self.HELP = _(
            'The item {0} present in the spine has the media-type {1}. '
            ' Most e-book software cannot handle non-HTML spine items. '
            ' If the item is actually HTML, you should change its media-type to {2}.'
            ' If it is not-HTML you should consider replacing it with an HTML item, as it'
            ' is unlikely to work in most readers.').format(name, mt, XHTML_MIME)
        if iid is not None:
            self.INDIVIDUAL_FIX = _('Change the media-type to %s') % XHTML_MIME
            self.iid = iid

    def __call__(self, container):
        container.opf_xpath('/opf:package/opf:manifest/opf:item[@id=%r]' % self.iid)[0].set(
            'media-type', XHTML_MIME)
        container.dirty(container.opf_name)
        container.refresh_mime_map()
        return True


def check_opf(container):
    errors = []
    opf_version = container.opf_version_parsed

    if container.opf.tag != OPF('package'):
        err = BaseError(_('The OPF does not have the correct root element'), container.opf_name, container.opf.sourceline)
        err.HELP = xml(_(
            'The opf must have the root element <package> in namespace {0}, like this: <package xmlns="{0}">')).format(OPF2_NS)
        errors.append(err)

    elif container.opf.get('version') is None and container.book_type == 'epub':
        err = BaseError(_('The OPF does not have a version'), container.opf_name, container.opf.sourceline)
        err.HELP = xml(_(
            'The <package> tag in the OPF must have a version attribute. This is usually version="2.0" for EPUB2 and AZW3 and version="3.0" for EPUB3'))
        errors.append(err)

    for tag in ('metadata', 'manifest', 'spine'):
        if not container.opf_xpath('/opf:package/opf:' + tag):
            errors.append(MissingSection(container.opf_name, tag))

    all_ids = set(container.opf_xpath('//*/@id'))
    for elem in container.opf_xpath('//*[@idref]'):
        if elem.get('idref') not in all_ids:
            errors.append(IncorrectIdref(container.opf_name, elem.get('idref'), elem.sourceline))

    nl_items = [elem.sourceline for elem in container.opf_xpath('//opf:spine/opf:itemref[@linear="no"]')]
    if nl_items:
        errors.append(NonLinearItems(container.opf_name, nl_items))

    seen, dups = {}, {}
    for item in container.opf_xpath('/opf:package/opf:manifest/opf:item'):
        href = item.get('href', None)
        if href is None:
            errors.append(NoHref(container.opf_name, item.get('id', None), item.sourceline))
        else:
            hname = container.href_to_name(href, container.opf_name)
            if not hname or not container.exists(hname):
                errors.append(MissingHref(container.opf_name, href, item.sourceline))
            if href in seen:
                if href not in dups:
                    dups[href] = [seen[href]]
                dups[href].append(item.sourceline)
            else:
                seen[href] = item.sourceline
    errors.extend(DuplicateHref(container.opf_name, eid, locs) for eid, locs in dups.iteritems())

    seen, dups = {}, {}
    for item in container.opf_xpath('/opf:package/opf:spine/opf:itemref[@idref]'):
        ref = item.get('idref')
        if ref in seen:
            if ref not in dups:
                dups[ref] = [seen[ref]]
            dups[ref].append(item.sourceline)
        else:
            seen[ref] = item.sourceline
    errors.extend(DuplicateHref(container.opf_name, eid, locs, for_spine=True) for eid, locs in dups.iteritems())

    spine = container.opf_xpath('/opf:package/opf:spine[@toc]')
    if spine:
        spine = spine[0]
        mitems = [x for x in container.opf_xpath('/opf:package/opf:manifest/opf:item[@id]') if x.get('id') == spine.get('toc')]
        if mitems:
            mitem = mitems[0]
            if mitem.get('media-type', '') != guess_type('a.ncx'):
                errors.append(IncorrectToc(container.opf_name, mitem.sourceline, bad_mimetype=mitem.get('media-type')))
        else:
            errors.append(IncorrectToc(container.opf_name, spine.sourceline, bad_idref=spine.get('toc')))
    else:
        spine = container.opf_xpath('/opf:package/opf:spine')
        if spine:
            spine = spine[0]
            ncx = container.manifest_type_map.get(guess_type('a.ncx'))
            if ncx:
                ncx_name = ncx[0]
                rmap = {v:k for k, v in container.manifest_id_map.iteritems()}
                ncx_id = rmap.get(ncx_name)
                if ncx_id:
                    errors.append(MissingNCXRef(container.opf_name, spine.sourceline, ncx_id))

    if opf_version.major > 2:
        existing_nav = find_existing_nav_toc(container)
        if existing_nav is None:
            errors.append(MissingNav(container.opf_name, 0))
        else:
            toc = parse_nav(container, existing_nav)
            if len(toc) == 0:
                errors.append(EmptyNav(existing_nav, 0))

    covers = container.opf_xpath('/opf:package/opf:metadata/opf:meta[@name="cover"]')
    if len(covers) > 0:
        if len(covers) > 1:
            errors.append(MultipleCovers(container.opf_name, [c.sourceline for c in covers]))
        manifest_ids = set(container.opf_xpath('/opf:package/opf:manifest/opf:item/@id'))
        for cover in covers:
            if cover.get('content', None) not in manifest_ids:
                errors.append(IncorrectCover(container.opf_name, cover.sourceline, cover.get('content', '')))
            raw = etree.tostring(cover)
            try:
                n, c = raw.index('name="'), raw.index('content="')
            except ValueError:
                n = c = -1
            if n > -1 and c > -1 and n > c:
                errors.append(NookCover(container.opf_name, cover.sourceline))

    uid = container.opf.get('unique-identifier', None)
    if uid is None or not container.opf_xpath('/opf:package/opf:metadata/dc:identifier[@id=%r]' % uid):
        errors.append(NoUID(container.opf_name))
    for elem in container.opf_xpath('/opf:package/opf:metadata/dc:identifier'):
        if not elem.text or not elem.text.strip():
            errors.append(EmptyIdentifier(container.opf_name, elem.sourceline))

    for item, name, linear in container.spine_iter:
        mt = container.mime_map[name]
        if mt != XHTML_MIME:
            iid = item.get('idref', None)
            lnum = None
            if iid:
                mitem = container.opf_xpath('/opf:package/opf:manifest/opf:item[@id=%r]' % iid)
                if mitem:
                    lnum = mitem[0].sourceline
                else:
                    iid = None
            errors.append(BadSpineMime(name, iid, mt, lnum, container.opf_name))

    return errors
