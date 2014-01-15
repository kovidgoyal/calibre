#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre import prepare_string_for_xml as xml
from calibre.ebooks.oeb.polish.check.base import BaseError, WARN
from calibre.ebooks.oeb.base import OPF, OPF2_NS

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
                 ' These will be displayed in random order by different ebook readers.'
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

def check_opf(container):
    errors = []

    if container.opf.tag != OPF('package'):
        err = BaseError(_('The OPF does not have the correct root element'), container.opf_name)
        err.HELP = xml(_(
            'The opf must have the root element <package> in namespace {0}, like this: <package xmlns="{0}">')).format(OPF2_NS)
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
    for item in container.opf_xpath('/opf:package/opf:manifest/opf:item[@href]'):
        href = item.get('href')
        if not container.exists(href):
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

    # Check unique identifier, <meta> tag with name before content for
    # cover and content pointing to proper manifest item.
    return errors
