#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


'''
BASH completion for calibre commands that are too complex for simple
completion.
'''

import sys, os, shlex, glob, re
from functools import partial

from calibre import prints

debug = partial(prints, file=sys.stderr)

def split(src):
    try:
        return shlex.split(src)
    except ValueError:
        try:
            return shlex.split(src+'"')
        except ValueError:
            return shlex.split(src+"'")


def files_and_dirs(prefix, allowed_exts=[]):
    for i in glob.iglob(prefix+'*'):
        _, ext = os.path.splitext(i)
        ext = ext.lower().replace('.', '')
        if os.path.isdir(i):
            yield i+os.sep
        elif allowed_exts is None or ext in allowed_exts:
            yield i+' '

def get_opts_from_parser(parser, prefix):
    def do_opt(opt):
        for x in opt._long_opts:
            if x.startswith(prefix):
                yield x
        for x in opt._short_opts:
            if x.startswith(prefix):
                yield x
    for o in parser.option_list:
        for x in do_opt(o): yield x
    for g in parser.option_groups:
        for o in g.option_list:
            for x in do_opt(o): yield x

def send(ans):
    pat = re.compile('([^0-9a-zA-Z_./])')
    for x in sorted(set(ans)):
        x = pat.sub(lambda m : '\\'+m.group(1), x)
        if x.endswith('\\ '):
            x = x[:-2]+' '
        prints(x)



class EbookConvert(object):

    def __init__(self, comp_line, pos):
        words = split(comp_line[:pos])
        char_before = comp_line[pos-1]
        prefix = words[-1] if words[-1].endswith(char_before) else ''
        wc = len(words)
        if not prefix:
            wc += 1
        self.words = words
        self.prefix = prefix
        self.previous = words[-2 if prefix else -1]
        self.complete(wc)

    def complete(self, wc):
        if wc == 2:
            self.complete_input()
        elif wc == 3:
            self.complete_output()
        else:
            from calibre.ebooks.conversion.cli import create_option_parser
            from calibre.utils.logging import Log
            log = Log()
            log.outputs = []
            ans = []
            if not self.prefix or self.prefix.startswith('-'):
                try:
                    parser, _ = create_option_parser(self.words[:3], log)
                    ans += list(get_opts_from_parser(parser, self.prefix))
                except:
                    pass
            if self.previous.startswith('-'):
                ans += list(files_and_dirs(self.prefix, None))
            send(ans)

    def complete_input(self):
        from calibre.ebooks.conversion.plumber import supported_input_formats
        ans = list(files_and_dirs(self.prefix, supported_input_formats()))
        from calibre.web.feeds.recipes import recipes
        ans += [t.title+'.recipe ' for t in recipes if
                (t.title+'.recipe').startswith(self.prefix)]
        send(ans)

    def complete_output(self):
        from calibre.customize.ui import available_output_formats
        fmts = available_output_formats()
        ans = list(files_and_dirs(self.prefix, fmts))
        ans += ['.'+x+' ' for x in fmts if ('.'+x).startswith(self.prefix)]
        send(ans)






def main(args=sys.argv):
    comp_line, pos = os.environ['COMP_LINE'], int(os.environ['COMP_POINT'])
    module = split(comp_line)[0].split(os.sep)[-1]
    if module == 'ebook-convert':
        EbookConvert(comp_line, pos)

    return 0


if __name__ == '__main__':
    raise sys.exit(main())
