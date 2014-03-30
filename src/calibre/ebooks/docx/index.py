#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import OrderedDict

from lxml.html.builder import A, SPAN
import lxml.etree

from calibre.ebooks.docx.names import XPath, ancestor, namespaces


NBSP = '\xa0'

class Location(object):
    r"""
    This class represents one location in the index.
    We should provide a way to mark the main entries. Libre office
    has a main attribute, which doesn't seem to map to docx, and at least
    some versions of word can mark entries bold or italic with \b and \i.
    One index entry corresponds to a list of locations where the entry
    is referenced in the text.
    """

    def __init__(self, bookmark, target):
        self.bookmark = bookmark
        self.target = target

class Entry(object):
    """
    This class represents one index entry.
    We can also have a list of sub-entries for the primary/secondary
    topic situation.
    Each entry has a list of locations we want to point to, but
    it could be empty if this is only here to organize sub-entries.
    """

    def __init__(self, name, index):
        self.subentries = {}
        self.locations = []
        self.name = name
        self.index = index

    def add_entry(self, entry, sub):
        """
        The entry has the form [xxx, field, bookmark, target]
        """
        if len(sub) == 0:
            self.locations.append(Location(entry[2], entry[3]))
        else:
            sube = find_entry(sub[0], self.subentries, self.index)
            sube.add_entry(entry, sub[1:])

    def make_link(self, loc, amap):
        # As a first pass, we just put a placeholder in the target location
        # We want it to float right
        markid = amap[loc.bookmark]
        if markid is None:
            return

        span = A()
        span.set('style', 'float:right')
        span.set('href', '#' + markid)
        from calibre.ebooks.docx.to_html import Text
        text = Text(span, 'text', [])
        text.buf.append(loc.target)
        setattr(text.elem, text.attr, ''.join(text.buf))
        return span

    def to_htmlunit(self, body, level, amap):
        """
        Append the material for one index entry to the document.
        There is a name, and 0 or more locations.
        Put the first location, if any, on the same line as the
        name, and others on following lines.
        """
        style = self.index.entry_styles[level]
        main = add_name(self.name, style)
        if len(self.locations) == 0:
            body.append(main)
            return

        # First link on same line as name
        link = self.make_link(self.locations[0], amap)
        main.append(link)
        body.append(main)

        # Put other links for same entry on their own lines
        # To keep the link span separate need to put a space as the name
        for l in self.locations[1:]:
            link = self.make_link(l, amap)
            dest = P()
            dest.set('class', style)
            dest.text = NBSP
            dest.append(link)
            body.append(dest)

    def to_html(self, body, level, amap):
        level = min(level, 2)
        self.to_htmlunit(body, level, amap)
        for key in sorted(self.subentries.keys()):
            self.subentries[key].to_html(body, level + 1, amap)

class Section(object):
    """
    This class represents one section of the index - usually,
    for example, the A's or the B's.
    It is primarily a dictionary of entries.
    """

    def __init__(self, index):
        self.index = index
        self.entries = {}

    def add_entry(self, entry):
        """
        We have information from one index marker.
        The entry has form [name, field, bookmark, target].
        The name is something like A or A:B and so on.
        If we already have an entry for that name, just add the new
        location to it; otherwise create a new entry.
        """
        topics = entry[0].strip('"').split(':')
        targ = find_entry(topics[0], self.entries, self.index)
        targ.add_entry(entry, topics[1:])

    def to_html(self, key, body, amap):
        """
        Add one section of the index to the html
        """
        if len(key) > 0:
            body.append(add_name(key, self.index.section_style))
        for ekey in sorted(self.entries.keys()):
            self.entries[ekey].to_html(body, 0, amap)

class Index(object):
    """
    This class generates an alphabetical index from the index markers in a docx file.

    Each field in the parse of the docx file contains an instructions list.
    Instructions with name XE are index instructions.
    The instruction also contains the entry specifier, of the form A[:B[:C]] for
    main entry, A, subentry B, and so on.

    The index object is a dictionary of sections, 'A' mapping to a section
    object with all the A entries, and so on. Each section in turn is a dictionary
    mapping an index specifier, like A:B, to a list of locations where that
    entry is referenced.

    We could make the formatting more configurable.
    Currently it uses fixed styles for the various elements, and a section
    heading for each letter.
    """

    def __init__(self, convert):
        """
        Convert the index markers in the document into an index object.
        """
        self.convert = convert
        self.sections = {}

        self.gen_styles()

        # Get a list of [name, field] entries, where name is the index
        # entry and field is the indexed location
        self.entries = self.get_entries()

        # Find styles which are provide the text for links.
        self.target_styles()

        # Generate bookmarks in the document at the indexed locations
        self.bookmarks()

        # Set up the entries in index sections
        for unit in self.entries:
            sec = self.find_section(unit[0])
            sec.add_entry(unit)

    def get_entries(self):
        r"""
        We already have a list of fields which includes the index marks,
        identified by an XE tag.
        In the base case, the field object includes an instruction list
        with one tuple like ('XE', '"entry"'), where entry is the text we
        want to put in the index. Note the double quotes around the entry.
        Sometimes the entry is broken up in the document, for example if
        there are spelling issues in the entry text.
        In this case, for reasons I don't understand, the instruction
        list includes a number of tuples, and we get the actual entry
        text by concatenating all of them after the initial tag.
        There can be formatting information in the instructions also, after
        the double quoted part, like '"entry" \b'.
        So, we want to concatenate all parts after the initial tag, and
        then get the part in double quotes.
        """
        fields = self.convert.fields.fields

        def get_entry(field):
            elist = [field.instructions[0][1]]
            for inst in field.instructions[1:]:
                elist.append(inst[0])
                elist.append(inst[1])

            entry = ''.join(elist)
            sep1 = entry.partition('"')
            if sep1[2] == '':
                return entry
            sep2 = sep1[2].partition('"')
            return sep2[0]

        # Only want the index entries
        return [[get_entry(f), f] for f in fields
                if f.instructions and f.instructions[0][0] == 'XE']

    def target_styles(self):
        """
        We want to get a list of styles which represent valid index targets.
        That is, the text of a link in the index will be the title of the
        section of the document containing the indexed location.
        We want the list of styles which can provide a valid title.
        In practice, this maps to Heading1 through Heading3 in the original document.
        Calibre apparently preprocesses docx files, so that a paragraph in
        the original with style Heading1 will now have a different, internal style.
        In this version we use convert.styles.id_map to find style ids
        with internal names beginning Heading; but I'd feel better if we
        jumped in earlier and could map it to the original docx styles.
        """
        smap = self.convert.styles.id_map
        self.targstyles = [name for name, style in smap.iteritems() if style.name.lower().startswith('heading')]

    def is_heading(self, node):
        """
        Return true if the input node is a valid index link target.
        """
        snodes = XPath("./w:pPr/w:pStyle")(node)
        if len(snodes) == 0:
            return False

        sn = snodes[0]

        # The key includes the long namespace information
        k = [key for key in sn.keys() if key.endswith('}val')]
        if len(k) == 0:
            return False
        style = sn.get(k[0])
        return style in self.targstyles

    def get_headings(self, node):
        """
        Get a list of all children of the input node which are headings -
        that is, valid targets for an index link
        """
        answer = []
        for c in node.getchildren():
            if self.is_heading(c):
                answer.append(c)
        return answer

    def text_value(self, node):
        tnodes = XPath("./w:r/w:t")(node)
        if len(tnodes) == 0:
            return 'Link'
        return ''.join((x.text or '') for x in tnodes)

    def find_target(self, node):
        """
        Given an index entry, find the text of the last heading section
        preceding the entry.
        To do this, find the containing w:p element. If it is a heading,
        return the text.
        Otherwise, go up the document level by level, staring with the
        parent of the w:p element containing the entry.
        At each level, get the list of heading w:p elements which are
        children of the top node. We also have the index in the top node
        of the child node containing the entry.
        Find the largest index of a heading child which is < the entry
        index, if any - that is the heading we want.
        Perhaps we should precalculate some of this.
        We could also consider doing some of this in xpath, but the style
        attributes have been modified, so we can't just look for the
        original names.
        """
        pnode = ancestor(node, 'w:p')
        if self.is_heading(pnode):
            return self.text_value(pnode)

        while True:
            parent = pnode.getparent()
            if parent is None:
                return 'Link'

            # Maintain document order in these lists
            pindex = parent.index(pnode)
            hlist = self.get_headings(parent)
            hlist = filter(lambda x: parent.index(x) < pindex, hlist)
            if len(hlist) > 0:
                return self.text_value(hlist[-1])

            # Try again
            pnode = parent

    def bookmarks(self):
        """
        For each index entry we need to insert a bookmark at the target location.
        These bookmarks are for our internal use - I'm not sure they would work well
        in the original docx document.
        For each entry we have the Field object, which includes the instrText
        element of the document.
        Try going to the parent, and inserting a bookmark start just before it.
        """
        bmno = 0
        for entry in self.entries:
            for instnode in entry[1].elements:
                name = 'indexBookmark' + str(bmno)
                bmno += 1
                tag = "{%s}bookmarkStart" % namespaces['w']
                att = "{%s}name" % namespaces['w']
                bookmark = lxml.etree.Element(tag)
                bookmark.set(att, name)
                rnode = instnode.getparent()

                # Add the name so that we can link to it
                entry.append(name)

                # insert the bookmark before rnode
                rparent = rnode.getparent()
                rind = rparent.index(rnode)
                rparent.insert(rind, bookmark)

                # We want the index entry to be the content of the closest
                # preceding Heading paragraph.
                # We should make the targets configurable, and add chapter
                # titles and maybe other things.
                # What about numbering?
                targnode = self.find_target(rnode)
                entry.append(targnode)

    def gen_styles(self):
        """
        Generate css styles for the index elements.
        We do title, section header, and three levels of entries.
        These are reasonable styles which only set a couple of key
        values, but we could provide an interface to allow the user to set them.
        Is there any problem registering the styles this early in the
        conversion process?
        """
        # The result is a string we can use as a class name.
        css = OrderedDict([('font-size', '20pt'), ('page-break-before', 'always')])
        self.title_style = self.convert.styles.register(css, 'block')

        css = OrderedDict([('font-size', '16pt'), ('margin-top', '20pt'), ('margin-bottom', '10pt')])
        self.section_style = self.convert.styles.register(css, 'block')

        self.entry_styles = []
        for i in range(3):
            indent = str(i*20) + 'pt'
            css = OrderedDict([('margin-top', '0pt'), ('margin-bottom', '0pt'), ('margin-left', indent)])
            self.entry_styles.append(self.convert.styles.register(css, 'block'))

    def find_section(self, tag):
        """
        Find the section for this index entry, creating it if required.
        The tag has a form like A or A:B or etc.
        If you want a single index without section divisions, you can
        just return the single section here every time.
        """
        shead = tag[0]

        # Make it lower case, and group all non-alphabetic things together
        if shead.isalpha():
            shead = shead.lower()
        else:
            shead = ''

        if shead in self.sections:
            return self.sections[shead]
        sect = Section(self)
        self.sections[shead] = sect
        return sect

    def generate(self):
        """
        We generated the index object in the constructor.
        This method writes it into the html.
        """
        # TODO: Only do this at locations of the INDEX field in the document
        body = self.convert.body
        body.append(add_name('Index', self.title_style))

        # And write them to the html
        for key in sorted(self.sections.keys()):
            self.sections[key].to_html(key, body, self.convert.anchor_map)

def add_name(str, clname):
    # Put this into the convert document map?
    dest = P()
    dest.set('class', clname)
    span = SPAN()
    from calibre.ebooks.docx.to_html import Text
    text = Text(span, 'text', [])
    text.buf.append(str)
    setattr(text.elem, text.attr, ''.join(text.buf))
    dest.append(span)
    return dest

def find_entry(value, dict, index):
    """
    Find the Entry in the dictionary, or create a new one.
    We convert to lower case to group all capitalizations
    together as a single entry.
    """
    lvalue = value.lower()
    if lvalue in dict:
        return dict[lvalue]
    ent = Entry(value, index)
    dict[lvalue] = ent
    return ent
