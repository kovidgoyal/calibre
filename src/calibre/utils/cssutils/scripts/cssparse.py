#!/usr/bin/env python
"""utility script to parse given filenames or string
"""
__docformat__ = 'restructuredtext'
__version__ = '$Id: cssparse.py 1327 2008-07-08 21:17:12Z cthedot $'

import cssutils
import logging
import optparse
import sys

def main(args=None):
    """
    Parses given filename(s) or string (using optional encoding) and prints
    the parsed style sheet to stdout.

    Redirect stdout to save CSS. Redirect stderr to save parser log infos.
    """
    usage = """usage: %prog [options] filename1.css [filename2.css ...]
        [>filename_combined.css] [2>parserinfo.log] """
    p = optparse.OptionParser(usage=usage)
    p.add_option('-e', '--encoding', action='store', dest='encoding',
        help='encoding of the file')
    p.add_option('-d', '--debug', action='store_true', dest='debug',
        help='activate debugging output')
    p.add_option('-m', '--minify', action='store_true', dest='minify',
        help='minify parsed CSS', default=False)
    p.add_option('-s', '--string', action='store_true', dest='string',
        help='parse given string')

    (options, params) = p.parse_args(args)

    if not params:
        p.error("no filename given")

    if options.debug:
        p = cssutils.CSSParser(loglevel=logging.DEBUG)
    else:
        p = cssutils.CSSParser()

    if options.minify:
        cssutils.ser.prefs.useMinified()

    if options.string:
        sheet = p.parseString(u''.join(params), encoding=options.encoding)
        print sheet.cssText
        print
        sys.stderr.write('\n')
    else:
        for filename in params:
            sys.stderr.write('=== CSS FILE: "%s" ===\n' % filename)
            sheet = p.parseFile(filename, encoding=options.encoding)
            print sheet.cssText
            print
            sys.stderr.write('\n')


if __name__ == "__main__":
 	sys.exit(main())
