#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from calibre.ebooks.conversion.preprocess import line_length
from calibre.utils.logging import default_log
from lxml import etree

class PreProcessor(object):
    html_preprocess_sections = 0

    def __init__(self, args):
        self.args = args
        self.log = default_log
   
    def chapter_head(self, match):
        chap = match.group('chap')
        title = match.group('title')
        if not title:
                   self.html_preprocess_sections = self.html_preprocess_sections + 1
                   self.log("marked " + str(self.html_preprocess_sections) + " chapters. - " + str(chap))
                   return '<h2>'+chap+'</h2>\n'
        else:
                   self.html_preprocess_sections = self.html_preprocess_sections + 1
                   self.log("marked " + str(self.html_preprocess_sections) + " chapters & titles. - " + str(chap) + ", " + str(title))
                   return '<h2>'+chap+'</h2>\n<h3>'+title+'</h3>\n'

    def chapter_link(self, match):
        chap = match.group('sectionlink')
        if not chap:
                   self.html_preprocess_sections = self.html_preprocess_sections + 1
                   self.log("marked " + str(self.html_preprocess_sections) + " section markers based on links")
                   return '<br style="page-break-before:always">'
        else:
                   self.html_preprocess_sections = self.html_preprocess_sections + 1
                   self.log("marked " + str(self.html_preprocess_sections) + " section markers based on links. - " + str(chap))
                   return '<br clear="all" style="page-break-before:always">\n<h2>'+chap+'</h2>'

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
        self.log("*** There are " + str(tot_ln_fds) + " total Line feeds, and " + str(tot_htm_ends) + " marked endings***")

        if percent > 1:
            percent = 1
        if percent < 0:
            percent = 0    
    
        min_lns = tot_ln_fds * percent
        self.log("There must be fewer than " + str(min_lns) + " unmarked lines to return true")
        if min_lns > tot_htm_ends:
            return True
            
    def __call__(self, html):
        self.log("*********  Preprocessing HTML  *********")
        # remove non-breaking spaces
        html = re.sub(ur'\u00a0', ' ', html)
        # Get rid of empty <o:p> tags to simplify other processing
        html = re.sub(ur'\s*<o:p>\s*</o:p>', ' ', html)
        # Get rid of empty span tags
        html = re.sub(r"\s*<span[^>]*>\s*</span>", " ", html)
        
        # If more than 40% of the lines are empty paragraphs then delete them to clean up spacing
        linereg = re.compile('(?<=<p).*?(?=</p>)', re.IGNORECASE)
        blankreg = re.compile(r'\s*<p[^>]*>\s*(<(b|i|u)>)?\s*(</(b|i|u)>)?\s*</p>', re.IGNORECASE)
        blanklines = blankreg.findall(html)
        lines = linereg.findall(html)
        if len(lines) > 1:
            self.log("There are " + str(len(blanklines)) + " blank lines. " + str(float(len(blanklines)) / float(len(lines))) + " percent blank")
            if float(len(blanklines)) / float(len(lines)) > 0.40:
                self.log("deleting blank lines")
                html = blankreg.sub('', html)
        # Arrange line feeds and </p> tags so the line_length and no_markup functions work correctly
        html = re.sub(r"\s*</p>", "</p>\n", html)
        html = re.sub(r"\s*<p>\s*", "\n<p>", html)
        
        # some lit files don't have any <p> tags or equivalent, check and 
        # mark up line endings if required before proceeding
        if self.no_markup(html, 0.1):
             self.log("not enough paragraph markers, adding now")
             add_markup = re.compile('(?<!>)(\n)')
             html = add_markup.sub('</p>\n<p>', html)
        
        # detect chapters/sections to match xpath or splitting logic
        # 
        # Start with most typical chapter headings       
        chapdetect = re.compile(r'(?=</?(br|p))(<(/?br|p)[^>]*>)\s*(<(i|b|u)>){0,2}\s*(<span[^>]*>)?\s*(?P<chap>(<(i|b|u)>){0,2}s*(<span[^>]*>)?\s*.?(Introduction|Acknowledgements|Chapter|Epilogue|Volume|Prologue|Book\s|Part\s|Dedication)\s*([\d\w-]+\:?\s*){0,8}\s*(</(i|b|u)>){0,2})\s*(</span>)?s*(</span>)?\s*(</(i|b|u)>){0,2}\s*(</(p|/?br)>)\s*(<(/?br|p)[^>]*>\s*(<(i|b|u)>){0,2}\s*(<span[^>]*>)?\s*(?P<title>(<(i|b|u)>){0,2}(\s*[\w\'\"-]+){1,5}\s*(</(i|b|u)>){0,2})\s*(</span>)?\s*(</(i|b|u)>){0,2}\s*(</(br|p)>))?', re.IGNORECASE)
        html = chapdetect.sub(self.chapter_head, html)
        if self.html_preprocess_sections < 10:
            self.log("not enough chapters, only " + str(self.html_preprocess_sections) + ", trying a more aggressive pattern")
            chapdetect2 = re.compile(r'(?=</?(br|p))(<(/?br|p)[^>]*>)\s*(<(i|b|u)>){0,2}\s*(<span[^>]*>)?\s*(?P<chap>(<(i|b|u)>){0,2}\s*.?(([A-Z#-]+\s*){1,9}|\d+\.?|(CHAPTER\s*([\dA-Z\-\'\"\?\.!#,]+\s*){1,10}))\s*(</(i|b|u)>){0,2})\s*(</span>)?\s*(</(i|b|u)>){0,2}\s*(</(p|/?br)>)\s*(<(/?br|p)[^>]*>\s*(<(i|b|u)>){0,2}\s*(<span[^>]*>)?\s*(?P<title>(<(i|b|u)>){0,2}(\s*[\w\'\"-]+){1,5}\s*(</(i|b|u)>){0,2})\s*(</span>)?\s*(</(i|b|u)>){0,2}\s*(</(br|p)>))?', re.UNICODE)
            html = chapdetect2.sub(self.chapter_head, html)    
        #    
        # Unwrap lines using punctation if the median length of all lines is less than 200        
        length = line_length('html', html, 0.4)
        self.log("*** Median line length is " + str(length) + " ***")
        unwrap = re.compile(r"(?<=.{%i}[a-z,;:\IA])\s*</(span|p|div)>\s*(</(p|span|div)>)?\s*(?P<up2threeblanks><(p|span|div)[^>]*>\s*(<(p|span|div)[^>]*>\s*</(span|p|div)>\s*)</(span|p|div)>\s*){0,3}\s*<(span|div|p)[^>]*>\s*(<(span|div|p)[^>]*>)?\s*" % length, re.UNICODE)
        if length < 200:
            self.log("Unwrapping Lines")
            html = unwrap.sub(' ', html)        
        # If still no sections after unwrapping lines break on lines with no punctuation
        if self.html_preprocess_sections < 10:
            self.log("not enough chapters, only " + str(self.html_preprocess_sections) + ", splitting based on punctuation")
            #self.log(html)
            chapdetect3 = re.compile(r'(<p[^>]*>)\s*(<(i|b|u)>){0,2}\s*(<span[^>]*>)?\s*(?P<chap>(<(i|b|u)>){0,2}\s*.?([a-z]+\s*){1,5}\s*(</(i|b|u)>){0,2})\s*(</span>)?\s*(</(i|b|u)>){0,2}\s*(</p>)(?P<title>)?', re.IGNORECASE)
            html = chapdetect3.sub(self.chapter_head, html)        
        # search for places where a first or second level heading is immediately followed by another
        # top level heading.  demote the second heading to h3 to prevent splitting between chapter
        # headings and titles, images, etc
        doubleheading = re.compile(r'(?P<firsthead><h(1|2)[^>]*>.+?</h(1|2)>\s*(<(?!h\d)[^>]*>\s*)*)<h(1|2)(?P<secondhead>[^>]*>.+?)</h(1|2)>', re.IGNORECASE)
        html = doubleheading.sub('\g<firsthead>'+'<h3'+'\g<secondhead>'+'</h3>', html)
        
        return html