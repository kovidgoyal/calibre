#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from calibre.ebooks.conversion.preprocess import DocAnalysis, Dehyphenator
from calibre.utils.logging import default_log
from calibre.utils.wordcount import get_wordcount_obj

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
            self.log("marked " + unicode(self.html_preprocess_sections) +
                    " chapters. - " + unicode(chap))
            return '<h2>'+chap+'</h2>\n'
        else:
            self.html_preprocess_sections = self.html_preprocess_sections + 1
            self.log("marked " + unicode(self.html_preprocess_sections) +
                    " chapters & titles. - " + unicode(chap) + ", " + unicode(title))
            return '<h2>'+chap+'</h2>\n<h3>'+title+'</h3>\n'

    def chapter_break(self, match):
        chap = match.group('section')
        styles = match.group('styles')
        self.html_preprocess_sections = self.html_preprocess_sections + 1
        self.log("marked " + unicode(self.html_preprocess_sections) +
                " section markers based on punctuation. - " + unicode(chap))
        return '<'+styles+' style="page-break-before:always">'+chap

    def insert_indent(self, match):
        pstyle = match.group('formatting')
        span = match.group('span')
        self.found_indents = self.found_indents + 1
        if pstyle:
            if pstyle.lower().find('style'):
                pstyle = re.sub(r'"$', '; text-indent:3%"', pstyle)
            else:
                pstyle = pstyle+' style="text-indent:3%"'
            if not span:
                return '<p '+pstyle+'>'
            else:
                return '<p '+pstyle+'>'+span
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
        htm_end_ere = re.compile('</(p|div)>', re.DOTALL)
        line_end_ere = re.compile('(\n|\r|\r\n)', re.DOTALL)
        htm_end = htm_end_ere.findall(raw)
        line_end = line_end_ere.findall(raw)
        tot_htm_ends = len(htm_end)
        tot_ln_fds = len(line_end)
        self.log("There are " + unicode(tot_ln_fds) + " total Line feeds, and " +
                unicode(tot_htm_ends) + " marked up endings")

        if percent > 1:
            percent = 1
        if percent < 0:
            percent = 0

        min_lns = tot_ln_fds * percent
        self.log("There must be fewer than " + unicode(min_lns) + " unmarked lines to add markup")
        if min_lns > tot_htm_ends:
            return True

    def dump(self, raw, where):
        import os
        dp = getattr(self.extra_opts, 'debug_pipeline', None)
        if dp and os.path.exists(dp):
            odir = os.path.join(dp, 'preprocess')
            if not os.path.exists(odir):
                    os.makedirs(odir)
            if os.path.exists(odir):
                odir = os.path.join(odir, where)
                if not os.path.exists(odir):
                    os.makedirs(odir)
                name, i = None, 0
                while not name or os.path.exists(os.path.join(odir, name)):
                    i += 1
                    name = '%04d.html'%i
                with open(os.path.join(odir, name), 'wb') as f:
                    f.write(raw.encode('utf-8'))

    def get_word_count(self, html):
        totalwords = 0
        word_count_text = re.sub(r'(?s)<head[^>]*>.*?</head>', '', html)
        word_count_text = re.sub(r'<[^>]*>', '', word_count_text)
        wordcount = get_wordcount_obj(word_count_text)
        return wordcount.words

    def markup_chapters(self, html, wordcount, blanks_between_paragraphs):
        # Typical chapters are between 2000 and 7000 words, use the larger number to decide the 
        # minimum of chapters to search for
        self.min_chapters = 1
        if wordcount > 7000:
            self.min_chapters = wordcount / 7000
        print "minimum chapters required are: "+str(self.min_chapters)
        heading = re.compile('<h[1-3][^>]*>', re.IGNORECASE)
        self.html_preprocess_sections = len(heading.findall(html))
        self.log("found " + unicode(self.html_preprocess_sections) + " pre-existing headings")

        # Build the Regular Expressions in pieces
        init_lookahead = "(?=<(p|div))"
        chapter_line_open = "<(?P<outer>p|div)[^>]*>\s*(<(?P<inner1>font|span|[ibu])[^>]*>)?\s*(<(?P<inner2>font|span|[ibu])[^>]*>)?\s*(<(?P<inner3>font|span|[ibu])[^>]*>)?\s*"
        title_line_open = "<(?P<outer2>p|div)[^>]*>\s*(<(?P<inner4>font|span|[ibu])[^>]*>)?\s*(<(?P<inner5>font|span|[ibu])[^>]*>)?\s*(<(?P<inner6>font|span|[ibu])[^>]*>)?\s*"
        chapter_header_open = r"(?P<chap>"
        title_header_open = r"(?P<title>"
        chapter_header_close = ")\s*"
        title_header_close = ")"
        chapter_line_close = "(</(?P=inner3)>)?\s*(</(?P=inner2)>)?\s*(</(?P=inner1)>)?\s*</(?P=outer)>"
        title_line_close = "(</(?P=inner6)>)?\s*(</(?P=inner5)>)?\s*(</(?P=inner4)>)?\s*</(?P=outer2)>"

        if blanks_between_paragraphs:
            blank_lines = "(\s*<p[^>]*>\s*</p>){0,2}\s*"
        else:
            blank_lines = ""
        opt_title_open = "("
        opt_title_close = ")?"
        n_lookahead_open = "\s+(?!"
        n_lookahead_close = ")"

        default_title = r"\s{0,3}([\w\'\"-]+\s{0,3}){1,5}?(?=<)"
        
        chapter_types = [
            [r"[^'\"]?(Introduction|Synopsis|Acknowledgements|Chapter|Kapitel|Epilogue|Volume\s|Prologue|Book\s|Part\s|Dedication)\s*([\d\w-]+\:?\s*){0,4}", True, "Searching for common Chapter Headings"],
            [r"[^'\"]?(\d+\.?|CHAPTER)\s*([\dA-Z\-\'\"\?\.!#,]+\s*){0,7}\s*", True, "Searching for numeric chapter headings"],  # Numeric Chapters
            [r"<b[^>]*>\s*(<span[^>]*>)?\s*(?!([*#•]+\s*)+)(\s*(?=[\w#\-*\s]+<)([\w#-*]+\s*){1,5}\s*)(</span>)?\s*</b>", True, "Searching for emphasized lines"], # Emphasized lines
            [r"[^'\"]?(\d+\.?\s+([\d\w-]+\:?\'?-?\s?){0,5})\s*", True, "Searching for numeric chapters with titles"], # Numeric Titles
            [r"\s*[^'\"]?([A-Z#]+(\s|-){0,3}){1,5}\s*", False, "Searching for chapters with Uppercase Characters" ] # Uppercase Chapters
            ]

        # Start with most typical chapter headings, get more aggressive until one works
        for [chapter_type, lookahead_ignorecase, log_message] in chapter_types:
            if self.html_preprocess_sections >= self.min_chapters:
                break
            full_chapter_line = chapter_line_open+chapter_header_open+chapter_type+chapter_header_close+chapter_line_close
            n_lookahead = re.sub("(ou|in|cha)", "lookahead_", full_chapter_line)
            self.log("Marked " + unicode(self.html_preprocess_sections) + " headings, " + log_message)
            if lookahead_ignorecase:
                chapter_marker = init_lookahead+full_chapter_line+blank_lines+n_lookahead_open+n_lookahead+n_lookahead_close+opt_title_open+title_line_open+title_header_open+default_title+title_header_close+title_line_close+opt_title_close
                chapdetect = re.compile(r'%s' % chapter_marker, re.IGNORECASE)
            else:
                chapter_marker = init_lookahead+full_chapter_line+blank_lines+opt_title_open+title_line_open+title_header_open+default_title+title_header_close+title_line_close+opt_title_close+n_lookahead_open+n_lookahead+n_lookahead_close
                chapdetect = re.compile(r'%s' % chapter_marker, re.UNICODE)
                
            html = chapdetect.sub(self.chapter_head, html)

        words_per_chptr = wordcount
        if words_per_chptr > 0 and self.html_preprocess_sections > 0:
            words_per_chptr = wordcount / self.html_preprocess_sections
        print "Total wordcount is: "+ str(wordcount)+", Average words per section is: "+str(words_per_chptr)+", Marked up "+str(self.html_preprocess_sections)+" chapters"            

        return html



    def __call__(self, html):
        self.log("*********  Preprocessing HTML  *********")

        # Count the words in the document to estimate how many chapters to look for and whether
        # other types of processing are attempted
        totalwords = self.get_word_count(html)
        
        if totalwords < 10:
            print "not enough text, not preprocessing"
            return html

        # Arrange line feeds and </p> tags so the line_length and no_markup functions work correctly
        html = re.sub(r"\s*</(?P<tag>p|div)>", "</"+"\g<tag>"+">\n", html)
        html = re.sub(r"\s*<(?P<tag>p|div)(?P<style>[^>]*)>\s*", "\n<"+"\g<tag>"+"\g<style>"+">", html)
        
        ###### Check Markup ######
        #
        # some lit files don't have any <p> tags or equivalent (generally just plain text between
        # <pre> tags), check and  mark up line endings if required before proceeding
        if self.no_markup(html, 0.1):
             self.log("not enough paragraph markers, adding now")
             # check if content is in pre tags, use txt processor to mark up if so
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
            self.log("replaced "+unicode(self.found_indents)+ " nbsp indents with inline styles")
        # remove remaining non-breaking spaces
        html = re.sub(ur'\u00a0', ' ', html)
        # Get rid of empty <o:p> tags to simplify other processing
        html = re.sub(ur'\s*<o:p>\s*</o:p>', ' ', html)
        # Get rid of empty span, bold, & italics tags
        html = re.sub(r"\s*<span[^>]*>\s*(<span[^>]*>\s*</span>){0,2}\s*</span>\s*", " ", html)
        html = re.sub(r"\s*<[ibu][^>]*>\s*(<[ibu][^>]*>\s*</[ibu]>\s*){0,2}\s*</[ibu]>", " ", html)
        html = re.sub(r"\s*<span[^>]*>\s*(<span[^>]>\s*</span>){0,2}\s*</span>\s*", " ", html)

        # If more than 40% of the lines are empty paragraphs and the user has enabled remove
        # paragraph spacing then delete blank lines to clean up spacing
        linereg = re.compile('(?<=<p).*?(?=</p>)', re.IGNORECASE|re.DOTALL)
        blankreg = re.compile(r'\s*(?P<openline><p[^>]*>)\s*(?P<closeline></p>)', re.IGNORECASE)
        #multi_blank = re.compile(r'(\s*<p[^>]*>\s*(<(b|i|u)>)?\s*(</(b|i|u)>)?\s*</p>){2,}', re.IGNORECASE)
        blanklines = blankreg.findall(html)
        lines = linereg.findall(html)
        blanks_between_paragraphs = False
        if len(lines) > 1:
            self.log("There are " + unicode(len(blanklines)) + " blank lines. " +
                    unicode(float(len(blanklines)) / float(len(lines))) + " percent blank")
            if float(len(blanklines)) / float(len(lines)) > 0.40 and getattr(self.extra_opts,
            'remove_paragraph_spacing', False):
                self.log("deleting blank lines")
                html = blankreg.sub('', html)
            elif float(len(blanklines)) / float(len(lines)) > 0.40:
               blanks_between_paragraphs = True
               #print "blanks between paragraphs is marked True"
            else:
                blanks_between_paragraphs = False
                
        #self.dump(html, 'before_chapter_markup')
        # detect chapters/sections to match xpath or splitting logic
        #

        self.markup_chapters(html, totalwords, blanks_between_paragraphs)


        ###### Unwrap lines ######
        #
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
        # Check Line histogram to determine if the document uses hard line breaks, If 50% or
        # more of the lines break in the same region of the document then unwrapping is required
        docanalysis = DocAnalysis(format, html)
        hardbreaks = docanalysis.line_histogram(.50)
        self.log("Hard line breaks check returned "+unicode(hardbreaks))
        # Calculate Length
        unwrap_factor = getattr(self.extra_opts, 'html_unwrap_factor', 0.4)
        length = docanalysis.line_length(unwrap_factor)
        self.log("Median line length is " + unicode(length) + ", calculated with " + format + " format")
        # only go through unwrapping code if the histogram shows unwrapping is required or if the user decreased the default unwrap_factor
        if hardbreaks or unwrap_factor < 0.4:
            self.log("Unwrapping required, unwrapping Lines")
            # Unwrap em/en dashes
            html = re.sub(u'(?<=.{%i}[\u2013\u2014])\s*(?=<)(</span>\s*(</[iubp]>\s*<[iubp][^>]*>\s*)?<span[^>]*>|</[iubp]>\s*<[iubp][^>]*>)?\s*(?=[[a-z\d])' % length, '', html)
            # Dehyphenate
            self.log("Unwrapping/Removing hyphens")
            dehyphenator = Dehyphenator()
            html = dehyphenator(html,'html', length)
            self.log("Done dehyphenating")
            # Unwrap lines using punctation and line length
            #unwrap_quotes = re.compile(u"(?<=.{%i}\"')\s*</(span|p|div)>\s*(</(p|span|div)>)?\s*(?P<up2threeblanks><(p|span|div)[^>]*>\s*(<(p|span|div)[^>]*>\s*</(span|p|div)>\s*)</(span|p|div)>\s*){0,3}\s*<(span|div|p)[^>]*>\s*(<(span|div|p)[^>]*>)?\s*(?=[a-z])" % length, re.UNICODE)
            unwrap = re.compile(u"(?<=.{%i}([a-zäëïöüàèìòùáćéíóńśúâêîôûçąężı,:)\IA\u00DF]|(?<!\&\w{4});))\s*</(span|p|div)>\s*(</(p|span|div)>)?\s*(?P<up2threeblanks><(p|span|div)[^>]*>\s*(<(p|span|div)[^>]*>\s*</(span|p|div)>\s*)</(span|p|div)>\s*){0,3}\s*<(span|div|p)[^>]*>\s*(<(span|div|p)[^>]*>)?\s*" % length, re.UNICODE)
            html = unwrap.sub(' ', html)
            #check any remaining hyphens, but only unwrap if there is a match
            dehyphenator = Dehyphenator()
            html = dehyphenator(html,'html_cleanup', length)
        else:
            # dehyphenate in cleanup mode to fix anything previous conversions/editing missed
            self.log("Cleaning up hyphenation")
            dehyphenator = Dehyphenator()
            html = dehyphenator(html,'html_cleanup', length)
            self.log("Done dehyphenating")

        # delete soft hyphens
        html = re.sub(u'\xad\s*(</span>\s*(</[iubp]>\s*<[iubp][^>]*>\s*)?<span[^>]*>|</[iubp]>\s*<[iubp][^>]*>)?\s*', '', html)

        # If still no sections after unwrapping mark split points on lines with no punctuation
        if self.html_preprocess_sections < self.min_chapters:
            self.log("Looking for more split points based on punctuation,"
                    " currently have " + unicode(self.html_preprocess_sections))
            chapdetect3 = re.compile(r'<(?P<styles>(p|div)[^>]*)>\s*(?P<section>(<span[^>]*>)?\s*(?!([*#•]+\s*)+)(<[ibu][^>]*>){0,2}\s*(<span[^>]*>)?\s*(<[ibu][^>]*>){0,2}\s*(<span[^>]*>)?\s*.?(?=[a-z#\-*\s]+<)([a-z#-*]+\s*){1,5}\s*\s*(</span>)?(</[ibu]>){0,2}\s*(</span>)?\s*(</[ibu]>){0,2}\s*(</span>)?\s*</(p|div)>)', re.IGNORECASE)
            html = chapdetect3.sub(self.chapter_break, html)
        # search for places where a first or second level heading is immediately followed by another
        # top level heading.  demote the second heading to h3 to prevent splitting between chapter
        # headings and titles, images, etc
        doubleheading = re.compile(r'(?P<firsthead><h(1|2)[^>]*>.+?</h(1|2)>\s*(<(?!h\d)[^>]*>\s*)*)<h(1|2)(?P<secondhead>[^>]*>.+?)</h(1|2)>', re.IGNORECASE)
        html = doubleheading.sub('\g<firsthead>'+'\n<h3'+'\g<secondhead>'+'</h3>', html)

        # put back non-breaking spaces in empty paragraphs to preserve original formatting
        html = blankreg.sub('\n'+r'\g<openline>'+u'\u00a0'+r'\g<closeline>', html)

        # Center separator lines
        html = re.sub(u'<p>\s*(?P<break>([*#•]+\s*)+)\s*</p>', '<p style="text-align:center">' + '\g<break>' + '</p>', html)

        return html
