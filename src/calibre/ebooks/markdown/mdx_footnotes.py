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
"""

FN_BACKLINK_TEXT = "zz1337820767766393qq"


import re, markdown, random

class FootnoteExtension (markdown.Extension):

    DEF_RE = re.compile(r'(\ ?\ ?\ ?)\[\^([^\]]*)\]:\s*(.*)')
    SHORT_USE_RE = re.compile(r'\[\^([^\]]*)\]', re.M) # [^a]

    def __init__ (self, configs) :

        self.config = {'PLACE_MARKER' :
                       ["///Footnotes Go Here///",
                        "The text string that marks where the footnotes go"]}

        for key, value in configs :
            self.config[key][0] = value
            
        self.reset()

    def extendMarkdown(self, md, md_globals) :

        self.md = md

        # Stateless extensions do not need to be registered
        md.registerExtension(self)

        # Insert a preprocessor before ReferencePreprocessor
        index = md.preprocessors.index(md_globals['REFERENCE_PREPROCESSOR'])
        preprocessor = FootnotePreprocessor(self)
        preprocessor.md = md
        md.preprocessors.insert(index, preprocessor)

        # Insert an inline pattern before ImageReferencePattern
        FOOTNOTE_RE = r'\[\^([^\]]*)\]' # blah blah [^1] blah
        index = md.inlinePatterns.index(md_globals['IMAGE_REFERENCE_PATTERN'])
        md.inlinePatterns.insert(index, FootnotePattern(FOOTNOTE_RE, self))

        # Insert a post-processor that would actually add the footnote div
        postprocessor = FootnotePostprocessor(self)
        postprocessor.extension = self

        md.postprocessors.append(postprocessor)
        
        textPostprocessor = FootnoteTextPostprocessor(self)

        md.textPostprocessors.append(textPostprocessor)


    def reset(self) :
        # May be called by Markdown is state reset is desired

        self.footnote_suffix = "-" + str(int(random.random()*1000000000))
        self.used_footnotes={}
        self.footnotes = {}

    def findFootnotesPlaceholder(self, doc) :
        def findFootnotePlaceholderFn(node=None, indent=0):
            if node.type == 'text':
                if node.value.find(self.getConfig("PLACE_MARKER")) > -1 :
                    return True

        fn_div_list = doc.find(findFootnotePlaceholderFn)
        if fn_div_list :
            return fn_div_list[0]


    def setFootnote(self, id, text) :
        self.footnotes[id] = text

    def makeFootnoteId(self, num) :
        return 'fn%d%s' % (num, self.footnote_suffix)

    def makeFootnoteRefId(self, num) :
        return 'fnr%d%s' % (num, self.footnote_suffix)

    def makeFootnotesDiv (self, doc) :
        """Creates the div with class='footnote' and populates it with
           the text of the footnotes.

           @returns: the footnote div as a dom element """

        if not self.footnotes.keys() :
            return None

        div = doc.createElement("div")
        div.setAttribute('class', 'footnote')
        hr = doc.createElement("hr")
        div.appendChild(hr)
        ol = doc.createElement("ol")
        div.appendChild(ol)

        footnotes = [(self.used_footnotes[id], id)
                     for id in self.footnotes.keys()]
        footnotes.sort()

        for i, id in footnotes :
            li = doc.createElement('li')
            li.setAttribute('id', self.makeFootnoteId(i))

            self.md._processSection(li, self.footnotes[id].split("\n"), looseList=1)

            #li.appendChild(doc.createTextNode(self.footnotes[id]))

            backlink = doc.createElement('a')
            backlink.setAttribute('href', '#' + self.makeFootnoteRefId(i))
            backlink.setAttribute('class', 'footnoteBackLink')
            backlink.setAttribute('title',
                                  'Jump back to footnote %d in the text' % 1)
            backlink.appendChild(doc.createTextNode(FN_BACKLINK_TEXT))

            if li.childNodes :
                node = li.childNodes[-1]
                if node.type == "text" :
		            li.appendChild(backlink)
                elif node.nodeName == "p":
                    node.appendChild(backlink)
                else:
                    p = doc.createElement('p')
                    p.appendChild(backlink)
                    li.appendChild(p)

            ol.appendChild(li)

        return div


class FootnotePreprocessor :

    def __init__ (self, footnotes) :
        self.footnotes = footnotes

    def run(self, lines) :

        self.blockGuru = markdown.BlockGuru()
        lines = self._handleFootnoteDefinitions (lines)

        # Make a hash of all footnote marks in the text so that we
        # know in what order they are supposed to appear.  (This
        # function call doesn't really substitute anything - it's just
        # a way to get a callback for each occurence.

        text = "\n".join(lines)
        self.footnotes.SHORT_USE_RE.sub(self.recordFootnoteUse, text)

        return text.split("\n")


    def recordFootnoteUse(self, match) :

        id = match.group(1)
        id = id.strip()
        nextNum = len(self.footnotes.used_footnotes.keys()) + 1
        self.footnotes.used_footnotes[id] = nextNum


    def _handleFootnoteDefinitions(self, lines) :
        """Recursively finds all footnote definitions in the lines.

            @param lines: a list of lines of text
            @returns: a string representing the text with footnote
                      definitions removed """

        i, id, footnote = self._findFootnoteDefinition(lines)

        if id :

            plain = lines[:i]

            detabbed, theRest = self.blockGuru.detectTabbed(lines[i+1:])

            self.footnotes.setFootnote(id,
                                       footnote + "\n"
                                       + "\n".join(detabbed))

            more_plain = self._handleFootnoteDefinitions(theRest)
            return plain + [""] + more_plain

        else :
            return lines

    def _findFootnoteDefinition(self, lines) :
        """Finds the first line of a footnote definition.

            @param lines: a list of lines of text
            @returns: the index of the line containing a footnote definition """

        counter = 0
        for line in lines :
            m = self.footnotes.DEF_RE.match(line)
            if m :
                return counter, m.group(2), m.group(3)
            counter += 1
        return counter, None, None


class FootnotePattern (markdown.Pattern) :

    def __init__ (self, pattern, footnotes) :

        markdown.Pattern.__init__(self, pattern)
        self.footnotes = footnotes

    def handleMatch(self, m, doc) :
        sup = doc.createElement('sup')
        a = doc.createElement('a')
        sup.appendChild(a)
        id = m.group(2)
        num = self.footnotes.used_footnotes[id]
        sup.setAttribute('id', self.footnotes.makeFootnoteRefId(num))
        a.setAttribute('href', '#' + self.footnotes.makeFootnoteId(num))
        a.appendChild(doc.createTextNode(str(num)))
        return sup

class FootnotePostprocessor (markdown.Postprocessor):

    def __init__ (self, footnotes) :
        self.footnotes = footnotes

    def run(self, doc) :
        footnotesDiv = self.footnotes.makeFootnotesDiv(doc)
        if footnotesDiv :
            fnPlaceholder = self.extension.findFootnotesPlaceholder(doc)
            if fnPlaceholder :
                fnPlaceholder.parent.replaceChild(fnPlaceholder, footnotesDiv)
            else :
                doc.documentElement.appendChild(footnotesDiv)

class FootnoteTextPostprocessor (markdown.Postprocessor):

    def __init__ (self, footnotes) :
        self.footnotes = footnotes

    def run(self, text) :
        return text.replace(FN_BACKLINK_TEXT, "&#8617;")

def makeExtension(configs=None) :
    return FootnoteExtension(configs=configs)

