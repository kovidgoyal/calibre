"""
Table of Contents Extension for Python-Markdown
* * *

(c) 2008 [Jack Miller](http://codezen.org)

Dependencies:
* [Markdown 2.0+](http://www.freewisdom.org/projects/python-markdown/)

"""
import calibre.ebooks.markdown.markdown as markdown
from calibre.ebooks.markdown.markdown import etree
import re

class TocTreeprocessor(markdown.treeprocessors.Treeprocessor):
    # Iterator wrapper to get parent and child all at once
    def iterparent(self, root):
        for parent in root.getiterator():
            for child in parent:
                yield parent, child

    def run(self, doc):
        div = etree.Element("div")
        div.attrib["class"] = "toc"
        last_li = None

        # Add title to the div
        if self.config["title"][0]:
            header = etree.SubElement(div, "span")
            header.attrib["class"] = "toctitle"
            header.text = self.config["title"][0]

        level = 0
        list_stack=[div]
        header_rgx = re.compile("[Hh][123456]")

        # Get a list of id attributes
        used_ids = []
        for c in doc.getiterator():
            if "id" in c.attrib:
                used_ids.append(c.attrib["id"])

        for (p, c) in self.iterparent(doc):
            if not c.text:
                continue

            # To keep the output from screwing up the
            # validation by putting a <div> inside of a <p>
            # we actually replace the <p> in its entirety.
            # We do not allow the marker inside a header as that
            # would causes an enless loop of placing a new TOC 
            # inside previously generated TOC.

            if c.text.find(self.config["marker"][0]) > -1 and not header_rgx.match(c.tag):
                for i in range(len(p)):
                    if p[i] == c:
                        p[i] = div
                        break
                    
            if header_rgx.match(c.tag):
                tag_level = int(c.tag[-1])
                
                # Regardless of how many levels we jumped
                # only one list should be created, since
                # empty lists containing lists are illegal.
    
                if tag_level < level:
                    list_stack.pop()
                    level = tag_level

                if tag_level > level:
                    newlist = etree.Element("ul")
                    if last_li:
                        last_li.append(newlist)
                    else:
                        list_stack[-1].append(newlist)
                    list_stack.append(newlist)
                    level = tag_level

                # Do not override pre-existing ids 
                if not "id" in c.attrib:
                    id = self.config["slugify"][0](c.text)
                    if id in used_ids:
                        ctr = 1
                        while "%s_%d" % (id, ctr) in used_ids:
                            ctr += 1
                        id = "%s_%d" % (id, ctr)
                    used_ids.append(id)
                    c.attrib["id"] = id
                else:
                    id = c.attrib["id"]

                # List item link, to be inserted into the toc div
                last_li = etree.Element("li")
                link = etree.SubElement(last_li, "a")
                link.text = c.text
                link.attrib["href"] = '#' + id

                if int(self.config["anchorlink"][0]):
                    anchor = etree.SubElement(c, "a")
                    anchor.text = c.text
                    anchor.attrib["href"] = "#" + id
                    anchor.attrib["class"] = "toclink"
                    c.text = ""

                list_stack[-1].append(last_li)

class TocExtension(markdown.Extension):
    def __init__(self, configs):
        self.config = { "marker" : ["[TOC]", 
                            "Text to find and replace with Table of Contents -"
                            "Defaults to \"[TOC]\""],
                        "slugify" : [self.slugify,
                            "Function to generate anchors based on header text-"
                            "Defaults to a built in slugify function."],
                        "title" : [None,
                            "Title to insert into TOC <div> - "
                            "Defaults to None"],
                        "anchorlink" : [0,
                            "1 if header should be a self link"
                            "Defaults to 0"]}

        for key, value in configs:
            self.setConfig(key, value)

    # This is exactly the same as Django's slugify
    def slugify(self, value):
        """ Slugify a string, to make it URL friendly. """
        import unicodedata
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
        value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
        return re.sub('[-\s]+','-',value)

    def extendMarkdown(self, md, md_globals):
        tocext = TocTreeprocessor(md)
        tocext.config = self.config
        md.treeprocessors.add("toc", tocext, "_begin")
	
def makeExtension(configs={}):
    return TocExtension(configs=configs)
