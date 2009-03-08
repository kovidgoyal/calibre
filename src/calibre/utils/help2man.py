from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time, bz2

from calibre.constants import __version__, __appname__, __author__


def create_man_page(prog, parser):
    usage  = parser.usage.splitlines()
    for i, line in enumerate(list(usage)):
        if not line.strip():
            usage[i] = '.PP'
        else:
            usage[i] = line.replace('%prog', prog)
    lines = [
             '.TH ' + prog.upper() + ' "1" ' + time.strftime('"%B %Y"') + 
             ' "%s (%s %s)" "%s"'%(prog, __appname__, __version__, __appname__),
             '.SH NAME',
             prog + r' \- part of '+__appname__,
             '.SH SYNOPSIS',
             '.B "%s"'%prog + r'\fR '+' '.join(usage[0].split()[1:]),
             '.SH DESCRIPTION',
             ]
    lines += usage[1:]
    
    lines += [
              '.SH OPTIONS'
              ]
    def format_option(opt):
        ans = ['.TP']
        opts = []
        opts += opt._short_opts
        opts.append(opt.get_opt_string())
        opts = [r'\fB'+x.replace('-', r'\-')+r'\fR' for x in opts]
        ans.append(', '.join(opts))
        help = opt.help if opt.help else ''
        ans.append(help.replace('%prog', prog).replace('%default', str(opt.default)))
        return ans
    
    for opt in parser.option_list:
        lines.extend(format_option(opt))
    for group in parser.option_groups:
        lines.append('.SS '+group.title)
        for opt in group.option_list:
            lines.extend(format_option(opt))
    
    lines += ['.SH SEE ALSO', 
              'The User Manual is available at '
              'http://calibre.kovidgoyal.net/user_manual',
              '.PP', '.B Created by '+__author__]
    
    return  bz2.compress('\n'.join(lines))

def main():
    from calibre.ebooks.epub.from_any import option_parser
    open('/tmp/any2epub.1calibre.bz2', 'w').write(create_man_page(
                                                'any2epub', option_parser()))
    
if __name__ == '__main__':
    main()