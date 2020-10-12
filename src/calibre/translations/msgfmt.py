#! /usr/bin/env python
# vim:fileencoding=utf-8
# Written by Martin v. Löwis <loewis@informatik.hu-berlin.de>


"""Generate binary message catalog from textual translation description.

This program converts a textual Uniforum-style message catalog (.po file) into
a binary GNU catalog (.mo file).  This is essentially the same function as the
GNU msgfmt program, however, it is a simpler implementation.  Currently it
does not handle plural forms but it does handle message contexts.

Usage: msgfmt.py [OPTIONS] filename.po

Options:
    -o file
    --output-file=file
        Specify the output file to write to.  If omitted, output will go to a
        file named filename.mo (based off the input file name).

    -h
    --help
        Print this message and exit.

    -V
    --version
        Display version information and exit.
"""

import os
import sys
import ast
import getopt
import struct
import array
from email.parser import HeaderParser

__version__ = "1.2"

MESSAGES = {}
STATS = {'translated': 0, 'untranslated': 0}


def usage(code, msg=''):
    print(__doc__, file=sys.stderr)
    if msg:
        print(msg, file=sys.stderr)
    sys.exit(code)


def add(ctxt, id, str, fuzzy):
    "Add a non-fuzzy translation to the dictionary."
    if not fuzzy and str:
        if id:
            STATS['translated'] += 1
        if ctxt is None:
            MESSAGES[id] = str
        else:
            MESSAGES[b"%b\x04%b" % (ctxt, id)] = str
    else:
        if id:
            STATS['untranslated'] += 1


def generate():
    "Return the generated output."
    # the keys are sorted in the .mo file
    keys = sorted(MESSAGES.keys())
    offsets = []
    ids = strs = b''
    for id in keys:
        # For each string, we need size and file offset.  Each string is NUL
        # terminated; the NUL does not count into the size.
        offsets.append((len(ids), len(id), len(strs), len(MESSAGES[id])))
        ids += id + b'\0'
        strs += MESSAGES[id] + b'\0'
    output = ''
    # The header is 7 32-bit unsigned integers.  We don't use hash tables, so
    # the keys start right after the index tables.
    # translated string.
    keystart = 7*4+16*len(keys)
    # and the values start after the keys
    valuestart = keystart + len(ids)
    koffsets = []
    voffsets = []
    # The string table first has the list of keys, then the list of values.
    # Each entry has first the size of the string, then the file offset.
    for o1, l1, o2, l2 in offsets:
        koffsets += [l1, o1+keystart]
        voffsets += [l2, o2+valuestart]
    offsets = koffsets + voffsets
    output = struct.pack("Iiiiiii",
                         0x950412de,       # Magic
                         0,                 # Version
                         len(keys),         # # of entries
                         7*4,               # start of key index
                         7*4+len(keys)*8,   # start of value index
                         0, 0)              # size and offset of hash table
    try:
        output += array.array("i", offsets).tobytes()
    except AttributeError:
        output += array.array("i", offsets).tostring()
    output += ids
    output += strs
    return output


def make(filename, outfile):
    ID = 1
    STR = 2
    CTXT = 3
    unicode_prefix = 'u' if sys.version_info.major < 3 else ''

    # Compute .mo name from .po name and arguments
    if filename.endswith('.po'):
        infile = filename
    else:
        infile = filename + '.po'
    if outfile is None:
        outfile = os.path.splitext(infile)[0] + '.mo'

    try:
        with open(infile, 'rb') as f:
            lines = f.readlines()
    except IOError as msg:
        print(msg, file=sys.stderr)
        sys.exit(1)

    section = msgctxt = None
    fuzzy = 0
    msgid = msgstr = b''

    # Start off assuming Latin-1, so everything decodes without failure,
    # until we know the exact encoding
    encoding = 'latin-1'

    # Parse the catalog
    lno = 0
    for l in lines:
        l = l.decode(encoding)
        lno += 1
        # If we get a comment line after a msgstr, this is a new entry
        if l[0] == '#' and section == STR:
            add(msgctxt, msgid, msgstr, fuzzy)
            section = msgctxt = None
            fuzzy = 0
        # Record a fuzzy mark
        if l[:2] == '#,' and 'fuzzy' in l:
            fuzzy = 1
        # Skip comments
        if l[0] == '#':
            continue
        # Now we are in a msgid or msgctxt section, output previous section
        if l.startswith('msgctxt'):
            if section == STR:
                add(msgctxt, msgid, msgstr, fuzzy)
            section = CTXT
            l = l[7:]
            msgctxt = b''
        elif l.startswith('msgid') and not l.startswith('msgid_plural'):
            if section == STR:
                add(msgctxt, msgid, msgstr, fuzzy)
                if not msgid:
                    # See whether there is an encoding declaration
                    p = HeaderParser()
                    if sys.version_info.major > 2:
                        charset = p.parsestr(msgstr.decode(encoding)).get_content_charset()
                    else:
                        charset = p.parsestr(msgstr.decode(encoding).encode('ascii', 'replace')).get_content_charset()
                        if isinstance(charset, bytes):
                            charset = charset.decode('ascii')
                    if charset:
                        encoding = charset
            section = ID
            l = l[5:]
            msgid = msgstr = b''
            is_plural = False
        # This is a message with plural forms
        elif l.startswith('msgid_plural'):
            if section != ID:
                print('msgid_plural not preceded by msgid on %s:%d' % (infile, lno),
                      file=sys.stderr)
                sys.exit(1)
            l = l[12:]
            msgid += b'\0'  # separator of singular and plural
            is_plural = True
        # Now we are in a msgstr section
        elif l.startswith('msgstr'):
            section = STR
            if l.startswith('msgstr['):
                if not is_plural:
                    print('plural without msgid_plural on %s:%d' % (infile, lno),
                          file=sys.stderr)
                    sys.exit(1)
                l = l.split(']', 1)[1]
                if msgstr:
                    msgstr += b'\0'  # Separator of the various plural forms
            else:
                if is_plural:
                    print('indexed msgstr required for plural on  %s:%d' % (infile, lno),
                          file=sys.stderr)
                    sys.exit(1)
                l = l[6:]
        # Skip empty lines
        l = l.strip()
        if not l:
            continue
        l = ast.literal_eval(unicode_prefix + l)
        lb = l.encode(encoding)
        if section == CTXT:
            msgctxt += lb
        elif section == ID:
            msgid += lb
        elif section == STR:
            msgstr += lb
        else:
            print('Syntax error on %s:%d' % (infile, lno),
                  'before:', file=sys.stderr)
            print(l, file=sys.stderr)
            sys.exit(1)
    # Add last entry
    if section == STR:
        add(msgctxt, msgid, msgstr, fuzzy)

    # Compute output
    output = generate()
    try:
        if hasattr(outfile, 'write'):
            outfile.write(output)
        else:
            with open(outfile, "wb") as f:
                f.write(output)
    except IOError as msg:
        print(msg, file=sys.stderr)


def make_with_stats(filename, outfile):
    MESSAGES.clear()
    STATS['translated'] = STATS['untranslated'] = 0
    make(filename, outfile)
    return STATS['translated'], STATS['untranslated']


def run_batch(pairs):
    for (filename, outfile) in pairs:
        yield make_with_stats(filename, outfile)


def main():
    args = sys.argv[1:]
    if args == ['STDIN']:
        import json
        results = tuple(run_batch(json.loads(sys.stdin.buffer.read())))
        sys.stdout.buffer.write(json.dumps(results).encode('utf-8'))
        sys.stdout.close()
        return
    try:
        opts, args = getopt.getopt(args, 'hVso:',
                                   ['help', 'version', 'statistics', 'output-file='])
    except getopt.error as msg:
        usage(1, msg)

    outfile = None
    output_stats = False
    # parse options
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            usage(0)
        elif opt in ('-V', '--version'):
            print("msgfmt.py", __version__, file=sys.stderr)
            sys.exit(0)
        elif opt in ('-o', '--output-file'):
            outfile = arg
        elif opt in ('-s', '--statistics'):
            output_stats = True
    # do it
    if not args:
        print('No input file given', file=sys.stderr)
        print("Try `msgfmt --help' for more information.", file=sys.stderr)
        return

    for filename in args:
        translated, untranslated = make_with_stats(filename, outfile)
        if output_stats:
            print(STATS['translated'], 'translated messages,', STATS['untranslated'], 'untranslated messages.')


if __name__ == '__main__':
    main()
