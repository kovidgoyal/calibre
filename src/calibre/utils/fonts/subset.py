#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from future_builtins import map

class NoGlyphs(ValueError):
    pass

def load_sfntly():
    from calibre.constants import plugins
    sfntly, err = plugins['sfntly']
    if err:
        raise RuntimeError('Failed to load sfntly: %s'%err)
    return sfntly

def subset(font_data, individual_chars, ranges):
    if font_data[:4] not in {b'\x00\x01\x00\x00', b'OTTO', b'true', b'typ1'}:
        raise ValueError('Not a supported font file. sfnt_version not recognized: %r'%
                font_data[:4])
    individual = tuple(sorted(map(ord, individual_chars)))
    cranges = []
    for s, e in ranges:
        sc, ec = map(ord, (s, e))
        if ec <= sc:
            raise ValueError('The start character %s is after the end'
                    ' character %s'%(s, e))
        cranges.append((sc, ec))
    sfntly = load_sfntly()
    try:
        return sfntly.subset(font_data, individual, tuple(cranges))
    except sfntly.NoGlyphs:
        raise NoGlyphs('No glyphs were found in this font for the'
                ' specified characters. Subsetting is pointless')

def option_parser():
    import textwrap
    from calibre.utils.config import OptionParser
    parser = OptionParser(usage=textwrap.dedent('''\
            %prog [options] input_font_file output_font_file characters_to_keep

            Subset the specified font, keeping only the glyphs for the characters in
            characters_to_keep. characters_to_keep is a comma separated list of characters of
            the form: a,b,c,A-Z,0-9,xyz

            You can specify ranges in the list of characters, as shown above.
            '''))
    parser.add_option('-c', '--codes', default=False, action='store_true',
            help='If specified, the list of characters is interpreted as '
            'numeric unicode codes instead of characters. So to specify the '
            'characters a,b you would use 97,98')
    parser.prog = 'subset-font'
    return parser

def print_stats(old_stats, new_stats):
    from calibre import prints
    prints('========= Table comparison (original vs. subset) =========')
    prints('Table', ' ', '%10s'%'Size', '  ', 'Percent', '   ', '%10s'%'New Size',
            ' New Percent')
    prints('='*80)
    old_total = sum(old_stats.itervalues())
    new_total = sum(new_stats.itervalues())
    tables = sorted(old_stats.iterkeys(), key=lambda x:old_stats[x],
            reverse=True)
    for table in tables:
        osz = old_stats[table]
        op = osz/old_total * 100
        nsz = new_stats.get(table, 0)
        np = nsz/new_total * 100
        suffix = ' | same size'
        if nsz != osz:
            suffix = ' | reduced to %.1f %%'%(nsz/osz * 100)
        prints('%4s'%table, '  ', '%10s'%osz, '  ', '%5.1f %%'%op, '   ',
                '%10s'%nsz, '  ', '%5.1f %%'%np, suffix)
    prints('='*80)

def test_mem():
    load_sfntly()
    from calibre.utils.mem import memory
    import gc
    gc.collect()
    start_mem = memory()
    raw = P('fonts/liberation/LiberationSerif-Regular.ttf', data=True)
    calls = 1000
    for i in xrange(calls):
        subset(raw, (), (('a', 'z'),))
    del raw
    for i in xrange(3): gc.collect()
    print ('Leaked memory per call:', (memory() - start_mem)/calls*1024, 'KB')


def main(args):
    import sys, time
    from calibre import prints
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) < 4 or len(args) > 4:
        parser.print_help()
        raise SystemExit(1)
    iff, off, chars = args[1:]
    with open(iff, 'rb') as f:
        orig = f.read()

    chars = [x.strip() for x in chars.split(',')]
    individual, ranges = set(), set()

    def not_single(c):
        if len(c) > 1:
            prints(c, 'is not a single character', file=sys.stderr)
            raise SystemExit(1)

    for c in chars:
        if '-' in c:
            parts = [x.strip() for x in c.split('-')]
            if len(parts) != 2:
                prints('Invalid range:', c, file=sys.stderr)
                raise SystemExit(1)
            if opts.codes:
                parts = tuple(map(unichr, map(int, parts)))
            map(not_single, parts)
            ranges.add(tuple(parts))
        else:
            if opts.codes:
                c = unichr(int(c))
            not_single(c)
            individual.add(c)
    st = time.time()
    sf, old_stats, new_stats = subset(orig, individual, ranges)
    taken = time.time() - st
    reduced = (len(sf)/len(orig)) * 100
    def sz(x):
        return '%gKB'%(len(x)/1024.)
    print_stats(old_stats, new_stats)
    prints('Original size:', sz(orig), 'Subset size:', sz(sf), 'Reduced to: %g%%'%(reduced))
    prints('Subsetting took %g seconds'%taken)
    with open(off, 'wb') as f:
        f.write(sf)
    prints('Subset font written to:', off)

if __name__ == '__main__':
    try:
        import init_calibre
        init_calibre
    except ImportError:
        pass
    import sys
    main(sys.argv)


