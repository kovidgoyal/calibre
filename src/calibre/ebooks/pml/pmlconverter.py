# -*- coding: utf-8 -*-

'''
Convert pml markup to and from html
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re
import StringIO

from calibre import my_unichr, prepare_string_for_xml
from calibre.ebooks.pdb.ereader import image_name

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
        'c',
        'r',
        't',
        's',
        'l',
        'T',
        'Fn',
        'Sd',
        'FS'
    ]

    STATES_VALUE_REQ = [
        'a',
        'T',
        'FS'
    ]

    STATES_TAGS = {
        'h1': ('<h1 style="page-break-after: always;">', '</h1>'),
        'h2': ('<h2>', '</h2>'),
        'h3': ('<h3>', '</h3>'),
        'h4': ('<h4>', '</h4>'),
        'h5': ('<h5>', '</h5>'),
        'h6': ('<h6>', '</h6>'),
        'sp': ('<sup>', '</sup>'),
        'sb': ('<sub>', '</sub>'),
        'a': ('<a href="%s">', '</a>'),
        'c': ('<div style="text-align: center; margin: auto;">', '</div>'),
        'r': ('<div style="text-align: right;">', '</div>'),
        't': ('<div style="margin-left: 5%;">', '</div>'),
        'T': ('<div style="margin-left: %s;">', '</div>'),
        'i': ('<span style="font-style : italic;">', '</span>'),
        'u': ('<span style="text-decoration : underline;">', '</span>'),
        'd': ('<span style="text-decoration: line-through;">', '</span>'),
        'b': ('<span style="font-weight: bold;">', '</span>'),
        's': ('<span style="font-size: 75%">', '</span>'),
        'l': ('<span style="font-size: 125%">', '</span>'),
        'FS': ('<div id="%s">', '</div>'),
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
        's': 's',
        'l': 'l',
        'Fn': 'a',
        'Sd': 'a',
        'FN': 'FS',
        'SB': 'FS',
    }

    DIV_STATES = [
        'c',
        'r',
        't',
        'T',
        'FS',
    ]

    SPAN_STATES = [
        's',
        'l',
        'i',
        'u',
        'd',
        'b',
    ]

    def __init__(self, close_all):
        self.close_all = close_all
        self.state = {}

    def prepare_pml(self, pml):
        # Remove comments
        pml = re.sub(r'(?mus)\\v(?P<text>.*?)\\v', '', pml)
        # Footnotes and Sidebars
        pml = re.sub(r'(?mus)<footnote\s+id="(?P<target>.+?)">\s*(?P<text>.*?)\s*</footnote>', lambda match: '\\FN="fns-%s"%s\\FN' % (match.group('target'), match.group('text')) if match.group('text') else '', pml)
        pml = re.sub(r'(?mus)<sidebar\s+id="(?P<target>.+?)">\s*(?P<text>.*?)\s*</sidebar>', lambda match: '\\SB="fns-%s"%s\\SB' % (match.group('target'), match.group('text')) if match.group('text') else '', pml)

        pml = prepare_string_for_xml(pml)

        pml = re.sub(r'\\a(?P<num>\d{3})', lambda match: '&#%s;' % match.group('num'), pml)
        pml = re.sub(r'\\U(?P<num>[0-9a-f]{4})', lambda match: '%s' % my_unichr(int(match.group('num'), 16)), pml)

        return pml

    def prepare_line(self, line):
        line = re.sub(r'[ ]{2,}', ' ', line)
        line = re.sub(r'^[ ]*(?=.)', '', line)
        line = re.sub(r'(?<=.)[ ]*$', '', line)
        line = re.sub(r'^[ ]*$', '', line)

        return line

    def start_line(self):
        start = u''

        for key, val in self.state.items():
            if val[0]:
                if key not in self.STATES_VALUE_REQ:
                    start += self.STATES_TAGS[key][0]
                else:
                    start += self.STATES_TAGS[key][0] % val[1]

        return u'<p>%s' % start

    def end_line(self):
        end = u''

        for key, val in self.state.items():
            if val[0]:
                if key == 'T':
                    self.state['T'][0] = False
                end += self.STATES_TAGS[key][1]

        return u'%s</p>' % end

    def process_code_simple(self, code):
        if code not in self.CODE_STATES.keys():
            return u''

        text = u''

        if self.state[self.CODE_STATES[code]][0]:
            text = self.STATES_TAGS[self.CODE_STATES[code]][1]
        else:
            text = self.STATES_TAGS[self.CODE_STATES[code]][0]

        self.state[self.CODE_STATES[code]][0] = not self.state[self.CODE_STATES[code]][0]

        return text

    def process_code_link(self, stream, pre=''):
        text = u''

        href = self.code_value(stream)
        if pre:
            href = '#%s-%s' % (pre, href)

        if self.state['a'][0]:
            text = self.STATES_TAGS['a'][1]
        else:
            text = self.STATES_TAGS['a'][0] % href
            self.state['a'][1] = href

        self.state['a'][0] = not self.state['a'][0]

        return text

    def process_code_div_span(self, code, stream):
        if self.close_all:
            return self.process_code_div_span_call(code, stream)
        else:
            return self.process_code_div_span_ind(code, stream)

    def process_code_div_span_ind(self, code, stream):
        text = u''
        ds = []

        code = self.CODE_STATES[code]

        if code in self.DIV_STATES:
            ds = self.DIV_STATES[:]
        elif code in self.SPAN_STATES:
            ds = self.SPAN_STATES[:]

        if self.state[code][0]:
            # Close all.
            for c in ds:
                if self.state[c][0]:
                    text += self.STATES_TAGS[c][1]
            # Reopen the based on state.
            del ds[ds.index(code)]
            for c in ds:
                if self.state[c][0]:
                    if c in self.STATES_VALUE_REQ:
                        text += self.STATES_TAGS[self.CODE_STATES[c]][0] % self.state[c][1]
                    else:
                        text += self.STATES_TAGS[c][0]
        else:
            if code in self.STATES_VALUE_REQ:
                val = self.code_value(stream)
                text = self.STATES_TAGS[code][0] % val
                self.state[code][1] = val
            else:
                text = self.STATES_TAGS[code][0]

        self.state[code][0] = not self.state[code][0]

        return text

    def process_code_div_span_call(self, code, stream):
        text = u''
        divs = self.DIV_STATES[:]
        spans = self.SPAN_STATES[:]

        code = self.CODE_STATES[code]

        if self.state[code][0]:
            # Close all divs then spans.
            for c in spans+divs:
                if self.state[c][0]:
                    text += self.STATES_TAGS[c][1]
            # Reopen the based on state. Open divs then spans
            if code in self.DIV_STATES:
                del divs[divs.index(code)]
            if code in self.SPAN_STATES:
                del spans[spans.index(code)]
            for c in divs+spans:
                if self.state[c][0]:
                    if c in self.STATES_VALUE_REQ:
                        text += self.STATES_TAGS[self.CODE_STATES[c]][0] % self.state[c][1]
                    else:
                        text += self.STATES_TAGS[c][0]
        else:
            if code in self.STATES_VALUE_REQ:
                val = self.code_value(stream)
                text = self.STATES_TAGS[code][0] % val
                self.state[code][1] = val
            else:
                text = self.STATES_TAGS[code][0]

        self.state[code][0] = not self.state[code][0]

        return text

    def code_value(self, stream):
        value = u''
        open = False

        c = stream.read(1)
        while c != '':
            if open and c != '"':
                value += c
            if c == '"':
                if not open:
                    open = True
                else:
                    break
            c = stream.read(1)

        return value.strip()

    def parse_pml(self, pml):
        pml = self.prepare_pml(pml)
        output = []

        self.state = {}
        for s in self.STATES:
            self.state[s] = [False, ''];

        for line in pml.splitlines():
            if not line:
                continue
            parsed = []
            empty = True

            # Must use StringIO, cStringIO does not support unicode
            line = StringIO.StringIO(self.prepare_line(line))
            parsed.append(self.start_line())

            c = line.read(1)
            while c != '':
                text = u''

                if c == '\\':
                    c = line.read(1)

                    if c == 'x':
                        text = self.process_code_simple(c)
                    elif c in 'XS':
                        l = line.read(1)
                        if '%s%s' % (c, l) == 'Sd':
                            text = self.process_code_link(line, 'fns')
                        elif '%s%s' % (c, l) == 'SB':
                            text = self.process_code_div_span('SB', line)
                        else:
                            text = self.process_code_simple('%s%s' % (c, l))
                    elif c == 'q':
                        text = self.process_code_link(line)
                    elif c in 'crtTiIuobB':
                        text = self.process_code_div_span(c, line)
                    elif c in 'sl':
                        close = u''
                        if c == 's' and self.state['l']:
                            close = self.process_code_div_span('l', line)
                        if c == 'l' and self.state['s']:
                            close = self.process_code_div_span('s', line)
                        text = self.process_code_div_span(c, line)
                        text = close+text
                    elif c == 'm':
                        empty = False
                        src = self.code_value(line)
                        text = '<img src="images/%s" />' % image_name(src).strip('\x00')
                    elif c == 'Q':
                        empty = False
                        id = self.code_value(line)
                        text = '<span id="%s"></span>' % id
                    elif c == 'p':
                        empty = False
                        text = '<br /><br style="page-break-after: always;" />'
                    elif c == 'C':
                        # This should be made to create a TOC entry
                        line.read(1)
                        self.code_value(line)
                    elif c == 'n':
                        pass
                    elif c == 'F':
                        l = line.read(1)
                        if '%s%s' % (c, l) == 'Fn':
                            text = self.process_code_link(line, 'fns')
                        elif '%s%s' % (c, l) == 'FN':
                            text = self.process_code_div_span('FN', line)
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

        return u'\n'.join(output)


def pml_to_html(pml, close_all=False):
    '''
    close_all will close div all div and span tags when one is closed and then
    re-open the appropriate ones.
    '''

    hizer = PML_HTMLizer(close_all)
    return hizer.parse_pml(pml)

def footnote_sidebar_to_html(id, pml):
    if id.startswith('\x01'):
        id = id[2:]
    html = '<div id="fns-%s"><dt>%s</dt></div><dd>%s</dd>' % (id, id, pml_to_html(pml))
    return html
