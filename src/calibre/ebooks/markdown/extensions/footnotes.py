"""
========================= FOOTNOTES =================================

This section adds footnote handling to markdown.  It can be used as
an example for extending python-markdown with relatively complex
functionality.  While in this case the extension is included inside
the module itself, it could just as easily be added from outside the
module.  Not that all markdown classes above are ignorant about
footnotes.  All footnote functionality is provided separately and
then added to the markdown instance at the run time.

Footnote functionality is attached by calling extendMarkdown()
method of FootnoteExtension.  The method also registers the
extension to allow it's state to be reset by a call to reset()
method.

Example:
    Footnotes[^1] have a label[^label] and a definition[^!DEF].

    [^1]: This is a footnote
    [^label]: A footnote on "label"
    [^!DEF]: The footnote for definition

"""

import re
import calibre.ebooks.markdown.markdown as markdown
from calibre.ebooks.markdown.markdown import etree

FN_BACKLINK_TEXT = "zz1337820767766393qq"
NBSP_PLACEHOLDER =  "qq3936677670287331zz"
DEF_RE = re.compile(r'(\ ?\ ?\ ?)\[\^([^\]]*)\]:\s*(.*)')
TABBED_RE = re.compile(r'((\t)|(    ))(.*)')

class FootnoteExtension(markdown.Extension):
    """ Footnote Extension. """

    def __init__ (self, configs):
        """ Setup configs. """
        self.config = {'PLACE_MARKER':
                       ["///Footnotes Go Here///",
                        "The text string that marks where the footnotes go"]}

        for key, value in configs:
            self.config[key][0] = value

        self.reset()

    def extendMarkdown(self, md, md_globals):
        """ Add pieces to Markdown. """
        md.registerExtension(self)
        self.parser = md.parser
        # Insert a preprocessor before ReferencePreprocessor
        md.preprocessors.add("footnote", FootnotePreprocessor(self),
                             "<reference")
        # Insert an inline pattern before ImageReferencePattern
        FOOTNOTE_RE = r'\[\^([^\]]*)\]' # blah blah [^1] blah
        md.inlinePatterns.add("footnote", FootnotePattern(FOOTNOTE_RE, self),
                              "<reference")
        # Insert a tree-processor that would actually add the footnote div
        # This must be before the inline treeprocessor so inline patterns
        # run on the contents of the div.
        md.treeprocessors.add("footnote", FootnoteTreeprocessor(self),
                                 "<inline")
        # Insert a postprocessor after amp_substitute oricessor
        md.postprocessors.add("footnote", FootnotePostprocessor(self),
                                  ">amp_substitute")

    def reset(self):
        """ Clear the footnotes on reset. """
        self.footnotes = markdown.odict.OrderedDict()

    def findFootnotesPlaceholder(self, root):
        """ Return ElementTree Element that contains Footnote placeholder. """
        def finder(element):
            for child in element:
                if child.text:
                    if child.text.find(self.getConfig("PLACE_MARKER")) > -1:
                        return child, True
                if child.tail:
                    if child.tail.find(self.getConfig("PLACE_MARKER")) > -1:
                        return (child, element), False
                finder(child)
            return None

        res = finder(root)
        return res

    def setFootnote(self, id, text):
        """ Store a footnote for later retrieval. """
        self.footnotes[id] = text

    def makeFootnoteId(self, id):
        """ Return footnote link id. """
        return 'fn:%s' % id

    def makeFootnoteRefId(self, id):
        """ Return footnote back-link id. """
        return 'fnref:%s' % id

    def makeFootnotesDiv(self, root):
        """ Return div of footnotes as et Element. """

        if not self.footnotes.keys():
            return None

        div = etree.Element("div")
        div.set('class', 'footnote')
        etree.SubElement(div, "hr")
        ol = etree.SubElement(div, "ol")

        for id in self.footnotes.keys():
            li = etree.SubElement(ol, "li")
            li.set("id", self.makeFootnoteId(id))
            self.parser.parseChunk(li, self.footnotes[id])
            backlink = etree.Element("a")
            backlink.set("href", "#" + self.makeFootnoteRefId(id))
            backlink.set("rev", "footnote")
            backlink.set("title", "Jump back to footnote %d in the text" % \
                            (self.footnotes.index(id)+1))
            backlink.text = FN_BACKLINK_TEXT

            if li.getchildren():
                node = li[-1]
                if node.tag == "p":
                    node.text = node.text + NBSP_PLACEHOLDER
                    node.append(backlink)
                else:
                    p = etree.SubElement(li, "p")
                    p.append(backlink)
        return div


class FootnotePreprocessor(markdown.preprocessors.Preprocessor):
    """ Find all footnote references and store for later use. """

    def __init__ (self, footnotes):
        self.footnotes = footnotes

    def run(self, lines):
        lines = self._handleFootnoteDefinitions(lines)
        text = "\n".join(lines)
        return text.split("\n")

    def _handleFootnoteDefinitions(self, lines):
        """
        Recursively find all footnote definitions in lines.

        Keywords:

        * lines: A list of lines of text

        Return: A list of lines with footnote definitions removed.

        """
        i, id, footnote = self._findFootnoteDefinition(lines)

        if id :
            plain = lines[:i]
            detabbed, theRest = self.detectTabbed(lines[i+1:])
            self.footnotes.setFootnote(id,
                                       footnote + "\n"
                                       + "\n".join(detabbed))
            more_plain = self._handleFootnoteDefinitions(theRest)
            return plain + [""] + more_plain
        else :
            return lines

    def _findFootnoteDefinition(self, lines):
        """
        Find the parts of a footnote definition.

        Keywords:

        * lines: A list of lines of text.

        Return: A three item tuple containing the index of the first line of a
        footnote definition, the id of the definition and the body of the
        definition.

        """
        counter = 0
        for line in lines:
            m = DEF_RE.match(line)
            if m:
                return counter, m.group(2), m.group(3)
            counter += 1
        return counter, None, None

    def detectTabbed(self, lines):
        """ Find indented text and remove indent before further proccesing.

        Keyword arguments:

        * lines: an array of strings

        Returns: a list of post processed items and the unused
        remainder of the original list

        """
        items = []
        i = 0 # to keep track of where we are

        def detab(line):
            match = TABBED_RE.match(line)
            if match:
               return match.group(4)

        for line in lines:
            if line.strip(): # Non-blank line
                line = detab(line)
                if line:
                    items.append(line)
                    i += 1
                    continue
                else:
                    return items, lines[i:]

            else: # Blank line: _maybe_ we are done.
                i += 1 # advance

                # Find the next non-blank line
                for j in range(i, len(lines)):
                    if lines[j].strip():
                        next_line = lines[j]; break
                else:
                    break # There is no more text; we are done.

                # Check if the next non-blank line is tabbed
                if detab(next_line): # Yes, more work to do.
                    items.append("")
                    continue
                else:
                    break # No, we are done.
        else:
            i += 1

        return items, lines[i:]


class FootnotePattern(markdown.inlinepatterns.Pattern):
    """ InlinePattern for footnote markers in a document's body text. """

    def __init__(self, pattern, footnotes):
        markdown.inlinepatterns.Pattern.__init__(self, pattern)
        self.footnotes = footnotes

    def handleMatch(self, m):
        sup = etree.Element("sup")
        a = etree.SubElement(sup, "a")
        id = m.group(2)
        sup.set('id', self.footnotes.makeFootnoteRefId(id))
        a.set('href', '#' + self.footnotes.makeFootnoteId(id))
        a.set('rel', 'footnote')
        a.text = str(self.footnotes.footnotes.index(id) + 1)
        return sup


class FootnoteTreeprocessor(markdown.treeprocessors.Treeprocessor):
    """ Build and append footnote div to end of document. """

    def __init__ (self, footnotes):
        self.footnotes = footnotes

    def run(self, root):
        footnotesDiv = self.footnotes.makeFootnotesDiv(root)
        if footnotesDiv:
            result = self.footnotes.findFootnotesPlaceholder(root)
            if result:
                node, isText = result
                if isText:
                    node.text = None
                    node.getchildren().insert(0, footnotesDiv)
                else:
                    child, element = node
                    ind = element.getchildren().find(child)
                    element.getchildren().insert(ind + 1, footnotesDiv)
                    child.tail = None
            else:
                root.append(footnotesDiv)

class FootnotePostprocessor(markdown.postprocessors.Postprocessor):
    """ Replace placeholders with html entities. """

    def run(self, text):
        text = text.replace(FN_BACKLINK_TEXT, "&#8617;")
        return text.replace(NBSP_PLACEHOLDER, "&#160;")

def makeExtension(configs=[]):
    """ Return an instance of the FootnoteExtension """
    return FootnoteExtension(configs=configs)

