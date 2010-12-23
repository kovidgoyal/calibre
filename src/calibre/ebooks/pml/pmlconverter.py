# -*- coding: utf-8 -*-

'''
Convert pml markup to and from html
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os
import re
import StringIO

from calibre import my_unichr, prepare_string_for_xml
from calibre.ebooks.metadata.toc import TOC

class PML_HTMLizer(object):

    STATES = [
        'i',
        'u',
        'd',
        'b',
        'sp',
        'sb',
        'h1',
        'h2',
        'h3',
        'h4',
        'h5',
        'h6',
        'a',
        'ra',
        'c',
        'r',
        't',
        's',
        'l',
        'k',
        'T',
        'FN',
        'SB',
    ]

    STATES_VALUE_REQ = [
        'a',
        'T',
        'FN',
        'SB',
    ]

    STATES_VALUE_REQ_2 = [
        'ra',
    ]

    STATES_CLOSE_VALUE_REQ = [
        'FN',
        'SB',
    ]

    STATES_TAGS = {
        'h1': ('<h1 style="page-break-before: always;">', '</h1>'),
        'h2': ('<h2>', '</h2>'),
        'h3': ('<h3>', '</h3>'),
        'h4': ('<h4>', '</h4>'),
        'h5': ('<h5>', '</h5>'),
        'h6': ('<h6>', '</h6>'),
        'sp': ('<sup>', '</sup>'),
        'sb': ('<sub>', '</sub>'),
        'a': ('<a href="#%s">', '</a>'),
        'ra': ('<span id="r%s"></span><a href="#%s">', '</a>'),
        'c': ('<div style="text-align: center; margin: auto;">', '</div>'),
        'r': ('<div style="text-align: right;">', '</div>'),
        't': ('<div style="margin-left: 5%;">', '</div>'),
        'T': ('<div style="margin-left: %s;">', '</div>'),
        'i': ('<span style="font-style: italic;">', '</span>'),
        'u': ('<span style="text-decoration: underline;">', '</span>'),
        'd': ('<span style="text-decoration: line-through;">', '</span>'),
        'b': ('<span style="font-weight: bold;">', '</span>'),
        'l': ('<span style="font-size: 150%;">', '</span>'),
        'k': ('<span style="font-size: 75%; font-variant: small-caps;">', '</span>'),
        'FN': ('<br /><br style="page-break-after: always;" /><div id="fn-%s"><p>', '</p><<small><a href="#rfn-%s">return</a></small></div>'),
        'SB': ('<br /><br style="page-break-after: always;" /><div id="sb-%s"><p>', '</p><small><a href="#rsb-%s">return</a></small></div>'),
    }

    CODE_STATES = {
        'q': 'a',
        'x': 'h1',
        'X0': 'h2',
        'X1': 'h3',
        'X2': 'h4',
        'X3': 'h5',
        'X4': 'h6',
        'Sp': 'sp',
        'Sb': 'sb',
        'c': 'c',
        'r': 'r',
        't': 't',
        'T': 'T',
        'i': 'i',
        'I': 'i',
        'u': 'u',
        'o': 'd',
        'b': 'b',
        'B': 'b',
        'l': 'l',
        'k': 'k',
        'Fn': 'ra',
        'Sd': 'ra',
        'FN': 'FN',
        'SB': 'SB',
    }

    LINK_STATES = [
        'a',
        'ra',
    ]

    BLOCK_STATES = [
        'a',
        'ra',
        'h1',
        'h2',
        'h3',
        'h4',
        'h5',
        'h6',
        'sb',
        'sp',
    ]

    DIV_STATES = [
        'c',
        'r',
        't',
        'T',
        'FN',
        'SB',
    ]

    SPAN_STATES = [
        'l',
        'k',
        'i',
        'u',
        'd',
        'b',
    ]

    def __init__(self):
        self.state = {}
        self.toc = TOC()
        self.file_name = ''

    def prepare_pml(self, pml):
        # Give Chapters the form \\*='text'text\\*. This is used for generating
        # the TOC later.
        pml = re.sub(r'(?<=\\x)(?P<text>.*?)(?=\\x)', lambda match: '="%s"%s' % (self.strip_pml(match.group('text')), match.group('text')), pml)
        pml = re.sub(r'(?<=\\X[0-4])(?P<text>.*?)(?=\\X[0-4])', lambda match: '="%s"%s' % (self.strip_pml(match.group('text')), match.group('text')), pml)

        # Remove comments
        pml = re.sub(r'(?mus)\\v(?P<text>.*?)\\v', '', pml)

        # Remove extra white spaces.
        pml = re.sub(r'(?mus)[ ]{2,}', ' ', pml)
        pml = re.sub(r'(?mus)^[ ]*(?=.)', '', pml)
        pml = re.sub(r'(?mus)(?<=.)[ ]*$', '', pml)
        pml = re.sub(r'(?mus)^[ ]*$', '', pml)

        # Footnotes and Sidebars.
        pml = re.sub(r'(?mus)<footnote\s+id="(?P<target>.+?)">\s*(?P<text>.*?)\s*</footnote>', lambda match: '\\FN="%s"%s\\FN' % (match.group('target'), match.group('text')) if match.group('text') else '', pml)
        pml = re.sub(r'(?mus)<sidebar\s+id="(?P<target>.+?)">\s*(?P<text>.*?)\s*</sidebar>', lambda match: '\\SB="%s"%s\\SB' % (match.group('target'), match.group('text')) if match.group('text') else '', pml)

        # Convert &'s into entities so &amp; in the text doesn't get turned into
        # &. It will display as &amp;
        pml = pml.replace('&', '&amp;')

        # Replace \\a and \\U with either the unicode character or the entity.
        pml = re.sub(r'\\a(?P<num>\d{3})', lambda match: '&#%s;' % match.group('num'), pml)
        pml = re.sub(r'\\U(?P<num>[0-9a-f]{4})', lambda match: '%s' % my_unichr(int(match.group('num'), 16)), pml)

        pml = prepare_string_for_xml(pml)

        return pml

    def strip_pml(self, pml):
        pml = re.sub(r'\\C\d=".*"', '', pml)
        pml = re.sub(r'\\Fn=".*"', '', pml)
        pml = re.sub(r'\\Sd=".*"', '', pml)
        pml = re.sub(r'\\.=".*"', '', pml)
        pml = re.sub(r'\\X\d', '', pml)
        pml = re.sub(r'\\S[pbd]', '', pml)
        pml = re.sub(r'\\Fn', '', pml)
        pml = re.sub(r'\\a\d\d\d', '', pml)
        pml = re.sub(r'\\U\d\d\d\d', '', pml)
        pml = re.sub(r'\\.', '', pml)
        pml.replace('\r\n', ' ')
        pml.replace('\n', ' ')
        pml.replace('\r', ' ')

        return pml

    def cleanup_html(self, html):
        old = html
        html = self.cleanup_html_remove_redundant(html)
        while html != old:
            old = html
            html = self.cleanup_html_remove_redundant(html)
        html = re.sub(r'(?imu)^\s*', '', html)
        return html

    def cleanup_html_remove_redundant(self, html):
        for key in self.STATES_TAGS.keys():
            open, close = self.STATES_TAGS[key]
            if key in self.STATES_VALUE_REQ:
                html = re.sub(r'(?u)%s\s*%s' % (open % '.*?', close), '', html)
            else:
                html = re.sub(r'(?u)%s\s*%s' % (open, close), '', html)
        html = re.sub(r'(?imu)<p>\s*</p>', '', html)
        return html

    def start_line(self):
        start = u''

        div = []
        span = []
        other = []

        for key, val in self.state.items():
            if val[0]:
                if key in self.DIV_STATES:
                    div.append((key, val[1]))
                elif key in self.SPAN_STATES:
                    span.append((key, val[1]))
                else:
                    other.append((key, val[1]))

        for key, val in other+div+span:
            if key in self.STATES_VALUE_REQ:
                start += self.STATES_TAGS[key][0] % val
            elif key in self.STATES_VALUE_REQ_2:
                start += self.STATES_TAGS[key][0] % (val, val)
            else:
                start += self.STATES_TAGS[key][0]

        return u'<p>%s' % start

    def end_line(self):
        end = u''

        div = []
        span = []
        other = []

        for key, val in self.state.items():
            if val[0]:
                if key == 'T':
                    self.state['T'][0] = False
                if key in self.DIV_STATES:
                    div.append(key)
                elif key in self.SPAN_STATES:
                    span.append(key)
                else:
                    other.append(key)
        for key in span+div+other:
            if key in self.STATES_CLOSE_VALUE_REQ:
                end += self.STATES_TAGS[key][1] % self.state[key][1]
            else:
                end += self.STATES_TAGS[key][1]

        return u'%s</p>' % end

    def process_code(self, code, stream, pre=''):
        text = u''

        code = self.CODE_STATES.get(code, None)
        if not code:
            return text

        if code in self.DIV_STATES:
            # Ignore multilple T's on the same line. They do not have a closing
            # code. They get closed at the end of the line.
            if code == 'T' and self.state['T'][0]:
                self.code_value(stream)
                return text
            text = self.process_code_div(code, stream)
        elif code in self.SPAN_STATES:
            text = self.process_code_span(code, stream)
        elif code in self.BLOCK_STATES:
            text = self.process_code_block(code, stream, pre)
        else:
            text = self.process_code_simple(code, stream)

        self.state[code][0] = not self.state[code][0]

        return text

    def process_code_simple(self, code, stream):
        text = u''

        if self.state[code][0]:
            if code in self.STATES_CLOSE_VALUE_REQ:
                text = self.STATES_TAGS[code][1] % self.state[code][1]
            else:
                text = self.STATES_TAGS[code][1]
        else:
            if code in self.STATES_VALUE_REQ or code in self.STATES_VALUE_REQ_2:
                val = self.code_value(stream)
                if code in self.STATES_VALUE_REQ:
                    text = self.STATES_TAGS[code][0] % val
                else:
                    text = self.STATES_TAGS[code][0] % (val, val)
                self.state[code][1] = val
            else:
                text = self.STATES_TAGS[code][0]

        return text

    def process_code_div(self, code, stream):
        text = u''

        # Close code.
        if self.state[code][0]:
            # Close all.
            for c in self.SPAN_STATES+self.DIV_STATES:
                if self.state[c][0]:
                    if c in self.STATES_CLOSE_VALUE_REQ:
                        text += self.STATES_TAGS[c][1] % self.state[c][1]
                    else:
                        text += self.STATES_TAGS[c][1]
            # Reopen the based on state.
            for c in self.DIV_STATES+self.SPAN_STATES:
                if code == c:
                    continue
                if self.state[c][0]:
                    if c in self.STATES_VALUE_REQ:
                        text += self.STATES_TAGS[self.CODE_STATES[c]][0] % self.state[c][1]
                    elif c in self.STATES_VALUE_REQ_2:
                        text += self.STATES_TAGS[self.CODE_STATES[c]][0] % (self.state[c][1], self.state[c][1])
                    else:
                        text += self.STATES_TAGS[c][0]
        # Open code.
        else:
            # Close all spans.
            for c in self.SPAN_STATES:
                if self.state[c][0]:
                    if c in self.STATES_CLOSE_VALUE_REQ:
                        text += self.STATES_TAGS[c][1] % self.state[c][1]
                    else:
                        text += self.STATES_TAGS[c][1]
            # Process the code
            if code in self.STATES_VALUE_REQ or code in self.STATES_VALUE_REQ_2:
                val = self.code_value(stream)
                if code in self.STATES_VALUE_REQ:
                    text += self.STATES_TAGS[code][0] % val
                else:
                    text += self.STATES_TAGS[code][0] % (val, val)
                self.state[code][1] = val
            else:
                text += self.STATES_TAGS[code][0]
            # Re-open all spans based on state
            for c in self.SPAN_STATES:
                if self.state[c][0]:
                    if c in self.STATES_VALUE_REQ:
                        text += self.STATES_TAGS[self.CODE_STATES[c]][0] % self.state[c][1]
                    elif c in self.STATES_VALUE_REQ_2:
                        text += self.STATES_TAGS[self.CODE_STATES[c]][0] % (self.state[c][1], self.state[c][1])
                    else:
                        text += self.STATES_TAGS[c][0]

        return text

    def process_code_span(self, code, stream):
        text = u''

        # Close code.
        if self.state[code][0]:
            # Close all spans
            for c in self.SPAN_STATES:
                if self.state[c][0]:
                    if c in self.STATES_CLOSE_VALUE_REQ:
                        text += self.STATES_TAGS[c][1] % self.state[c][1]
                    else:
                        text += self.STATES_TAGS[c][1]
            # Re-open the spans based on state except for code which will be
            # left closed.
            for c in self.SPAN_STATES:
                if code == c:
                    continue
                if self.state[c][0]:
                    if c in self.STATES_VALUE_REQ:
                        text += self.STATES_TAGS[code][0] % self.state[c][1]
                    elif c in self.STATES_VALUE_REQ_2:
                        text += self.STATES_TAGS[code][0] % (self.state[c][1], self.state[c][1])
                    else:
                        text += self.STATES_TAGS[c][0]
        # Open code.
        else:
            if code in self.STATES_VALUE_REQ or code in self.STATES_VALUE_REQ_2:
                val = self.code_value(stream)
                if code in self.STATES_VALUE_REQ:
                    text += self.STATES_TAGS[code][0] % val
                else:
                    text += self.STATES_TAGS[code][0] % (val, val)
                self.state[code][1] = val
            else:
                text += self.STATES_TAGS[code][0]

        return text

    def process_code_block(self, code, stream, pre=''):
        text = u''

        # Close all spans
        for c in self.SPAN_STATES:
            if self.state[c][0]:
                if c in self.STATES_CLOSE_VALUE_REQ:
                    text += self.STATES_TAGS[c][1] % self.state[c][1]
                else:
                    text += self.STATES_TAGS[c][1]
        # Process the code
        if self.state[code][0]:
            # Close tag
            if code in self.STATES_CLOSE_VALUE_REQ:
                text += self.STATES_TAGS[code][1] % self.state[code][1]
            else:
                text += self.STATES_TAGS[code][1]
        else:
            # Open tag
            if code in self.STATES_VALUE_REQ or code in self.STATES_VALUE_REQ_2:
                val = self.code_value(stream)
                if code in self.LINK_STATES:
                    val = val.lstrip('#')
                if pre:
                    val = '%s-%s' % (pre, val)
                if code in self.STATES_VALUE_REQ:
                    text += self.STATES_TAGS[code][0] % val
                else:
                    text += self.STATES_TAGS[code][0] % (val, val)
                self.state[code][1] = val
            else:
                text += self.STATES_TAGS[code][0]

        # Re-open all spans if code was a div based on state
        for c in self.SPAN_STATES:
            if self.state[c][0]:
                if c in self.STATES_VALUE_REQ:
                    text += self.STATES_TAGS[code][0] % self.state[c][1]
                elif c in self.STATES_VALUE_REQ_2:
                    text += self.STATES_TAGS[code][0] % (self.state[c][1], self.state[c][1])
                else:
                    text += self.STATES_TAGS[c][0]

        return text

    def code_value(self, stream):
        value = u''
        # state 0 is before =
        # state 1 is before the first "
        # state 2 is before the second "
        # state 3 is after the second "
        state = 0
        loc = stream.tell()

        c = stream.read(1)
        while c != '':
            if state == 0:
                if c == '=':
                    state = 1
                elif c != ' ':
                    # A code that requires an argument should have = after the
                    # code but sometimes has spaces. If it has anything other
                    # than a space or = after the code then we can assume the
                    # markup is invalid. We will stop looking for the value
                    # and continue to hopefully not lose any data.
                    break
            elif state == 1:
                if c == '"':
                    state = 2
                elif c != ' ':
                    # " should always follow = but we will allow for blank
                    # space after the =.
                    break
            elif state == 2:
                if c == '"':
                    state = 3
                    break
                else:
                    value += c
            c = stream.read(1)

        if state != 3:
            # Unable to complete the sequence to reterieve the value. Reset
            # the stream to the location it started.
            stream.seek(loc)
            value = u''

        return value.strip()

    def parse_pml(self, pml, file_name=''):
        pml = self.prepare_pml(pml)
        output = []

        self.state = {}
        self.toc = TOC()
        self.file_name = file_name

        for s in self.STATES:
            self.state[s] = [False, ''];

        for line in pml.splitlines():
            if not line:
                continue

            parsed = []
            empty = True

            # Must use StringIO, cStringIO does not support unicode
            line = StringIO.StringIO(line)
            parsed.append(self.start_line())

            c = line.read(1)
            while c != '':
                text = u''

                if c == '\\':
                    c = line.read(1)

                    if c in 'qcrtTiIuobBlk':
                        text = self.process_code(c, line)
                    elif c in 'FS':
                        l = line.read(1)
                        if '%s%s' % (c, l) == 'Fn':
                            text = self.process_code('Fn', line, 'fn')
                        elif '%s%s' % (c, l) == 'FN':
                            text = self.process_code('FN', line)
                        elif '%s%s' % (c, l) == 'SB':
                            text = self.process_code('SB', line)
                        elif '%s%s' % (c, l) == 'Sd':
                            text = self.process_code('Sd', line, 'sb')
                    elif c in 'xXC':
                        empty = False
                        # The PML was modified eariler so x and X put the text
                        # inside of ="" so we don't have do special processing
                        # for C.
                        t = ''
                        if c in 'XC':
                            level = line.read(1)
                        id = 'pml_toc-%s' % len(self.toc)
                        value = self.code_value(line)
                        if c == 'x':
                            t = self.process_code(c, line)
                        elif c == 'X':
                            t = self.process_code('%s%s' % (c, level), line)
                        if not value or value == '':
                            text = t
                        else:
                            self.toc.add_item(os.path.basename(self.file_name), id, value)
                            text = '%s<span id="%s"></span>' % (t, id)
                    elif c == 'm':
                        empty = False
                        src = self.code_value(line)
                        text = '<img src="images/%s" />' % src
                    elif c == 'Q':
                        empty = False
                        id = self.code_value(line)
                        text = '<span id="%s"></span>' % id
                    elif c == 'p':
                        empty = False
                        text = '<br /><br style="page-break-after: always;" />'
                    elif c == 'n':
                        pass
                    elif c == 'w':
                        empty = False
                        text = '<hr width="%s" />' % self.code_value(line)
                    elif c == '-':
                        empty = False
                        text = '&shy;'
                    elif c == '\\':
                        empty = False
                        text = '\\'
                else:
                    if c != ' ':
                        empty = False
                    text = c
                parsed.append(text)
                c = line.read(1)

            if not empty:
                text = self.end_line()
                parsed.append(text)
                output.append(u''.join(parsed))
            line.close()

        output = self.cleanup_html(u'\n'.join(output))

        return output

    def get_toc(self):
        return self.toc


def pml_to_html(pml):
    hizer = PML_HTMLizer()
    return hizer.parse_pml(pml)

def footnote_sidebar_to_html(pre_id, id, pml):
    id = id.strip('\x01')
    html = '<br /><br style="page-break-after: always;" /><div id="%s-%s"><p>%s</p><small><a href="#r%s-%s">return</a></small></div>' % (pre_id, id, pml_to_html(pml), pre_id, id)
    return html

def footnote_to_html(id, pml):
    return footnote_sidebar_to_html('fn', id, pml)

def sidebar_to_html(id, pml):
    return footnote_sidebar_to_html('sb', id, pml)
