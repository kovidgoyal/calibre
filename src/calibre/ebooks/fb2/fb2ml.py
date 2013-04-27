# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into FB2 markup
'''

from base64 import b64encode
from datetime import datetime
import re
import uuid

from lxml import etree

from calibre import prepare_string_for_xml
from calibre.constants import __appname__, __version__
from calibre.utils.magick import Image
from calibre.utils.localization import lang_as_iso639_1
from calibre.ebooks.oeb.base import urlnormalize

class FB2MLizer(object):
    '''
    Todo: * Include more FB2 specific tags in the conversion.
          * Handle a tags.
    '''

    def __init__(self, log):
        self.log = log
        self.reset_state()

    def reset_state(self):
        # Used to ensure text and tags are always within <p> and </p>
        self.in_p = False
        # Mapping of image names. OEB allows for images to have the same name but be stored
        # in different directories. FB2 images are all in a flat layout so we rename all images
        # into a sequential numbering system to ensure there are no collisions between image names.
        self.image_hrefs = {}
        # Mapping of toc items and their
        self.toc = {}
        # Used to see whether a new <section> needs to be opened
        self.section_level = 0

    def extract_content(self, oeb_book, opts):
        self.log.info('Converting XHTML to FB2 markup...')
        self.oeb_book = oeb_book
        self.opts = opts
        self.reset_state()

        # Used for adding <section>s and <title>s to allow readers
        # to generate toc from the document.
        if self.opts.sectionize == 'toc':
            self.create_flat_toc(self.oeb_book.toc, 1)

        return self.fb2mlize_spine()

    def fb2mlize_spine(self):
        output = [self.fb2_header()]
        output.append(self.get_text())
        output.append(self.fb2mlize_images())
        output.append(self.fb2_footer())
        output = self.clean_text(u''.join(output))

        if self.opts.pretty_print:
            return u'<?xml version="1.0" encoding="UTF-8"?>\n%s' % etree.tostring(etree.fromstring(output), encoding=unicode, pretty_print=True)
        else:
            return u'<?xml version="1.0" encoding="UTF-8"?>' + output

    def clean_text(self, text):
        # Condense empty paragraphs into a line break.
        text = re.sub(r'(?miu)(<p>\s*</p>\s*){3,}', '<empty-line />', text)
        # Remove empty paragraphs.
        text = re.sub(r'(?miu)<p>\s*</p>', '', text)
        # Clean up pargraph endings.
        text = re.sub(r'(?miu)\s*</p>', '</p>', text)
        # Put paragraphs following a paragraph on a separate line.
        text = re.sub(r'(?miu)</p>\s*<p>', '</p>\n\n<p>', text)

        # Remove empty title elements.
        text = re.sub(r'(?miu)<title>\s*</title>', '', text)
        text = re.sub(r'(?miu)\s+</title>', '</title>', text)

        # Remove empty sections.
        text = re.sub(r'(?miu)<section>\s*</section>', '', text)
        # Clean up sections start and ends.
        text = re.sub(r'(?miu)\s*</section>', '\n</section>', text)
        text = re.sub(r'(?miu)</section>\s*', '</section>\n\n', text)
        text = re.sub(r'(?miu)\s*<section>', '\n<section>', text)
        text = re.sub(r'(?miu)<section>\s*', '<section>\n', text)
        # Put sectnions followed by sections on a separate line.
        text = re.sub(r'(?miu)</section>\s*<section>', '</section>\n\n<section>', text)

        if self.opts.insert_blank_line:
            text = re.sub(r'(?miu)</p>', '</p><empty-line />', text)

        return text

    def fb2_header(self):
        from calibre.ebooks.oeb.base import OPF
        metadata = {}
        metadata['title'] = self.oeb_book.metadata.title[0].value
        metadata['appname'] = __appname__
        metadata['version'] = __version__
        metadata['date'] = '%i.%i.%i' % (datetime.now().day, datetime.now().month, datetime.now().year)
        if self.oeb_book.metadata.language:
            lc = lang_as_iso639_1(self.oeb_book.metadata.language[0].value)
            if not lc:
                lc = self.oeb_book.metadata.language[0].value
            metadata['lang'] = lc or 'en'
        else:
            metadata['lang'] = u'en'
        metadata['id'] = None
        metadata['cover'] = self.get_cover()
        metadata['genre'] = self.opts.fb2_genre

        metadata['author'] = u''
        for auth in self.oeb_book.metadata.creator:
            author_first = u''
            author_middle = u''
            author_last = u''
            author_parts = auth.value.split(' ')
            if len(author_parts) == 1:
                author_last = author_parts[0]
            elif len(author_parts) == 2:
                author_first = author_parts[0]
                author_last = author_parts[1]
            else:
                author_first = author_parts[0]
                author_middle = ' '.join(author_parts[1:-1])
                author_last = author_parts[-1]
            metadata['author'] += '<author>'
            metadata['author'] += '<first-name>%s</first-name>' % prepare_string_for_xml(author_first)
            if author_middle:
                metadata['author'] += '<middle-name>%s</middle-name>' % prepare_string_for_xml(author_middle)
            metadata['author'] += '<last-name>%s</last-name>' % prepare_string_for_xml(author_last)
            metadata['author'] += '</author>'
        if not metadata['author']:
            metadata['author'] = u'<author><first-name></first-name><last-name><last-name></author>'

        metadata['sequence'] = u''
        if self.oeb_book.metadata.series:
            index = '1'
            if self.oeb_book.metadata.series_index:
                index = self.oeb_book.metadata.series_index[0]
            metadata['sequence'] = u'<sequence name="%s" number="%s" />' % (prepare_string_for_xml(u'%s' % self.oeb_book.metadata.series[0]), index)

        identifiers = self.oeb_book.metadata['identifier']
        for x in identifiers:
            if x.get(OPF('scheme'), None).lower() == 'uuid' or unicode(x).startswith('urn:uuid:'):
                metadata['id'] = unicode(x).split(':')[-1]
                break
        if metadata['id'] is None:
            self.log.warn('No UUID identifier found')
            metadata['id'] = str(uuid.uuid4())

        for key, value in metadata.items():
            if key not in ('author', 'cover', 'sequence'):
                metadata[key] = prepare_string_for_xml(value)

        return u'<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0" xmlns:xlink="http://www.w3.org/1999/xlink">' \
                '<description>' \
                    '<title-info>' \
                        '<genre>%(genre)s</genre>' \
                            '%(author)s' \
                        '<book-title>%(title)s</book-title>' \
                        '%(cover)s' \
                        '<lang>%(lang)s</lang>' \
                        '%(sequence)s' \
                    '</title-info>' \
                    '<document-info>' \
                        '%(author)s' \
                        '<program-used>%(appname)s %(version)s</program-used>' \
                        '<date>%(date)s</date>' \
                        '<id>%(id)s</id>' \
                        '<version>1.0</version>' \
                    '</document-info>' \
                '</description>' % metadata

    def fb2_footer(self):
        return u'</FictionBook>'

    def get_cover(self):
        from calibre.ebooks.oeb.base import OEB_RASTER_IMAGES

        cover_href = None

        # Get the raster cover if it's available.
        if self.oeb_book.metadata.cover and unicode(self.oeb_book.metadata.cover[0]) in self.oeb_book.manifest.ids:
            id = unicode(self.oeb_book.metadata.cover[0])
            cover_item = self.oeb_book.manifest.ids[id]
            if cover_item.media_type in OEB_RASTER_IMAGES:
                cover_href = cover_item.href
        else:
            # Figure out if we have a title page or a cover page
            page_name = ''
            if 'titlepage' in self.oeb_book.guide:
                page_name = 'titlepage'
            elif 'cover' in self.oeb_book.guide:
                page_name = 'cover'

            if page_name:
                cover_item = self.oeb_book.manifest.hrefs[self.oeb_book.guide[page_name].href]
                # Get the first image in the page
                for img in cover_item.xpath('//img'):
                    cover_href = cover_item.abshref(img.get('src'))
                    break

        if cover_href:
            # Only write the image tag if it is in the manifest.
            if cover_href in self.oeb_book.manifest.hrefs.keys():
                if cover_href not in self.image_hrefs.keys():
                    self.image_hrefs[cover_href] = '_%s.jpg' % len(self.image_hrefs.keys())
            return u'<coverpage><image xlink:href="#%s" /></coverpage>' % self.image_hrefs[cover_href]

        return u''

    def get_text(self):
        from calibre.ebooks.oeb.base import XHTML
        from calibre.ebooks.oeb.stylizer import Stylizer
        text = ['<body>']

        # Create main section if there are no others to create
        if self.opts.sectionize == 'nothing':
            text.append('<section>')
            self.section_level += 1

        for item in self.oeb_book.spine:
            self.log.debug('Converting %s to FictionBook2 XML' % item.href)
            stylizer = Stylizer(item.data, item.href, self.oeb_book, self.opts, self.opts.output_profile)

            # Start a <section> if we must sectionize each file or if the TOC references this page
            page_section_open = False
            if self.opts.sectionize == 'files' or self.toc.get(item.href) == 'page':
                text.append('<section>')
                page_section_open = True
                self.section_level += 1

            text += self.dump_text(item.data.find(XHTML('body')), stylizer, item)

            if page_section_open:
                text.append('</section>')
                self.section_level -= 1

        # Close any open sections
        while self.section_level > 0:
            text.append('</section>')
            self.section_level -= 1

        return ''.join(text) + '</body>'

    def fb2mlize_images(self):
        '''
        This function uses the self.image_hrefs dictionary mapping. It is populated by the dump_text function.
        '''
        from calibre.ebooks.oeb.base import OEB_RASTER_IMAGES

        images = []
        for item in self.oeb_book.manifest:
            # Don't write the image if it's not referenced in the document's text.
            if item.href not in self.image_hrefs:
                continue
            if item.media_type in OEB_RASTER_IMAGES:
                try:
                    if item.media_type != 'image/jpeg':
                        im = Image()
                        im.load(item.data)
                        im.set_compression_quality(70)
                        imdata = im.export('jpg')
                        raw_data = b64encode(imdata)
                    else:
                        raw_data = b64encode(item.data)
                    # Don't put the encoded image on a single line.
                    data = ''
                    col = 1
                    for char in raw_data:
                        if col == 72:
                            data += '\n'
                            col = 1
                        col += 1
                        data += char
                    images.append('<binary id="%s" content-type="image/jpeg">%s\n</binary>' % (self.image_hrefs[item.href], data))
                except Exception as e:
                    self.log.error('Error: Could not include file %s because '
                        '%s.' % (item.href, e))
        return ''.join(images)

    def create_flat_toc(self, nodes, level):
        for item in nodes:
            href, mid, id = item.href.partition('#')
            if not id:
                self.toc[href] = 'page'
            else:
                if not self.toc.get(href, None):
                    self.toc[href] = {}
                self.toc[href][id] = level
                self.create_flat_toc(item.nodes, level + 1)

    def ensure_p(self):
        if self.in_p:
            return [], []
        else:
            self.in_p = True
            return ['<p>'], ['p']

    def close_open_p(self, tags):
        text = ['']
        added_p = False

        if self.in_p:
            # Close all up to p. Close p. Reopen all closed tags including p.
            closed_tags = []
            tags.reverse()
            for t in tags:
                text.append('</%s>' % t)
                closed_tags.append(t)
                if t == 'p':
                    break
            closed_tags.reverse()
            for t in closed_tags:
                text.append('<%s>' % t)
        else:
            text.append('<p>')
            added_p = True
            self.in_p = True

        return text, added_p

    def handle_simple_tag(self, tag, tags):
        s_out = []
        s_tags = []
        if tag not in tags:
            p_out, p_tags = self.ensure_p()
            s_out += p_out
            s_tags += p_tags
            s_out.append('<%s>' % tag)
            s_tags.append(tag)
        return s_out, s_tags

    def dump_text(self, elem_tree, stylizer, page, tag_stack=[]):
        '''
        This function is intended to be used in a recursive manner. dump_text will
        run though all elements in the elem_tree and call itself on each element.

        self.image_hrefs will be populated by calling this function.

        @param elem_tree: etree representation of XHTML content to be transformed.
        @param stylizer: Used to track the style of elements within the tree.
        @param page: OEB page used to determine absolute urls.
        @param tag_stack: List of open FB2 tags to take into account.

        @return: List of string representing the XHTML converted to FB2 markup.
        '''
        from calibre.ebooks.oeb.base import XHTML_NS, barename, namespace
        elem = elem_tree

        # Ensure what we are converting is not a string and that the fist tag is part of the XHTML namespace.
        if not isinstance(elem_tree.tag, basestring) or namespace(elem_tree.tag) != XHTML_NS:
            p = elem.getparent()
            if p is not None and isinstance(p.tag, basestring) and namespace(p.tag) == XHTML_NS \
                    and elem.tail:
                return [elem.tail]
            return []

        style = stylizer.style(elem_tree)
        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            if hasattr(elem, 'tail') and elem.tail:
                return [elem.tail]
            return []

        # FB2 generated output.
        fb2_out = []
        # FB2 tags in the order they are opened. This will be used to close the tags.
        tags = []
        # First tag in tree
        tag = barename(elem_tree.tag)
        # Number of blank lines above tag
        try:
            ems = int(round((float(style.marginTop) / style.fontSize) - 1))
            if ems < 0:
                ems = 0
        except:
            ems = 0

        # Convert TOC entries to <title>s and add <section>s
        if self.opts.sectionize == 'toc':
            # A section cannot be a child of any other element than another section,
            # so leave the tag alone if there are parents
            if not tag_stack:
                # There are two reasons to start a new section here: the TOC pointed to
                # this page (then we use the first non-<body> on the page as a <title>), or
                # the TOC pointed to a specific element
                newlevel = 0
                toc_entry = self.toc.get(page.href, None)
                if toc_entry == 'page':
                    if tag != 'body' and hasattr(elem_tree, 'text') and elem_tree.text:
                        newlevel = 1
                        self.toc[page.href] = None
                elif toc_entry and elem_tree.attrib.get('id', None):
                    newlevel = toc_entry.get(elem_tree.attrib.get('id', None), None)

                # Start a new section if necessary
                if newlevel:
                    if not (newlevel > self.section_level):
                        fb2_out.append('</section>')
                        self.section_level -= 1
                    fb2_out.append('<section>')
                    self.section_level += 1
                    fb2_out.append('<title>')
                    tags.append('title')
            if self.section_level == 0:
                # If none of the prior processing made a section, make one now to be FB2 spec compliant
                fb2_out.append('<section>')
                self.section_level += 1

        # Process the XHTML tag and styles. Converted to an FB2 tag.
        # Use individual if statement not if else. There can be
        # only one XHTML tag but it can have multiple styles.
        if tag == 'img':
            if elem_tree.attrib.get('src', None):
                # Only write the image tag if it is in the manifest.
                ihref = urlnormalize(page.abshref(elem_tree.attrib['src']))
                if ihref in self.oeb_book.manifest.hrefs:
                    if ihref not in self.image_hrefs:
                        self.image_hrefs[ihref] = '_%s.jpg' % len(self.image_hrefs)
                    p_txt, p_tag = self.ensure_p()
                    fb2_out += p_txt
                    tags += p_tag
                    fb2_out.append('<image xlink:href="#%s" />' % self.image_hrefs[ihref])
                else:
                    self.log.warn(u'Ignoring image not in manifest: %s'%ihref)
        if tag in ('br', 'hr') or ems >= 1:
            if ems < 1:
                multiplier = 1
            else:
                multiplier = ems
            if self.in_p:
                closed_tags = []
                open_tags = tag_stack+tags
                open_tags.reverse()
                for t in open_tags:
                    fb2_out.append('</%s>' % t)
                    closed_tags.append(t)
                    if t == 'p':
                        break
                fb2_out.append('<empty-line />' * multiplier)
                closed_tags.reverse()
                for t in closed_tags:
                    fb2_out.append('<%s>' % t)
            else:
                fb2_out.append('<empty-line />' * multiplier)
        if tag in ('div', 'li', 'p'):
            p_text, added_p = self.close_open_p(tag_stack+tags)
            fb2_out += p_text
            if added_p:
                tags.append('p')
        if tag == 'b' or style['font-weight'] in ('bold', 'bolder'):
            s_out, s_tags = self.handle_simple_tag('strong', tag_stack+tags)
            fb2_out += s_out
            tags += s_tags
        if tag == 'i' or style['font-style'] == 'italic':
            s_out, s_tags = self.handle_simple_tag('emphasis', tag_stack+tags)
            fb2_out += s_out
            tags += s_tags
        if tag in ('del', 'strike') or style['text-decoration'] == 'line-through':
            s_out, s_tags = self.handle_simple_tag('strikethrough', tag_stack+tags)
            fb2_out += s_out
            tags += s_tags
        if tag == 'sub':
            s_out, s_tags = self.handle_simple_tag('sub', tag_stack+tags)
            fb2_out += s_out
            tags += s_tags
        if tag == 'sup':
            s_out, s_tags = self.handle_simple_tag('sup', tag_stack+tags)
            fb2_out += s_out
            tags += s_tags

        # Process element text.
        if hasattr(elem_tree, 'text') and elem_tree.text:
            if not self.in_p:
                fb2_out.append('<p>')
            fb2_out.append(prepare_string_for_xml(elem_tree.text))
            if not self.in_p:
                fb2_out.append('</p>')

        # Process sub-elements.
        for item in elem_tree:
            fb2_out += self.dump_text(item, stylizer, page, tag_stack+tags)

        # Close open FB2 tags.
        tags.reverse()
        fb2_out += self.close_tags(tags)

        # Process element text that comes after the close of the XHTML tag but before the next XHTML tag.
        if hasattr(elem_tree, 'tail') and elem_tree.tail:
            if not self.in_p:
                fb2_out.append('<p>')
            fb2_out.append(prepare_string_for_xml(elem_tree.tail))
            if not self.in_p:
                fb2_out.append('</p>')

        return fb2_out

    def close_tags(self, tags):
        text = []
        for tag in tags:
            text.append('</%s>' % tag)
            if tag == 'p':
                self.in_p = False

        return text
