## To access this file as plain text go to
## http://freewisdom.org/projects/python-markdown/mdx_toc.raw_content

"""
Chris Clark - clach04 -at- sf.net

My markdown extensions for adding:
    Table of Contents (aka toc)
"""

import re
import markdown

DEFAULT_TITLE = None

def extract_alphanumeric(in_str=None):
    """take alpha-numeric (7bit ascii) and return as a string
    """
    # I'm sure this is really inefficient and
    # could be done with a lambda/map()
    #x.strip(). title().replace(' ', "")
    out_str=[]
    for x in in_str:
        x = icu_title(x)
        if x.isalnum(): out_str.append(x)
    return ''.join(out_str)

class TitlePostprocessor (markdown.Postprocessor):

    def __init__ (self, extension) :
        self.extension = extension

    def run(self, doc) :
        titleElement = self.extension.createTitle(doc)
        if titleElement :
            doc.documentElement.insertChild(0, titleElement)


class TocExtension (markdown.Extension):
    """Markdown extension: generate a Table Of Contents (aka toc)
    toc is returned in a div tag with class='toc'
    toc is either:
        appended to end of document
      OR
        replaces first string occurence of "///Table of Contents Goes Here///"
    """

    def __init__ (self, configs={}) :
        #maybe add these as parameters to the class init?
        self.TOC_INCLUDE_MARKER = "///Table of Contents///"
        self.TOC_TITLE = "Table Of Contents"
        self.auto_toc_heading_type=2
        self.toc_heading_type=3
        self.configs = configs

    def extendMarkdown(self, md, md_globals) :
        # Just insert in the end
        md.postprocessors.append(TocPostprocessor(self))
        # Stateless extensions do not need to be registered, so we don't
        # register.

    def findTocPlaceholder(self, doc) :
        def findTocPlaceholderFn(node=None, indent=0):
            if node.type == 'text':
                if node.value.find(self.TOC_INCLUDE_MARKER) > -1 :
                    return True

        toc_div_list = doc.find(findTocPlaceholderFn)
        if toc_div_list :
            return toc_div_list[0]


    def createTocDiv(self, doc) :
        """
           Creates Table Of Contents based on headers.

           @returns: toc as a single as a dom element
                     in a <div> tag with class='toc'
        """

        # Find headers
        headers_compiled_re = re.compile("h[123456]", re.IGNORECASE)
        def findHeadersFn(element=None):
            if element.type=='element':
                if headers_compiled_re.match(element.nodeName):
                    return True

        headers_doc_list = doc.find(findHeadersFn)

        # Insert anchor tags into dom
        generated_anchor_id=0
        headers_list=[]
        min_header_size_found = 6
        for element in headers_doc_list:
            heading_title = element.childNodes[0].value
            if heading_title.strip() !="":
                heading_type = int(element.nodeName[-1:])
                if heading_type == self.auto_toc_heading_type:
                    min_header_size_found=min(min_header_size_found,
                                              heading_type)

                html_anchor_name= (extract_alphanumeric(heading_title)
                                   +'__MD_autoTOC_%d' % (generated_anchor_id))

                # insert anchor tag inside header tags
                html_anchor = doc.createElement("a")
                html_anchor.setAttribute('name', html_anchor_name)
                element.appendChild(html_anchor)

                headers_list.append( (heading_type, heading_title,
                                      html_anchor_name) )
                generated_anchor_id = generated_anchor_id + 1

        # create dom for toc
        if headers_list != []:
            # Create list
            toc_doc_list = doc.createElement("ul")
            for (heading_type, heading_title, html_anchor_name) in headers_list:
                if heading_type == self.auto_toc_heading_type:
                    toc_doc_entry = doc.createElement("li")
                    toc_doc_link = doc.createElement("a")
                    toc_doc_link.setAttribute('href', '#'+html_anchor_name)
                    toc_doc_text = doc.createTextNode(heading_title)
                    toc_doc_link.appendChild(toc_doc_text)
                    toc_doc_entry.appendChild(toc_doc_link)
                    toc_doc_list.appendChild(toc_doc_entry)


            # Put list into div
            div = doc.createElement("div")
            div.setAttribute('class', 'toc')
            if self.TOC_TITLE:
                toc_header = doc.createElement("h%d"%(self.toc_heading_type) )
                toc_header_text = doc.createTextNode(self.TOC_TITLE)
                toc_header.appendChild(toc_header_text)
                div.appendChild(toc_header)
            div.appendChild(toc_doc_list)
            #hr = doc.createElement("hr")
            #div.appendChild(hr)

            return div


class TocPostprocessor (markdown.Postprocessor):

    def __init__ (self, toc) :
        self.toc = toc

    def run(self, doc):
        tocPlaceholder = self.toc.findTocPlaceholder(doc)

        if self.toc.configs.get("disable_toc", False):
            if tocPlaceholder:
                tocPlaceholder.parent.replaceChild(tocPlaceholder, "")
        else:

            tocDiv = self.toc.createTocDiv(doc)

            if tocDiv:
                if tocPlaceholder :
                    # Replace "magic" pattern with toc
                    tocPlaceholder.parent.replaceChild(tocPlaceholder, tocDiv)
                else :
                    # Dump at the end of the DOM
                    # Probably want to use CSS to position div
                    doc.documentElement.appendChild(tocDiv)


def makeExtension(configs={}):
    return TocExtension(configs=configs)
