#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from collections import OrderedDict
from operator import itemgetter

from calibre.utils.fonts.sfnt.container import Sfnt
from calibre.utils.fonts.sfnt.errors import UnsupportedFont, NoGlyphs

# TrueType outlines {{{

def resolve_glyphs(loca, glyf, character_map):
    unresolved_glyphs = set(character_map.itervalues())
    unresolved_glyphs.add(0) # We always want the .notdef glyph
    resolved_glyphs = {}

    while unresolved_glyphs:
        glyph_id = unresolved_glyphs.pop()
        try:
            offset, length = loca.glyph_location(glyph_id)
        except (IndexError, ValueError, KeyError, TypeError):
            continue
        if length < 1:
            continue
        glyph = glyf.glyph_data(offset, length)
        if len(glyph) == 0:
            continue
        resolved_glyphs[glyph_id] = glyph
        for gid in glyph.glyph_indices:
            if gid not in resolved_glyphs:
                unresolved_glyphs.add(gid)

    return OrderedDict(sorted(resolved_glyphs.iteritems(), key=itemgetter(0)))

def subset_truetype(sfnt, character_map):
    loca = sfnt[b'loca']
    glyf = sfnt[b'glyf']

    try:
        head, maxp = sfnt[b'head'], sfnt[b'maxp']
    except KeyError:
        raise UnsupportedFont('This font does not contain head and/or maxp tables')
    loca.load_offsets(head, maxp)

    resolved_glyphs = resolve_glyphs(loca, glyf, character_map)
    if not resolved_glyphs or set(resolved_glyphs) == {0}:
        raise NoGlyphs('This font has no glyphs for the specified character '
                'set, subsetting it is pointless')

    # Keep only character codes that have resolved glyphs
    for code, glyph_id in tuple(character_map.iteritems()):
        if glyph_id not in resolved_glyphs:
            del character_map[code]

    # Update the glyf table
    glyph_offset_map = glyf.update(resolved_glyphs)

    # Update the loca table
    loca.subset(glyph_offset_map)

# }}}

def subset_postscript(sfnt, character_map):
    cff = sfnt[b'CFF ']
    cff.decompile()
    cff.subset(character_map)

def subset(raw, individual_chars, ranges=()):
    chars = list(map(ord, individual_chars))
    for r in ranges:
        chars += list(xrange(ord(r[0]), ord(r[1])+1))

    sfnt = Sfnt(raw)
    old_sizes = sfnt.sizes()

    # Remove the Digital Signature table since it is useless in a subset
    # font anyway
    sfnt.pop(b'DSIG', None)

    try:
        cmap = sfnt[b'cmap']
    except KeyError:
        raise UnsupportedFont('This font has no cmap table')

    # Get mapping of chars to glyph ids for all specified chars
    character_map = cmap.get_character_map(chars)

    if b'loca' in sfnt and b'glyf' in sfnt:
        # TrueType Outlines
        subset_truetype(sfnt, character_map)
    elif b'CFF ' in sfnt:
        # PostScript Outlines
        from calibre.utils.config_base import tweaks
        if tweaks['subset_cff_table']:
            subset_postscript(sfnt, character_map)
        else:
            raise UnsupportedFont('This font contains PostScript outlines, '
                'subsetting not supported')
    else:
        raise UnsupportedFont('This font does not contain TrueType '
                'or PostScript outlines')

    # Restrict the cmap table to only contain entries for the resolved glyphs
    cmap.set_character_map(character_map)

    raw, new_sizes = sfnt()
    return raw, old_sizes, new_sizes

# CLI {{{
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
# }}}

# Tests {{{
def test_mem():
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

def test():
    raw = P('fonts/liberation/LiberationSerif-Regular.ttf', data=True)
    sf, old_stats, new_stats = subset(raw, set(('a', 'b', 'c')), ())
    if len(sf) > 0.3 * len(raw):
        raise Exception('Subsetting failed')

def all():
    from calibre.utils.fonts.scanner import font_scanner
    failed = []
    unsupported = []
    total = 0
    for family in font_scanner.find_font_families():
        for font in font_scanner.fonts_for_family(family):
            raw = font_scanner.get_font_data(font)
            print ('Subsetting', font['full_name'], end='\t')
            total += 1
            try:
                sf, old_stats, new_stats = subset(raw, set(('a', 'b', 'c')), ())
            except NoGlyphs:
                print('No glyphs!')
                continue
            except UnsupportedFont as e:
                unsupported.append((font['full_name'], font['path'], unicode(e)))
                print ('Unsupported!')
                continue
            except Exception as e:
                print ('Failed!')
                failed.append((font['full_name'], font['path'], unicode(e)))
            else:
                print ('Reduced to:', '%.1f'%(
                        sum(new_stats.itervalues())/sum(old_stats.itervalues())
                        * 100), '%')
    if unsupported:
        print ('\n\nUnsupported:')
        for name, path, err in unsupported:
            print (name, path, err)
            print()
    if failed:
        print ('\n\nFailures:')
        for name, path, err in failed:
            print (name, path, err)
            print()

    print('Total:', total, 'Unsupported:', len(unsupported), 'Failed:',
            len(failed))


# }}}


