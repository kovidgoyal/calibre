#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import functools, re, json

from calibre import entity_to_unicode, as_unicode

XMLDECL_RE    = re.compile(r'^\s*<[?]xml.*?[?]>')
SVG_NS       = 'http://www.w3.org/2000/svg'
XLINK_NS     = 'http://www.w3.org/1999/xlink'

convert_entities = functools.partial(entity_to_unicode,
        result_exceptions = {
            u'<' : '&lt;',
            u'>' : '&gt;',
            u"'" : '&apos;',
            u'"' : '&quot;',
            u'&' : '&amp;',
        })
_span_pat = re.compile('<span.*?</span>', re.DOTALL|re.IGNORECASE)

LIGATURES = {
#        u'\u00c6': u'AE',
#        u'\u00e6': u'ae',
#        u'\u0152': u'OE',
#        u'\u0153': u'oe',
#        u'\u0132': u'IJ',
#        u'\u0133': u'ij',
#        u'\u1D6B': u'ue',
        u'\uFB00': u'ff',
        u'\uFB01': u'fi',
        u'\uFB02': u'fl',
        u'\uFB03': u'ffi',
        u'\uFB04': u'ffl',
        u'\uFB05': u'ft',
        u'\uFB06': u'st',
        }

_ligpat = re.compile(u'|'.join(LIGATURES))

def sanitize_head(match):
    x = match.group(1)
    x = _span_pat.sub('', x)
    return '<head>\n%s\n</head>' % x

def chap_head(match):
    chap = match.group('chap')
    title = match.group('title')
    if not title:
        return '<h1>'+chap+'</h1><br/>\n'
    else:
        return '<h1>'+chap+'</h1>\n<h3>'+title+'</h3>\n'

def wrap_lines(match):
    ital = match.group('ital')
    if not ital:
        return ' '
    else:
        return ital+' '

class DocAnalysis(object):
    '''
    Provides various text analysis functions to determine how the document is structured.
    format is the type of document analysis will be done against.
    raw is the raw text to determine the line length to use for wrapping.
    Blank lines are excluded from analysis
    '''

    def __init__(self, format='html', raw=''):
        raw = raw.replace('&nbsp;', ' ')
        if format == 'html':
            linere = re.compile('(?<=<p)(?![^>]*>\s*</p>).*?(?=</p>)', re.DOTALL)
        elif format == 'pdf':
            linere = re.compile('(?<=<br>)(?!\s*<br>).*?(?=<br>)', re.DOTALL)
        elif format == 'spanned_html':
            linere = re.compile('(?<=<span).*?(?=</span>)', re.DOTALL)
        elif format == 'txt':
            linere = re.compile('.*?\n')
        self.lines = linere.findall(raw)

    def line_length(self, percent):
        '''
        Analyses the document to find the median line length.
        percentage is a decimal number, 0 - 1 which is used to determine
        how far in the list of line lengths to use. The list of line lengths is
        ordered smallest to larged and does not include duplicates. 0.5 is the
        median value.
        '''
        lengths = []
        for line in self.lines:
            if len(line) > 0:
                lengths.append(len(line))

        if not lengths:
            return 0

        lengths = list(set(lengths))
        total = sum(lengths)
        avg = total / len(lengths)
        max_line = avg * 2

        lengths = sorted(lengths)
        for i in range(len(lengths) - 1, -1, -1):
            if lengths[i] > max_line:
                del lengths[i]

        if percent > 1:
            percent = 1
        if percent < 0:
            percent = 0

        index = int(len(lengths) * percent) - 1

        return lengths[index]

    def line_histogram(self, percent):
        '''
        Creates a broad histogram of the document to determine whether it incorporates hard
        line breaks.  Lines are sorted into 20 'buckets' based on length.
        percent is the percentage of lines that should be in a single bucket to return true
        The majority of the lines will exist in 1-2 buckets in typical docs with hard line breaks
        '''
        minLineLength=20 # Ignore lines under 20 chars (typical of spaces)
        maxLineLength=1900 # Discard larger than this to stay in range
        buckets=20 # Each line is divided into a bucket based on length

        #print "there are "+str(len(lines))+" lines"
        #max = 0
        #for line in self.lines:
        #    l = len(line)
        #    if l > max:
        #        max = l
        #print "max line found is "+str(max)
        # Build the line length histogram
        hRaw = [ 0 for i in range(0,buckets) ]
        for line in self.lines:
            l = len(line)
            if l > minLineLength and l < maxLineLength:
                    l = int(l/100)
                    #print "adding "+str(l)
                    hRaw[l]+=1

        # Normalize the histogram into percents
        totalLines = len(self.lines)
        if totalLines > 0:
            h = [ float(count)/totalLines for count in hRaw ]
        else:
            h = []
        #print "\nhRaw histogram lengths are: "+str(hRaw)
        #print "              percents are: "+str(h)+"\n"

        # Find the biggest bucket
        maxValue = 0
        for i in range(0,len(h)):
            if h[i] > maxValue:
                maxValue = h[i]

        if maxValue < percent:
            #print "Line lengths are too variable. Not unwrapping."
            return False
        else:
            #print str(maxValue)+" of the lines were in one bucket"
            return True

class Dehyphenator(object):
    '''
    Analyzes words to determine whether hyphens should be retained/removed.  Uses the document
    itself is as a dictionary. This method handles all languages along with uncommon, made-up, and
    scientific words. The primary disadvantage is that words appearing only once in the document
    retain hyphens.
    '''

    def __init__(self, verbose=0, log=None):
        self.log = log
        self.verbose = verbose
        # Add common suffixes to the regex below to increase the likelihood of a match -
        # don't add suffixes which are also complete words, such as 'able' or 'sex'
        # only remove if it's not already the point of hyphenation
        self.suffix_string = "((ed)?ly|'?e?s||a?(t|s)?ion(s|al(ly)?)?|ings?|er|(i)?ous|(i|a)ty|(it)?ies|ive|gence|istic(ally)?|(e|a)nce|m?ents?|ism|ated|(e|u)ct(ed)?|ed|(i|ed)?ness|(e|a)ncy|ble|ier|al|ex|ian)$"
        self.suffixes = re.compile(r"^%s" % self.suffix_string, re.IGNORECASE)
        self.removesuffixes = re.compile(r"%s" % self.suffix_string, re.IGNORECASE)
        # remove prefixes if the prefix was not already the point of hyphenation
        self.prefix_string = '^(dis|re|un|in|ex)'
        self.prefixes = re.compile(r'%s$' % self.prefix_string, re.IGNORECASE)
        self.removeprefix = re.compile(r'%s' % self.prefix_string, re.IGNORECASE)

    def dehyphenate(self, match):
        firsthalf = match.group('firstpart')
        secondhalf = match.group('secondpart')
        try:
            wraptags = match.group('wraptags')
        except:
            wraptags = ''
        hyphenated = unicode(firsthalf) + "-" + unicode(secondhalf)
        dehyphenated = unicode(firsthalf) + unicode(secondhalf)
        if self.suffixes.match(secondhalf) is None:
            lookupword = self.removesuffixes.sub('', dehyphenated)
        else:
            lookupword = dehyphenated
        if len(firsthalf) > 4 and self.prefixes.match(firsthalf) is None:
            lookupword = self.removeprefix.sub('', lookupword)
        if self.verbose > 2:
            self.log("lookup word is: "+str(lookupword)+", orig is: " + str(hyphenated))
        try:
            searchresult = self.html.find(lookupword.lower())
        except:
            return hyphenated
        if self.format == 'html_cleanup' or self.format == 'txt_cleanup':
            if self.html.find(lookupword) != -1 or searchresult != -1:
                if self.verbose > 2:
                    self.log("    Cleanup:returned dehyphenated word: " + str(dehyphenated))
                return dehyphenated
            elif self.html.find(hyphenated) != -1:
                if self.verbose > 2:
                    self.log("        Cleanup:returned hyphenated word: " + str(hyphenated))
                return hyphenated
            else:
                if self.verbose > 2:
                    self.log("            Cleanup:returning original text "+str(firsthalf)+" + linefeed "+str(secondhalf))
                return firsthalf+u'\u2014'+wraptags+secondhalf

        else:
            if self.format == 'individual_words' and len(firsthalf) + len(secondhalf) <= 6:
                if self.verbose > 2:
                    self.log("too short, returned hyphenated word: " + str(hyphenated))
                return hyphenated
            if len(firsthalf) <= 2 and len(secondhalf) <= 2:
                if self.verbose > 2:
                    self.log("too short, returned hyphenated word: " + str(hyphenated))
                return hyphenated
            if self.html.find(lookupword) != -1 or searchresult != -1:
                if self.verbose > 2:
                    self.log("     returned dehyphenated word: " + str(dehyphenated))
                return dehyphenated
            else:
                if self.verbose > 2:
                    self.log("          returned hyphenated word: " + str(hyphenated))
                return hyphenated

    def __call__(self, html, format, length=1):
        self.html = html
        self.format = format
        if format == 'html':
            intextmatch = re.compile(u'(?<=.{%i})(?P<firstpart>[^\W\-]+)(-|‐)\s*(?=<)(?P<wraptags>(</span>)?\s*(</[iubp]>\s*){1,2}(?P<up2threeblanks><(p|div)[^>]*>\s*(<p[^>]*>\s*</p>\s*)?</(p|div)>\s+){0,3}\s*(<[iubp][^>]*>\s*){1,2}(<span[^>]*>)?)\s*(?P<secondpart>[\w\d]+)' % length)
        elif format == 'pdf':
            intextmatch = re.compile(u'(?<=.{%i})(?P<firstpart>[^\W\-]+)(-|‐)\s*(?P<wraptags><p>|</[iub]>\s*<p>\s*<[iub]>)\s*(?P<secondpart>[\w\d]+)'% length)
        elif format == 'txt':
            intextmatch = re.compile(u'(?<=.{%i})(?P<firstpart>[^\W\-]+)(-|‐)(\u0020|\u0009)*(?P<wraptags>(\n(\u0020|\u0009)*)+)(?P<secondpart>[\w\d]+)'% length)
        elif format == 'individual_words':
            intextmatch = re.compile(u'(?!<)(?P<firstpart>[^\W\-]+)(-|‐)\s*(?P<secondpart>\w+)(?![^<]*?>)')
        elif format == 'html_cleanup':
            intextmatch = re.compile(u'(?P<firstpart>[^\W\-]+)(-|‐)\s*(?=<)(?P<wraptags></span>\s*(</[iubp]>\s*<[iubp][^>]*>\s*)?<span[^>]*>|</[iubp]>\s*<[iubp][^>]*>)?\s*(?P<secondpart>[\w\d]+)')
        elif format == 'txt_cleanup':
            intextmatch = re.compile(u'(?P<firstpart>[^\W\-]+)(-|‐)(?P<wraptags>\s+)(?P<secondpart>[\w\d]+)')


        html = intextmatch.sub(self.dehyphenate, html)
        return html

class CSSPreProcessor(object):

    PAGE_PAT   = re.compile(r'@page[^{]*?{[^}]*?}')
    # Remove some of the broken CSS Microsoft products
    # create
    MS_PAT     = re.compile(r'''
        (?P<start>^|;|\{)\s*    # The end of the previous rule or block start
        (%s).+?                 # The invalid selectors
        (?P<end>$|;|\})         # The end of the declaration
        '''%'mso-|panose-|text-underline|tab-interval',
        re.MULTILINE|re.IGNORECASE|re.VERBOSE)

    def ms_sub(self, match):
        end = match.group('end')
        try:
            start = match.group('start')
        except:
            start = ''
        if end == ';':
            end = ''
        return start + end

    def __call__(self, data, add_namespace=False):
        from calibre.ebooks.oeb.base import XHTML_CSS_NAMESPACE
        data = self.PAGE_PAT.sub('', data)
        data = self.MS_PAT.sub(self.ms_sub, data)
        if not add_namespace:
            return data

        # Remove comments as the following namespace logic will break if there
        # are commented lines before the first @import or @charset rule. Since
        # the conversion will remove all stylesheets anyway, we don't lose
        # anything
        data = re.sub(ur'/\*.*?\*/', u'', data, flags=re.DOTALL)

        ans, namespaced = [], False
        for line in data.splitlines():
            ll = line.lstrip()
            if not (namespaced or ll.startswith('@import') or not ll or
                        ll.startswith('@charset')):
                ans.append(XHTML_CSS_NAMESPACE.strip())
                namespaced = True
            ans.append(line)

        return u'\n'.join(ans)

class HTMLPreProcessor(object):

    PREPROCESS = [
                  # Remove huge block of contiguous spaces as they slow down
                  # the following regexes pretty badly
                  (re.compile(r'\s{10000,}'), lambda m: ''),
                  # Some idiotic HTML generators (Frontpage I'm looking at you)
                  # Put all sorts of crap into <head>. This messes up lxml
                  (re.compile(r'<head[^>]*>\n*(.*?)\n*</head>', re.IGNORECASE|re.DOTALL),
                   sanitize_head),
                  # Convert all entities, since lxml doesn't handle them well
                  (re.compile(r'&(\S+?);'), convert_entities),
                  # Remove the <![if/endif tags inserted by everybody's darling, MS Word
                  (re.compile(r'</{0,1}!\[(end){0,1}if\]{0,1}>', re.IGNORECASE),
                   lambda match: ''),
                  ]

    # Fix pdftohtml markup
    PDFTOHTML  = [
                  # Fix umlauts
                  (re.compile(u'¨\s*(<br.*?>)*\s*a', re.UNICODE), lambda match: u'ä'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*A', re.UNICODE), lambda match: u'Ä'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*e', re.UNICODE), lambda match: u'ë'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*E', re.UNICODE), lambda match: u'Ë'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*i', re.UNICODE), lambda match: u'ï'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*I', re.UNICODE), lambda match: u'Ï'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*o', re.UNICODE), lambda match: u'ö'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*O', re.UNICODE), lambda match: u'Ö'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*u', re.UNICODE), lambda match: u'ü'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*U', re.UNICODE), lambda match: u'Ü'),

                  # Fix accents
                  # `
                  (re.compile(u'`\s*(<br.*?>)*\s*a', re.UNICODE), lambda match: u'à'),
                  (re.compile(u'`\s*(<br.*?>)*\s*A', re.UNICODE), lambda match: u'À'),
                  (re.compile(u'`\s*(<br.*?>)*\s*e', re.UNICODE), lambda match: u'è'),
                  (re.compile(u'`\s*(<br.*?>)*\s*E', re.UNICODE), lambda match: u'È'),
                  (re.compile(u'`\s*(<br.*?>)*\s*i', re.UNICODE), lambda match: u'ì'),
                  (re.compile(u'`\s*(<br.*?>)*\s*I', re.UNICODE), lambda match: u'Ì'),
                  (re.compile(u'`\s*(<br.*?>)*\s*o', re.UNICODE), lambda match: u'ò'),
                  (re.compile(u'`\s*(<br.*?>)*\s*O', re.UNICODE), lambda match: u'Ò'),
                  (re.compile(u'`\s*(<br.*?>)*\s*u', re.UNICODE), lambda match: u'ù'),
                  (re.compile(u'`\s*(<br.*?>)*\s*U', re.UNICODE), lambda match: u'Ù'),

                  # ` with letter before
                  (re.compile(u'a\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'à'),
                  (re.compile(u'A\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'À'),
                  (re.compile(u'e\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'è'),
                  (re.compile(u'E\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'È'),
                  (re.compile(u'i\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'ì'),
                  (re.compile(u'I\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'Ì'),
                  (re.compile(u'o\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'ò'),
                  (re.compile(u'O\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'Ò'),
                  (re.compile(u'u\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'ù'),
                  (re.compile(u'U\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'Ù'),

                  # ´
                  (re.compile(u'´\s*(<br.*?>)*\s*a', re.UNICODE), lambda match: u'á'),
                  (re.compile(u'´\s*(<br.*?>)*\s*A', re.UNICODE), lambda match: u'Á'),
                  (re.compile(u'´\s*(<br.*?>)*\s*c', re.UNICODE), lambda match: u'ć'),
                  (re.compile(u'´\s*(<br.*?>)*\s*C', re.UNICODE), lambda match: u'Ć'),
                  (re.compile(u'´\s*(<br.*?>)*\s*e', re.UNICODE), lambda match: u'é'),
                  (re.compile(u'´\s*(<br.*?>)*\s*E', re.UNICODE), lambda match: u'É'),
                  (re.compile(u'´\s*(<br.*?>)*\s*i', re.UNICODE), lambda match: u'í'),
                  (re.compile(u'´\s*(<br.*?>)*\s*I', re.UNICODE), lambda match: u'Í'),
                  (re.compile(u'´\s*(<br.*?>)*\s*l', re.UNICODE), lambda match: u'ĺ'),
                  (re.compile(u'´\s*(<br.*?>)*\s*L', re.UNICODE), lambda match: u'Ĺ'),
                  (re.compile(u'´\s*(<br.*?>)*\s*o', re.UNICODE), lambda match: u'ó'),
                  (re.compile(u'´\s*(<br.*?>)*\s*O', re.UNICODE), lambda match: u'Ó'),
                  (re.compile(u'´\s*(<br.*?>)*\s*n', re.UNICODE), lambda match: u'ń'),
                  (re.compile(u'´\s*(<br.*?>)*\s*N', re.UNICODE), lambda match: u'Ń'),
                  (re.compile(u'´\s*(<br.*?>)*\s*r', re.UNICODE), lambda match: u'ŕ'),
                  (re.compile(u'´\s*(<br.*?>)*\s*R', re.UNICODE), lambda match: u'Ŕ'),
                  (re.compile(u'´\s*(<br.*?>)*\s*s', re.UNICODE), lambda match: u'ś'),
                  (re.compile(u'´\s*(<br.*?>)*\s*S', re.UNICODE), lambda match: u'Ś'),
                  (re.compile(u'´\s*(<br.*?>)*\s*u', re.UNICODE), lambda match: u'ú'),
                  (re.compile(u'´\s*(<br.*?>)*\s*U', re.UNICODE), lambda match: u'Ú'),
                  (re.compile(u'´\s*(<br.*?>)*\s*z', re.UNICODE), lambda match: u'ź'),
                  (re.compile(u'´\s*(<br.*?>)*\s*Z', re.UNICODE), lambda match: u'Ź'),

                  # ˆ
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*a', re.UNICODE), lambda match: u'â'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*A', re.UNICODE), lambda match: u'Â'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*e', re.UNICODE), lambda match: u'ê'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*E', re.UNICODE), lambda match: u'Ê'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*i', re.UNICODE), lambda match: u'î'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*I', re.UNICODE), lambda match: u'Î'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*o', re.UNICODE), lambda match: u'ô'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*O', re.UNICODE), lambda match: u'Ô'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*u', re.UNICODE), lambda match: u'û'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*U', re.UNICODE), lambda match: u'Û'),

                  # ¸
                  (re.compile(u'¸\s*(<br.*?>)*\s*c', re.UNICODE), lambda match: u'ç'),
                  (re.compile(u'¸\s*(<br.*?>)*\s*C', re.UNICODE), lambda match: u'Ç'),

                  # ˛
                  (re.compile(u'\s*˛\s*(<br.*?>)*\s*a', re.UNICODE), lambda match: u'ą'),
                  (re.compile(u'\s*˛\s*(<br.*?>)*\s*A', re.UNICODE), lambda match: u'Ą'),
                  (re.compile(u'˛\s*(<br.*?>)*\s*e', re.UNICODE), lambda match: u'ę'),
                  (re.compile(u'˛\s*(<br.*?>)*\s*E', re.UNICODE), lambda match: u'Ę'),

                  # ˙
                  (re.compile(u'˙\s*(<br.*?>)*\s*z', re.UNICODE), lambda match: u'ż'),
                  (re.compile(u'˙\s*(<br.*?>)*\s*Z', re.UNICODE), lambda match: u'Ż'),

                  # ˇ
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*c', re.UNICODE), lambda match: u'č'),
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*C', re.UNICODE), lambda match: u'Č'),
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*d', re.UNICODE), lambda match: u'ď'),
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*D', re.UNICODE), lambda match: u'Ď'),
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*e', re.UNICODE), lambda match: u'ě'),
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*E', re.UNICODE), lambda match: u'Ě'),
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*l', re.UNICODE), lambda match: u'ľ'),
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*L', re.UNICODE), lambda match: u'Ľ'),
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*n', re.UNICODE), lambda match: u'ň'),
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*N', re.UNICODE), lambda match: u'Ň'),
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*r', re.UNICODE), lambda match: u'ř'),
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*R', re.UNICODE), lambda match: u'Ř'),
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*s', re.UNICODE), lambda match: u'š'),
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*S', re.UNICODE), lambda match: u'Š'),
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*t', re.UNICODE), lambda match: u'ť'),
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*T', re.UNICODE), lambda match: u'Ť'),
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*z', re.UNICODE), lambda match: u'ž'),
                  (re.compile(u'ˇ\s*(<br.*?>)*\s*Z', re.UNICODE), lambda match: u'Ž'),

                  # °
                  (re.compile(u'°\s*(<br.*?>)*\s*u', re.UNICODE), lambda match: u'ů'),
                  (re.compile(u'°\s*(<br.*?>)*\s*U', re.UNICODE), lambda match: u'Ů'),

                  # If pdf printed from a browser then the header/footer has a reliable pattern
                  (re.compile(r'((?<=</a>)\s*file:/{2,4}[A-Z].*<br>|file:////?[A-Z].*<br>(?=\s*<hr>))', re.IGNORECASE), lambda match: ''),

                  # Center separator lines
                  (re.compile(u'<br>\s*(?P<break>([*#•✦=] *){3,})\s*<br>'), lambda match: '<p>\n<p style="text-align:center">' + match.group('break') + '</p>'),

                  # Remove page links
                  (re.compile(r'<a name=\d+></a>', re.IGNORECASE), lambda match: ''),
                  # Remove <hr> tags
                  (re.compile(r'<hr.*?>', re.IGNORECASE), lambda match: ''),

                  # Remove gray background
                  (re.compile(r'<BODY[^<>]+>'), lambda match : '<BODY>'),

                  # Convert line breaks to paragraphs
                  (re.compile(r'<br[^>]*>\s*'), lambda match : '</p>\n<p>'),
                  (re.compile(r'<body[^>]*>\s*'), lambda match : '<body>\n<p>'),
                  (re.compile(r'\s*</body>'), lambda match : '</p>\n</body>'),

                  # Clean up spaces
                  (re.compile(u'(?<=[\.,;\?!”"\'])[\s^ ]*(?=<)'), lambda match: ' '),
                  # Add space before and after italics
                  (re.compile(u'(?<!“)<i>'), lambda match: ' <i>'),
                  (re.compile(r'</i>(?=\w)'), lambda match: '</i> '),
                 ]

    # Fix Book Designer markup
    BOOK_DESIGNER = [
                     # HR
                     (re.compile('<hr>', re.IGNORECASE),
                      lambda match : '<span style="page-break-after:always"> </span>'),
                     # Create header tags
                     (re.compile('<h2[^><]*?id=BookTitle[^><]*?(align=)*(?(1)(\w+))*[^><]*?>[^><]*?</h2>', re.IGNORECASE),
                      lambda match : '<h1 id="BookTitle" align="%s">%s</h1>'%(match.group(2) if match.group(2) else 'center', match.group(3))),
                     (re.compile('<h2[^><]*?id=BookAuthor[^><]*?(align=)*(?(1)(\w+))*[^><]*?>[^><]*?</h2>', re.IGNORECASE),
                      lambda match : '<h2 id="BookAuthor" align="%s">%s</h2>'%(match.group(2) if match.group(2) else 'center', match.group(3))),
                     (re.compile('<span[^><]*?id=title[^><]*?>(.*?)</span>', re.IGNORECASE|re.DOTALL),
                      lambda match : '<h2 class="title">%s</h2>'%(match.group(1),)),
                     (re.compile('<span[^><]*?id=subtitle[^><]*?>(.*?)</span>', re.IGNORECASE|re.DOTALL),
                      lambda match : '<h3 class="subtitle">%s</h3>'%(match.group(1),)),
                     ]
    def __init__(self, log=None, extra_opts=None):
        self.log = log
        self.extra_opts = extra_opts

    def is_baen(self, src):
        return re.compile(r'<meta\s+name="Publisher"\s+content=".*?Baen.*?"',
                          re.IGNORECASE).search(src) is not None

    def is_book_designer(self, raw):
        return re.search('<H2[^><]*id=BookTitle', raw) is not None

    def is_pdftohtml(self, src):
        return '<!-- created by calibre\'s pdftohtml -->' in src[:1000]

    def __call__(self, html, remove_special_chars=None,
            get_preprocess_html=False):
        if remove_special_chars is not None:
            html = remove_special_chars.sub('', html)
        html = html.replace('\0', '')
        is_pdftohtml = self.is_pdftohtml(html)
        if self.is_baen(html):
            rules = []
        elif self.is_book_designer(html):
            rules = self.BOOK_DESIGNER
        elif is_pdftohtml:
            rules = self.PDFTOHTML
        else:
            rules = []

        start_rules = []
        if is_pdftohtml:
            # Remove non breaking spaces
            start_rules.append((re.compile(ur'\u00a0'), lambda match : ' '))

        if not getattr(self.extra_opts, 'keep_ligatures', False):
            html = _ligpat.sub(lambda m:LIGATURES[m.group()], html)

        user_sr_rules = {}
        # Function for processing search and replace
        def do_search_replace(search_pattern, replace_txt):
            try:
                search_re = re.compile(search_pattern)
                if not replace_txt:
                    replace_txt = ''
                rules.insert(0, (search_re, replace_txt))
                user_sr_rules[(search_re, replace_txt)] = search_pattern
            except Exception as e:
                self.log.error('Failed to parse %r regexp because %s' %
                        (search, as_unicode(e)))

        # search / replace using the sr?_search / sr?_replace options
        for i in range(1, 4):
            search, replace = 'sr%d_search'%i, 'sr%d_replace'%i
            search_pattern = getattr(self.extra_opts, search, '')
            replace_txt = getattr(self.extra_opts, replace, '')
            if search_pattern:
                do_search_replace(search_pattern, replace_txt)

        # multi-search / replace using the search_replace option
        search_replace = getattr(self.extra_opts, 'search_replace', None)
        if search_replace:
            search_replace = json.loads(search_replace)
            for search_pattern, replace_txt in reversed(search_replace):
                do_search_replace(search_pattern, replace_txt)

        end_rules = []
        # delete soft hyphens - moved here so it's executed after header/footer removal
        if is_pdftohtml:
            # unwrap/delete soft hyphens
            end_rules.append((re.compile(u'[­](</p>\s*<p>\s*)+\s*(?=[[a-z\d])'), lambda match: ''))
            # unwrap/delete soft hyphens with formatting
            end_rules.append((re.compile(u'[­]\s*(</(i|u|b)>)+(</p>\s*<p>\s*)+\s*(<(i|u|b)>)+\s*(?=[[a-z\d])'), lambda match: ''))

        length = -1
        if getattr(self.extra_opts, 'unwrap_factor', 0.0) > 0.01:
            docanalysis = DocAnalysis('pdf', html)
            length = docanalysis.line_length(getattr(self.extra_opts, 'unwrap_factor'))
            if length:
                #print "The pdf line length returned is " + str(length)
                # unwrap em/en dashes
                end_rules.append((re.compile(u'(?<=.{%i}[–—])\s*<p>\s*(?=[[a-z\d])' % length), lambda match: ''))
                end_rules.append(
                    # Un wrap using punctuation
                    (re.compile(u'(?<=.{%i}([a-zäëïöüàèìòùáćéíĺóŕńśúýâêîôûçąężıãõñæøþðßěľščťžňďřů,:)\IA\u00DF]|(?<!\&\w{4});))\s*(?P<ital></(i|b|u)>)?\s*(</p>\s*<p>\s*)+\s*(?=(<(i|b|u)>)?\s*[\w\d$(])' % length, re.UNICODE), wrap_lines),
                )

        for rule in self.PREPROCESS + start_rules:
            html = rule[0].sub(rule[1], html)

        if get_preprocess_html:
            return html

        def dump(raw, where):
            import os
            dp = getattr(self.extra_opts, 'debug_pipeline', None)
            if dp and os.path.exists(dp):
                odir = os.path.join(dp, 'input')
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

        #dump(html, 'pre-preprocess')

        for rule in rules + end_rules:
            try:
                html = rule[0].sub(rule[1], html)
            except re.error as e:
                if rule in user_sr_rules:
                    self.log.error(
                        'User supplied search & replace rule: %s -> %s '
                        'failed with error: %s, ignoring.'%(
                            user_sr_rules[rule], rule[1], e))
                else:
                    raise

        if is_pdftohtml and length > -1:
            # Dehyphenate
            dehyphenator = Dehyphenator(self.extra_opts.verbose, self.log)
            html = dehyphenator(html,'html', length)

        if is_pdftohtml:
            from calibre.ebooks.conversion.utils import HeuristicProcessor
            pdf_markup = HeuristicProcessor(self.extra_opts, None)
            totalwords = 0
            if pdf_markup.get_word_count(html) > 7000:
                html = pdf_markup.markup_chapters(html, totalwords, True)

        #dump(html, 'post-preprocess')

        # Handle broken XHTML w/ SVG (ugh)
        if 'svg:' in html and SVG_NS not in html:
            html = html.replace(
                '<html', '<html xmlns:svg="%s"' % SVG_NS, 1)
        if 'xlink:' in html and XLINK_NS not in html:
            html = html.replace(
                '<html', '<html xmlns:xlink="%s"' % XLINK_NS, 1)

        html = XMLDECL_RE.sub('', html)

        if getattr(self.extra_opts, 'asciiize', False):
            from calibre.utils.localization import get_udc
            from calibre.utils.mreplace import MReplace
            unihandecoder = get_udc()
            mr = MReplace(data={u'«':u'&lt;'*3, u'»':u'&gt;'*3})
            html = mr.mreplace(html)
            html = unihandecoder.decode(html)

        if getattr(self.extra_opts, 'enable_heuristics', False):
            from calibre.ebooks.conversion.utils import HeuristicProcessor
            preprocessor = HeuristicProcessor(self.extra_opts, self.log)
            html = preprocessor(html)

        if getattr(self.extra_opts, 'smarten_punctuation', False):
            html = self.smarten_punctuation(html)

        try:
            unsupported_unicode_chars = self.extra_opts.output_profile.unsupported_unicode_chars
        except AttributeError:
            unsupported_unicode_chars = u''
        if unsupported_unicode_chars:
            from calibre.utils.localization import get_udc
            unihandecoder = get_udc()
            for char in unsupported_unicode_chars:
                asciichar = unihandecoder.decode(char)
                html = html.replace(char, asciichar)

        return html

    def smarten_punctuation(self, html):
        from calibre.utils.smartypants import smartyPants
        from calibre.ebooks.chardet import substitute_entites
        from calibre.ebooks.conversion.utils import HeuristicProcessor
        preprocessor = HeuristicProcessor(self.extra_opts, self.log)
        from uuid import uuid4
        start = 'calibre-smartypants-'+str(uuid4())
        stop = 'calibre-smartypants-'+str(uuid4())
        html = html.replace('<!--', start)
        html = html.replace('-->', stop)
        html = preprocessor.fix_nbsp_indents(html)
        html = smartyPants(html)
        html = html.replace(start, '<!--')
        html = html.replace(stop, '-->')
        # convert ellipsis to entities to prevent wrapping
        html = re.sub(r'(?u)(?<=\w)\s?(\.\s?){2}\.', '&hellip;', html)
        # convert double dashes to em-dash
        html = re.sub(r'\s--\s', u'\u2014', html)
        return substitute_entites(html)

