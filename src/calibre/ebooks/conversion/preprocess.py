#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json
import re
from math import ceil

from calibre import as_unicode
from calibre import xml_entity_to_unicode as convert_entities

XMLDECL_RE    = re.compile(r'^\s*<[?]xml.*?[?]>')
SVG_NS       = 'http://www.w3.org/2000/svg'
XLINK_NS     = 'http://www.w3.org/1999/xlink'

_span_pat = re.compile('<span.*?</span>', re.DOTALL|re.IGNORECASE)

LIGATURES = {
#        '\u00c6': 'AE',
#        '\u00e6': 'ae',
#        '\u0152': 'OE',
#        '\u0153': 'oe',
#        '\u0132': 'IJ',
#        '\u0133': 'ij',
#        '\u1D6B': 'ue',
        '\uFB00': 'ff',
        '\uFB01': 'fi',
        '\uFB02': 'fl',
        '\uFB03': 'ffi',
        '\uFB04': 'ffl',
        '\uFB05': 'ft',
        '\uFB06': 'st',
        }

_ligpat = re.compile('|'.join(LIGATURES))


def sanitize_head(match):
    x = match.group(1).strip()
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


def smarten_punctuation(html, log=None):
    from calibre.ebooks.chardet import substitute_entites
    from calibre.ebooks.conversion.utils import HeuristicProcessor
    from calibre.utils.smartypants import smartyPants
    preprocessor = HeuristicProcessor(log=log)
    from uuid import uuid4
    start = 'calibre-smartypants-'+str(uuid4())
    stop = 'calibre-smartypants-'+str(uuid4())
    html = html.replace('<!--', start)
    html = html.replace('-->', stop)
    html = preprocessor.fix_nbsp_indents(html)
    html = smartyPants(html)
    html = html.replace(start, '<!--')
    html = html.replace(stop, '-->')
    return substitute_entites(html)


class DocAnalysis:
    '''
    Provides various text analysis functions to determine how the document is structured.
    format is the type of document analysis will be done against.
    raw is the raw text to determine the line length to use for wrapping.
    Blank lines are excluded from analysis
    '''

    def __init__(self, format='html', raw=''):
        raw = raw.replace('&nbsp;', ' ')
        if format == 'html':
            linere = re.compile(r'(?<=<p)(?![^>]*>\s*</p>).*?(?=</p>)', re.DOTALL)
        elif format == 'pdf':
            linere = re.compile(r'(?<=<br>)(?!\s*<br>).*?(?=<br>)', re.DOTALL)
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
        ordered smallest to largest and does not include duplicates. 0.5 is the
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
        max_line = ceil(avg * 2)

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
        minLineLength=20  # Ignore lines under 20 chars (typical of spaces)
        maxLineLength=1900  # Discard larger than this to stay in range
        buckets=20  # Each line is divided into a bucket based on length

        # print("there are "+str(len(lines))+" lines")
        # max = 0
        # for line in self.lines:
        #    l = len(line)
        #    if l > max:
        #        max = l
        # print("max line found is "+str(max))
        # Build the line length histogram
        hRaw = [0 for i in range(0,buckets)]
        for line in self.lines:
            l = len(line)
            if l > minLineLength and l < maxLineLength:
                l = int(l // 100)
                # print("adding "+str(l))
                hRaw[l]+=1

        # Normalize the histogram into percents
        totalLines = len(self.lines)
        if totalLines > 0:
            h = [float(count)/totalLines for count in hRaw]
        else:
            h = []
        # print("\nhRaw histogram lengths are: "+str(hRaw))
        # print("              percents are: "+str(h)+"\n")

        # Find the biggest bucket
        maxValue = 0
        for i in range(0,len(h)):
            if h[i] > maxValue:
                maxValue = h[i]

        if maxValue < percent:
            # print("Line lengths are too variable. Not unwrapping.")
            return False
        else:
            # print(str(maxValue)+" of the lines were in one bucket")
            return True


class Dehyphenator:
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
        self.suffix_string = (
            "((ed)?ly|'?e?s||a?(t|s)?ion(s|al(ly)?)?|ings?|er|(i)?ous|"
            "(i|a)ty|(it)?ies|ive|gence|istic(ally)?|(e|a)nce|m?ents?|ism|ated|"
            "(e|u)ct(ed)?|ed|(i|ed)?ness|(e|a)ncy|ble|ier|al|ex|ian)$")
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
        hyphenated = str(firsthalf) + "-" + str(secondhalf)
        dehyphenated = str(firsthalf) + str(secondhalf)
        if self.suffixes.match(secondhalf) is None:
            lookupword = self.removesuffixes.sub('', dehyphenated)
        else:
            lookupword = dehyphenated
        if len(firsthalf) > 4 and self.prefixes.match(firsthalf) is None:
            lookupword = self.removeprefix.sub('', lookupword)
        if self.verbose > 2:
            self.log("lookup word is: "+lookupword+", orig is: " + hyphenated)
        try:
            searchresult = self.html.find(lookupword.lower())
        except:
            return hyphenated
        if self.format == 'html_cleanup' or self.format == 'txt_cleanup':
            if self.html.find(lookupword) != -1 or searchresult != -1:
                if self.verbose > 2:
                    self.log("    Cleanup:returned dehyphenated word: " + dehyphenated)
                return dehyphenated
            elif self.html.find(hyphenated) != -1:
                if self.verbose > 2:
                    self.log("        Cleanup:returned hyphenated word: " + hyphenated)
                return hyphenated
            else:
                if self.verbose > 2:
                    self.log("            Cleanup:returning original text "+firsthalf+" + linefeed "+secondhalf)
                return firsthalf+'\u2014'+wraptags+secondhalf

        else:
            if self.format == 'individual_words' and len(firsthalf) + len(secondhalf) <= 6:
                if self.verbose > 2:
                    self.log("too short, returned hyphenated word: " + hyphenated)
                return hyphenated
            if len(firsthalf) <= 2 and len(secondhalf) <= 2:
                if self.verbose > 2:
                    self.log("too short, returned hyphenated word: " + hyphenated)
                return hyphenated
            if self.html.find(lookupword) != -1 or searchresult != -1:
                if self.verbose > 2:
                    self.log("     returned dehyphenated word: " + dehyphenated)
                return dehyphenated
            else:
                if self.verbose > 2:
                    self.log("          returned hyphenated word: " + hyphenated)
                return hyphenated

    def __call__(self, html, format, length=1):
        self.html = html
        self.format = format
        if format == 'html':
            intextmatch = re.compile((
                r'(?<=.{%i})(?P<firstpart>[^\W\-]+)(-|‐)\s*(?=<)(?P<wraptags>(</span>)?'
                r'\s*(</[iubp]>\s*){1,2}(?P<up2threeblanks><(p|div)[^>]*>\s*(<p[^>]*>\s*</p>\s*)'
                r'?</(p|div)>\s+){0,3}\s*(<[iubp][^>]*>\s*){1,2}(<span[^>]*>)?)\s*(?P<secondpart>[\w\d]+)') % length)
        elif format == 'pdf':
            intextmatch = re.compile((
                r'(?<=.{%i})(?P<firstpart>[^\W\-]+)(-|‐)\s*(?P<wraptags><p>|'
                r'</[iub]>\s*<p>\s*<[iub]>)\s*(?P<secondpart>[\w\d]+)')% length)
        elif format == 'txt':
            intextmatch = re.compile(
                '(?<=.{%i})(?P<firstpart>[^\\W\\-]+)(-|‐)(\u0020|\u0009)*(?P<wraptags>(\n(\u0020|\u0009)*)+)(?P<secondpart>[\\w\\d]+)'% length)
        elif format == 'individual_words':
            intextmatch = re.compile(
                r'(?!<)(?P<firstpart>[^\W\-]+)(-|‐)\s*(?P<secondpart>\w+)(?![^<]*?>)', re.UNICODE)
        elif format == 'html_cleanup':
            intextmatch = re.compile(
                r'(?P<firstpart>[^\W\-]+)(-|‐)\s*(?=<)(?P<wraptags></span>\s*(</[iubp]>'
                r'\s*<[iubp][^>]*>\s*)?<span[^>]*>|</[iubp]>\s*<[iubp][^>]*>)?\s*(?P<secondpart>[\w\d]+)')
        elif format == 'txt_cleanup':
            intextmatch = re.compile(
                r'(?P<firstpart>[^\W\-]+)(-|‐)(?P<wraptags>\s+)(?P<secondpart>[\w\d]+)')

        html = intextmatch.sub(self.dehyphenate, html)
        return html


class CSSPreProcessor:

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
        data = self.MS_PAT.sub(self.ms_sub, data)
        if not add_namespace:
            return data

        # Remove comments as the following namespace logic will break if there
        # are commented lines before the first @import or @charset rule. Since
        # the conversion will remove all stylesheets anyway, we don't lose
        # anything
        data = re.sub(r'/\*.*?\*/', '', data, flags=re.DOTALL)

        ans, namespaced = [], False
        for line in data.splitlines():
            ll = line.lstrip()
            if not (namespaced or ll.startswith('@import') or not ll or
                        ll.startswith('@charset')):
                ans.append(XHTML_CSS_NAMESPACE.strip())
                namespaced = True
            ans.append(line)

        return '\n'.join(ans)


def accent_regex(accent_maps, letter_before=False):
    accent_cat = set()
    letters = set()

    for accent in tuple(accent_maps):
        accent_cat.add(accent)
        k, v = accent_maps[accent].split(':', 1)
        if len(k) != len(v):
            raise ValueError(f'Invalid mapping for: {k} -> {v}')
        accent_maps[accent] = lmap = dict(zip(k, v))
        letters |= set(lmap)

    if letter_before:
        args = ''.join(letters), ''.join(accent_cat)
        accent_group, letter_group = 2, 1
    else:
        args = ''.join(accent_cat), ''.join(letters)
        accent_group, letter_group = 1, 2

    pat = re.compile(r'([{}])\s*(?:<br[^>]*>){{0,1}}\s*([{}])'.format(*args), re.UNICODE)

    def sub(m):
        lmap = accent_maps[m.group(accent_group)]
        return lmap.get(m.group(letter_group)) or m.group()

    return pat, sub


def html_preprocess_rules():
    ans = getattr(html_preprocess_rules, 'ans', None)
    if ans is None:
        ans = html_preprocess_rules.ans = [
        # Remove huge block of contiguous spaces as they slow down
        # the following regexes pretty badly
        (re.compile(r'\s{10000,}'), ''),
        # Some idiotic HTML generators (Frontpage I'm looking at you)
        # Put all sorts of crap into <head>. This messes up lxml
        (re.compile(r'<head[^>]*>(.*?)</head>', re.IGNORECASE|re.DOTALL), sanitize_head),
        # Convert all entities, since lxml doesn't handle them well
        (re.compile(r'&(\S+?);'), convert_entities),
        # Remove the <![if/endif tags inserted by everybody's darling, MS Word
        (re.compile(r'</{0,1}!\[(end){0,1}if\]{0,1}>', re.IGNORECASE), ''),
    ]
    return ans


def pdftohtml_rules():
    ans = getattr(pdftohtml_rules, 'ans', None)
    if ans is None:
        ans = pdftohtml_rules.ans = [
        accent_regex({
            '¨': 'aAeEiIoOuU:äÄëËïÏöÖüÜ',
            '`': 'aAeEiIoOuU:àÀèÈìÌòÒùÙ',
            '´': 'aAcCeEiIlLoOnNrRsSuUzZ:áÁćĆéÉíÍĺĹóÓńŃŕŔśŚúÚźŹ',
            'ˆ': 'aAeEiIoOuU:âÂêÊîÎôÔûÛ',
            '¸': 'cC:çÇ',
            '˛': 'aAeE:ąĄęĘ',
            '˙': 'zZ:żŻ',
            'ˇ': 'cCdDeElLnNrRsStTzZ:čČďĎěĚľĽňŇřŘšŠťŤžŽ',
            '°': 'uU:ůŮ',
        }),

        accent_regex({'`': 'aAeEiIoOuU:àÀèÈìÌòÒùÙ'}, letter_before=True),

        # If pdf printed from a browser then the header/footer has a reliable pattern
        (re.compile(r'((?<=</a>)\s*file:/{2,4}[A-Z].*<br>|file:////?[A-Z].*<br>(?=\s*<hr>))', re.IGNORECASE), lambda match: ''),

        # Center separator lines
        (re.compile(r'<br>\s*(?P<break>([*#•✦=] *){3,})\s*<br>'), lambda match: '<p>\n<p style="text-align:center">' + match.group('break') + '</p>'),

        # Remove <hr> tags
        (re.compile(r'<hr.*?>', re.IGNORECASE), ''),

        # Remove gray background
        (re.compile(r'<BODY[^<>]+>'), '<BODY>'),

        # Convert line breaks to paragraphs
        (re.compile(r'<br[^>]*>\s*'), '</p>\n<p>'),
        (re.compile(r'<body[^>]*>\s*'), '<body>\n<p>'),
        (re.compile(r'\s*</body>'), '</p>\n</body>'),

        # Clean up spaces
        (re.compile(r'(?<=[\.,;\?!”"\'])[\s^ ]*(?=<)'), ' '),
        # Add space before and after italics
        (re.compile(r'(?<!“)<i>'), ' <i>'),
        (re.compile(r'</i>(?=\w)'), '</i> '),
    ]
    return ans


def book_designer_rules():
    ans = getattr(book_designer_rules, 'ans', None)
    if ans is None:
        ans = book_designer_rules.ans = [
        # HR
        (re.compile('<hr>', re.IGNORECASE),
        lambda match : '<span style="page-break-after:always"> </span>'),
        # Create header tags
        (re.compile(r'<h2[^><]*?id=BookTitle[^><]*?(align=)*(?(1)(\w+))*[^><]*?>[^><]*?</h2>', re.IGNORECASE),
        lambda match : '<h1 id="BookTitle" align="%s">%s</h1>'%(match.group(2) if match.group(2) else 'center', match.group(3))),
        (re.compile(r'<h2[^><]*?id=BookAuthor[^><]*?(align=)*(?(1)(\w+))*[^><]*?>[^><]*?</h2>', re.IGNORECASE),
        lambda match : '<h2 id="BookAuthor" align="%s">%s</h2>'%(match.group(2) if match.group(2) else 'center', match.group(3))),
        (re.compile('<span[^><]*?id=title[^><]*?>(.*?)</span>', re.IGNORECASE|re.DOTALL),
        lambda match : '<h2 class="title">%s</h2>'%(match.group(1),)),
        (re.compile('<span[^><]*?id=subtitle[^><]*?>(.*?)</span>', re.IGNORECASE|re.DOTALL),
        lambda match : '<h3 class="subtitle">%s</h3>'%(match.group(1),)),
    ]
    return ans


class HTMLPreProcessor:

    def __init__(self, log=None, extra_opts=None, regex_wizard_callback=None):
        self.log = log
        self.extra_opts = extra_opts
        self.regex_wizard_callback = regex_wizard_callback
        self.current_href = None

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
            rules = book_designer_rules()
        elif is_pdftohtml:
            rules = pdftohtml_rules()
        else:
            rules = []

        start_rules = []

        if not getattr(self.extra_opts, 'keep_ligatures', False):
            html = _ligpat.sub(lambda m:LIGATURES[m.group()], html)

        user_sr_rules = {}
        # Function for processing search and replace

        def do_search_replace(search_pattern, replace_txt):
            from calibre.ebooks.conversion.search_replace import compile_regular_expression
            try:
                search_re = compile_regular_expression(search_pattern)
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
            end_rules.append((re.compile(
                r'[­](</p>\s*<p>\s*)+\s*(?=[\[a-z\d])'), lambda match: ''))
            # unwrap/delete soft hyphens with formatting
            end_rules.append((re.compile(
                r'[­]\s*(</(i|u|b)>)+(</p>\s*<p>\s*)+\s*(<(i|u|b)>)+\s*(?=[\[a-z\d])'), lambda match: ''))

        length = -1
        if getattr(self.extra_opts, 'unwrap_factor', 0.0) > 0.01:
            docanalysis = DocAnalysis('pdf', html)
            length = docanalysis.line_length(getattr(self.extra_opts, 'unwrap_factor'))
            if length:
                # print("The pdf line length returned is " + str(length))
                # unwrap em/en dashes
                end_rules.append((re.compile(
                    r'(?<=.{%i}[–—])\s*<p>\s*(?=[\[a-z\d])' % length), lambda match: ''))
                end_rules.append(
                    # Un wrap using punctuation
                    (re.compile((
                        r'(?<=.{%i}([a-zäëïöüàèìòùáćéíĺóŕńśúýâêîôûçąężıãõñæøþðßěľščťžňďřů,:)\\IAß]'
                        r'|(?<!\&\w{4});))\s*(?P<ital></(i|b|u)>)?\s*(</p>\s*<p>\s*)+\s*(?=(<(i|b|u)>)?'
                        r'\s*[\w\d$(])') % length, re.UNICODE), wrap_lines),
                )

        for rule in html_preprocess_rules() + start_rules:
            html = rule[0].sub(rule[1], html)

        if self.regex_wizard_callback is not None:
            self.regex_wizard_callback(self.current_href, html)

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

        # dump(html, 'pre-preprocess')

        for rule in rules + end_rules:
            try:
                html = rule[0].sub(rule[1], html)
            except Exception as e:
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

        # dump(html, 'post-preprocess')

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
            mr = MReplace(data={'«':'&lt;'*3, '»':'&gt;'*3})
            html = mr.mreplace(html)
            html = unihandecoder.decode(html)

        if getattr(self.extra_opts, 'enable_heuristics', False):
            from calibre.ebooks.conversion.utils import HeuristicProcessor
            preprocessor = HeuristicProcessor(self.extra_opts, self.log)
            html = preprocessor(html)

        if is_pdftohtml:
            html = html.replace('<!-- created by calibre\'s pdftohtml -->', '')

        if getattr(self.extra_opts, 'smarten_punctuation', False):
            html = smarten_punctuation(html, self.log)

        try:
            unsupported_unicode_chars = self.extra_opts.output_profile.unsupported_unicode_chars
        except AttributeError:
            unsupported_unicode_chars = ''
        if unsupported_unicode_chars:
            from calibre.utils.localization import get_udc
            unihandecoder = get_udc()
            for char in unsupported_unicode_chars:
                asciichar = unihandecoder.decode(char)
                html = html.replace(char, asciichar)

        return html
