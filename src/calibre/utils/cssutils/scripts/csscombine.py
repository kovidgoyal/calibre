#!/usr/bin/env python
"""Combine sheets referred to by @import rules in a given CSS proxy sheet
into a single new sheet.

- proxy currently is a path (no URI!)
- in @import rules only relative paths do work for now but should be used
  anyway
- currently no nested @imports are resolved
- messages are send to stderr
- output to stdout.

Example::

    csscombine sheets\csscombine-proxy.css -m -t ascii -s utf-8
        1>combined.css 2>log.txt

results in log.txt::

    COMBINING sheets/csscombine-proxy.css
    USING SOURCE ENCODING: css
    * PROCESSING @import sheets\csscombine-1.css
    * PROCESSING @import sheets\csscombine-2.css
    INFO    Nested @imports are not combined: @import "1.css";
    SETTING TARGET ENCODING: ascii

and combined.css::

    @charset "ascii";@import"1.css";@namespaces2"uri";s2|sheet-1{top:1px}s2|sheet-2{top:2px}proxy{top:3px}

or without option -m::

    @charset "ascii";
    @import "1.css";
    @namespace s2 "uri";
    @namespace other "other";
    /* proxy sheet were imported sheets should be combined */
    /* non-ascii chars: \F6 \E4 \FC  */
    /* @import "csscombine-1.css"; */
    /* combined sheet 1 */
    s2|sheet-1 {
        top: 1px
        }
    /* @import url(csscombine-2.css); */
    /* combined sheet 2 */
    s2|sheet-2 {
        top: 2px
        }
    proxy {
        top: 3px
        }

TODO
    - URL or file hrefs? URI should be default
    - no nested @imports are resolved yet
    - maybe add a config file which is used?

"""
__all__ = ['csscombine']
__docformat__ = 'restructuredtext'
__version__ = '$Id: csscombine.py 1332 2008-07-09 13:12:56Z cthedot $'

import optparse
import sys
from cssutils.script import csscombine

def main(args=None):
    usage = "usage: %prog [options] path"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('-s', '--sourceencoding', action='store',
        dest='sourceencoding', 
        help='encoding of input, defaulting to "css". If given overwrites other encoding information like @charset declarations')
    parser.add_option('-t', '--targetencoding', action='store',
        dest='targetencoding',
        help='encoding of output, defaulting to "UTF-8"', default='utf-8')
    parser.add_option('-m', '--minify', action='store_true', dest='minify',
        default=False,
        help='saves minified version of combined files, defaults to False')
    options, path = parser.parse_args()

    if not path:
        parser.error('no path given')
    else:
        path = path[0]

    print csscombine(path, options.sourceencoding, options.targetencoding,
                     options.minify)


if __name__ == '__main__':
    sys.exit(main())