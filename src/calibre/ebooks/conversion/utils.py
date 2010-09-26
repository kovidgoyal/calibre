#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from calibre.ebooks.conversion.preprocess import line_length, Dehyphenator
from calibre.utils.logging import default_log

class PreProcessor(object):

    def __init__(self, extra_opts=None, log=None):
        self.log = default_log if log is None else log
        self.html_preprocess_sections = 0
        self.found_indents = 0
        self.extra_opts = extra_opts

    def chapter_head(self, match):
        chap = match.group('chap')
        title = match.group('title')
        if not title:
            self.html_preprocess_sections = self.html_preprocess_sections + 1
            self.log("found " + str(self.html_preprocess_sections) + " chapters. - " + str(chap))
            return '<h2>'+chap+'</h2>\n'
        else:
            self.html_preprocess_sections = self.html_preprocess_sections + 1
            self.log("found " + str(self.html_preprocess_sections) + " chapters & titles. - " + str(chap) + ", " + str(title))
            return '<h2>'+chap+'</h2>\n<h3>'+title+'</h3>\n'

    def chapter_break(self, match):
        chap = match.group('section')
        styles = match.group('styles')
        self.html_preprocess_sections = self.html_preprocess_sections + 1
        self.log("marked " + str(self.html_preprocess_sections) + " section markers based on punctuation. - " + str(chap))
        return '<'+styles+' style="page-break-before:always">'+chap

    def insert_indent(self, match):
        pstyle = match.group('formatting')
        span = match.group('span')
        self.found_indents = self.found_indents + 1
        if pstyle:
            if not span:
                return '<p '+pstyle+' style="text-indent:3%">'
            else:
                return '<p '+pstyle+' style="text-indent:3%">'+span
        else:
            if not span:
                return '<p style="text-indent:3%">'
            else:
                return '<p style="text-indent:3%">'+span

    def no_markup(self, raw, percent):
        '''
        Detects total marked up line endings in the file. raw is the text to
        inspect.  Percent is the minimum percent of line endings which should
        be marked up to return true.
        '''
        htm_end_ere = re.compile('</p>', re.DOTALL)
        line_end_ere = re.compile('(\n|\r|\r\n)', re.DOTALL)
        htm_end = htm_end_ere.findall(raw)
        line_end = line_end_ere.findall(raw)
        tot_htm_ends = len(htm_end)
        tot_ln_fds = len(line_end)
        self.log("There are " + str(tot_ln_fds) + " total Line feeds, and " + str(tot_htm_ends) + " marked up endings")

        if percent > 1:
            percent = 1
        if percent < 0:
            percent = 0

        min_lns = tot_ln_fds * percent
        self.log("There must be fewer than " + str(min_lns) + " unmarked lines to add markup")
        if min_lns > tot_htm_ends:
            return True

    def __call__(self, html):
        self.log("*********  Preprocessing HTML  *********")
        ###### Check Markup ######
        #
        # some lit files don't have any <p> tags or equivalent (generally just plain text between
        # <pre> tags), check and  mark up line endings if required before proceeding
        if self.no_markup(html, 0.1):
             self.log("not enough paragraph markers, adding now")
             # check if content is in pre tags, use txt procesor to mark up if so
             pre = re.compile(r'<pre>', re.IGNORECASE)
             if len(pre.findall(html)) == 1:
                 self.log("Running Text Processing")
                 from calibre.ebooks.txt.processor import convert_basic, preserve_spaces, \
                 separate_paragraphs_single_line
                 outerhtml = re.compile(r'.*?(?<=<pre>)(?P<text>.*)(?=</pre>).*', re.IGNORECASE|re.DOTALL)
                 html = outerhtml.sub('\g<text>', html)
                 html = separate_paragraphs_single_line(html)
                 html = preserve_spaces(html)
                 html = convert_basic(html, epub_split_size_kb=0)
             else:
                 # Add markup naively
                 # TODO - find out if there are cases where there are more than one <pre> tag or
                 # other types of unmarked html and handle them in some better fashion
                 add_markup = re.compile('(?<!>)(\n)')
                 html = add_markup.sub('</p>\n<p>', html)

        ###### Mark Indents/Cleanup ######
        #
        # Replace series of non-breaking spaces with text-indent
        txtindent = re.compile(ur'<p(?P<formatting>[^>]*)>\s*(?P<span>(<span[^>]*>\s*)+)?\s*(\u00a0){2,}', re.IGNORECASE)
        html = txtindent.sub(self.insert_indent, html)
        if self.found_indents > 1:
            self.log("replaced "+str(self.found_indents)+ " nbsp indents with inline styles")
        # remove remaining non-breaking spaces
        html = re.sub(ur'\u00a0', ' ', html)
        # Get rid of empty <o:p> tags to simplify other processing
        html = re.sub(ur'\s*<o:p>\s*</o:p>', ' ', html)
        # Get rid of empty span, bold, & italics tags
        html = re.sub(r"\s*<span[^>]*>\s*(<span[^>]>\s*</span>){0,2}\s*</span>\s*", " ", html)
        html = re.sub(r"\s*<[ibu][^>]*>\s*(<[ibu][^>]*>\s*</[ibu]>\s*){0,2}\s*</[ibu]>", " ", html)
        html = re.sub(r"\s*<span[^>]*>\s*(<span[^>]>\s*</span>){0,2}\s*</span>\s*", " ", html)

        # If more than 40% of the lines are empty paragraphs then delete them to clean up spacing
        linereg = re.compile('(?<=<p).*?(?=</p>)', re.IGNORECASE|re.DOTALL)
        blankreg = re.compile(r'\s*(?P<openline><p[^>]*>)\s*(?P<closeline></p>)', re.IGNORECASE)
        #multi_blank = re.compile(r'(\s*<p[^>]*>\s*(<(b|i|u)>)?\s*(</(b|i|u)>)?\s*</p>){2,}', re.IGNORECASE)
        blanklines = blankreg.findall(html)
        lines = linereg.findall(html)
        if len(lines) > 1:
            self.log("There are " + str(len(blanklines)) + " blank lines. " + str(float(len(blanklines)) / float(len(lines))) + " percent blank")
            if float(len(blanklines)) / float(len(lines)) > 0.40 and getattr(self.extra_opts,
            'remove_paragraph_spacing', False):
                self.log("deleting blank lines")
                html = blankreg.sub('', html)
        # Arrange line feeds and </p> tags so the line_length and no_markup functions work correctly
        html = re.sub(r"\s*</p>", "</p>\n", html)
        html = re.sub(r"\s*<p>\s*", "\n<p>", html)
        # detect chapters/sections to match xpath or splitting logic
        heading = re.compile('<h[1-3][^>]*>', re.IGNORECASE)
        self.html_preprocess_sections = len(heading.findall(html))
        self.log("found " + str(self.html_preprocess_sections) + " pre-existing headings")
        #
        # Start with most typical chapter headings, get more aggressive until one works
        if self.html_preprocess_sections < 10:
            chapdetect = re.compile(r'(?=</?(br|p))(<(/?br|p)[^>]*>)\s*(<[ibu][^>]*>){0,2}\s*(<span[^>]*>)?\s*(<[ibu][^>]*>){0,2}\s*(<span[^>]*>)?\s*(?P<chap>(<[ibu][^>]*>){0,2}\s*.?(Introduction|Synopsis|Acknowledgements|Chapter|Epilogue|Volume|Prologue|Book\s|Part\s|Dedication)\s*([\d\w-]+\:?\s*){0,8}\s*(</[ibu]>){0,2})\s*(</span>)?s*(</[ibu]>){0,2}\s*(</span>)?\s*(</(p|/?br)>)\s*\s*(\s*<p[^>]*>\s*</p>){0,2}\s*(<(/?br|p)[^>]*>\s*(<[ibu][^>]*>){0,2}\s*(<span[^>]*>)?\s*(?P<title>(<[ibu][^>]*>){0,2}(\s*[\w\'\"-]+){1,5}\s*(</[ibu]>){0,2})\s*(</span>)?\s*(</[ibu]>){0,2}\s*(</(br|p)>))?', re.IGNORECASE|re.VERBOSE)
            html = chapdetect.sub(self.chapter_head, html)
        if self.html_preprocess_sections < 10:
            self.log("not enough chapters, only " + str(self.html_preprocess_sections) + ", trying numeric chapters")
            chapdetect2 = re.compile(r'(?=</?(br|p))(<(/?br|p)[^>]*>)\s*(<[ibu][^>]*>){0,2}\s*(<span[^>]*>)?\s*(?P<chap>(<[ibu][^>]*>){0,2}\s*.?(\d+\.?|(CHAPTER\s*([\dA-Z\-\'\"\?\.!#,]+\s*){1,10}))\s*(</[ibu]>){0,2})\s*(</span>)?\s*(</[ibu]>){0,2}\s*(</(p|/?br)>)\s*(<(/?br|p)[^>]*>\s*(<[ibu][^>]*>){0,2}\s*(<span[^>]*>)?\s*(?P<title>(<[ibu][^>]*>){0,2}(\s*[\w\'\"-]+){1,5}\s*(</[ibu]>){0,2})\s*(</span>)?\s*(</[ibu]>){0,2}\s*(</(br|p)>))?', re.UNICODE)
            html = chapdetect2.sub(self.chapter_head, html)

        if self.html_preprocess_sections < 10:
            self.log("not enough chapters, only " + str(self.html_preprocess_sections) + ", trying with uppercase words")
            chapdetect2 = re.compile(r'(?=</?(br|p))(<(/?br|p)[^>]*>)\s*(<[ibu][^>]*>){0,2}\s*(<span[^>]*>)?\s*(?P<chap>(<[ibu][^>]*>){0,2}\s*.?([A-Z#\-\s]+)\s*(</[ibu]>){0,2})\s*(</span>)?\s*(</[ibu]>){0,2}\s*(</(p|/?br)>)\s*(<(/?br|p)[^>]*>\s*(<[ibu][^>]*>){0,2}\s*(<span[^>]*>)?\s*(?P<title>(<[ibu][^>]*>){0,2}(\s*[\w\'\"-]+){1,5}\s*(</[ibu]>){0,2})\s*(</span>)?\s*(</[ibu]>){0,2}\s*(</(br|p)>))?', re.UNICODE)
            html = chapdetect2.sub(self.chapter_head, html)

        ###### Unwrap lines ######
        #
        self.log("Unwrapping Lines")
        # Some OCR sourced files have line breaks in the html using a combination of span & p tags
        # span are used for hard line breaks, p for new paragraphs.  Determine which is used so
        # that lines can be un-wrapped across page boundaries
        paras_reg = re.compile('<p[^>]*>', re.IGNORECASE)
        spans_reg = re.compile('<span[^>]*>', re.IGNORECASE)
        paras = len(paras_reg.findall(html))
        spans = len(spans_reg.findall(html))
        if spans > 1:
            if float(paras) / float(spans) < 0.75:
                format = 'spanned_html'
            else:
                format = 'html'
        else:
            format = 'html'

        # Calculate Length
        length = line_length(format, html, getattr(self.extra_opts,
            'html_unwrap_factor', 0.4))
        self.log("*** Median line length is " + str(length) + ", calculated with " + format + " format ***")
        max_length = length * 1.4
        min_max = str("(?<=.{"+str(length)+"})(?<!.{"+str(max_length)+"})")
        #
        # Unwrap em/en dashes, delete soft-hyphens
        #self.log("\n\n\n\n\n\n\n\n\n\n\n"+html+"\n\n\n\n\n\n\n\n\n\n\n\n\n")
        html = re.sub(u'\xad\s*(</span>\s*(</[iubp]>\s*<[iubp][^>]*>\s*)?<span[^>]*>|</[iubp]>\s*<[iubp][^>]*>)?\s*', '', html)
        html = re.sub(u'%s(?<=[\u2013\u2014])\s*(?=<)(</span>\s*(</[iubp]>\s*<[iubp][^>]*>\s*)?<span[^>]*>|</[iubp]>\s*<[iubp][^>]*>)?\s*(?=[[a-z\d])' % min_max, '', html)
        # Dehyphenate
        dehyphenator = Dehyphenator()
        html = dehyphenator(html,'html', length)

        # Unwrap lines using punctation and line length
        unwrap = re.compile(r"(?<=.{%i}([a-z,;):\IA]|(?<!\&\w{4});))\s*</(span|p|div)>\s*(</(p|span|div)>)?\s*(?P<up2threeblanks><(p|span|div)[^>]*>\s*(<(p|span|div)[^>]*>\s*</(span|p|div)>\s*)</(span|p|div)>\s*){0,3}\s*<(span|div|p)[^>]*>\s*(<(span|div|p)[^>]*>)?\s*" % length, re.UNICODE)
        html = unwrap.sub(' ', html)

        # If still no sections after unwrapping mark split points on lines with no punctuation
        if self.html_preprocess_sections < 10:
            self.log("Looking for more split points based on punctuation, currently have " + str(self.html_preprocess_sections))
            chapdetect3 = re.compile(r'<(?P<styles>(p|div)[^>]*)>\s*(?P<section>(<span[^>]*>)?\s*(<[ibu][^>]*>){0,2}\s*(<span[^>]*>)?\s*(<[ibu][^>]*>){0,2}\s*(<span[^>]*>)?\s*.?(?=[a-z#\-*\s]+<)([a-z#-*]+\s*){1,5}\s*\s*(</span>)?(</[ibu]>){0,2}\s*(</span>)?\s*(</[ibu]>){0,2}\s*(</span>)?\s*</(p|div)>)', re.IGNORECASE)
            html = chapdetect3.sub(self.chapter_break, html)
        # search for places where a first or second level heading is immediately followed by another
        # top level heading.  demote the second heading to h3 to prevent splitting between chapter
        # headings and titles, images, etc
        doubleheading = re.compile(r'(?P<firsthead><h(1|2)[^>]*>.+?</h(1|2)>\s*(<(?!h\d)[^>]*>\s*)*)<h(1|2)(?P<secondhead>[^>]*>.+?)</h(1|2)>', re.IGNORECASE)
        html = doubleheading.sub('\g<firsthead>'+'\n<h3'+'\g<secondhead>'+'</h3>', html)

        # put back non-breaking spaces in empty paragraphs to preserve original formatting
        html = blankreg.sub('\n'+r'\g<openline>'+u'\u00a0'+r'\g<closeline>', html)

        return html
