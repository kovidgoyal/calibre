#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Command line interface to the calibre database.
'''

import sys, os, cStringIO
from textwrap import TextWrapper
from urllib import quote

from calibre import terminal_controller, preferred_encoding, prints
from calibre.utils.config import OptionParser, prefs
from calibre.ebooks.metadata.meta import get_metadata
from calibre.library.database2 import LibraryDatabase2
from calibre.ebooks.metadata.opf2 import OPFCreator, OPF
from calibre.utils.genshi.template import MarkupTemplate
from calibre.utils.date import isoformat

FIELDS = set(['title', 'authors', 'author_sort', 'publisher', 'rating',
    'timestamp', 'size', 'tags', 'comments', 'series', 'series_index',
    'formats', 'isbn', 'uuid', 'pubdate', 'cover'])

XML_TEMPLATE = '''\
<?xml version="1.0"  encoding="UTF-8"?>
<calibredb xmlns:py="http://genshi.edgewall.org/">
<py:for each="record in data">
    <record>
        <id>${record['id']}</id>
        <uuid>${record['uuid']}</uuid>
        <title>${record['title']}</title>
        <authors sort="${record['author_sort']}">
        <py:for each="author in record['authors']">
            <author>$author</author>
        </py:for>
        </authors>
        <publisher>${record['publisher']}</publisher>
        <rating>${record['rating']}</rating>
        <date>${record['timestamp'].isoformat()}</date>
        <pubdate>${record['pubdate'].isoformat()}</pubdate>
        <size>${record['size']}</size>
        <tags py:if="record['tags']">
        <py:for each="tag in record['tags']">
            <tag>$tag</tag>
        </py:for>
        </tags>
        <comments>${record['comments']}</comments>
        <series py:if="record['series']" index="${record['series_index']}">${record['series']}</series>
        <isbn>${record['isbn']}</isbn>
        <cover py:if="record['cover']">${record['cover'].replace(os.sep, '/')}</cover>
        <formats py:if="record['formats']">
        <py:for each="path in record['formats']">
            <format>${path.replace(os.sep, '/')}</format>
        </py:for>
        </formats>
    </record>
</py:for>
</calibredb>
'''

STANZA_TEMPLATE='''\
<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:py="http://genshi.edgewall.org/">
  <title>calibre Library</title>
  <author>
    <name>calibre</name>
    <uri>http://calibre-ebook.com</uri>
  </author>
  <id>$id</id>
  <updated>${updated.isoformat()}</updated>
  <subtitle>
        ${subtitle}
  </subtitle>
  <py:for each="record in data">
  <entry>
      <title>${record['title']}</title>
      <id>urn:calibre:${record['uuid']}</id>
      <author><name>${record['author_sort']}</name></author>
      <updated>${record['timestamp'].isoformat()}</updated>
      <link type="application/epub+zip" href="${quote(record['fmt_epub'].replace(sep, '/'))}"/>
      <link py:if="record['cover']" rel="x-stanza-cover-image" type="image/png" href="${quote(record['cover'].replace(sep, '/'))}"/>
      <link py:if="record['cover']" rel="x-stanza-cover-image-thumbnail" type="image/png" href="${quote(record['cover'].replace(sep, '/'))}"/>
      <content type="xhtml">
          <div xmlns="http://www.w3.org/1999/xhtml">
              <py:for each="f in ('authors', 'publisher', 'rating', 'tags', 'series', 'isbn')">
              <py:if test="record[f]">
              ${f.capitalize()}:${unicode(', '.join(record[f]) if f=='tags' else record[f])}
              <py:if test="f =='series'"># ${str(record['series_index'])}</py:if>
              <br/>
              </py:if>
              </py:for>
              <py:if test="record['comments']">
              <br/>
              ${record['comments']}
              </py:if>
          </div>
      </content>
  </entry>
  </py:for>
</feed>
'''

def send_message(msg=''):
    prints('Notifying calibre of the change')
    from calibre.utils.ipc import RC
    import time
    t = RC(print_error=False)
    t.start()
    time.sleep(3)
    if t.done:
        t.conn.send('refreshdb:'+msg)
        t.conn.close()




def get_parser(usage):
    parser = OptionParser(usage)
    go = parser.add_option_group('GLOBAL OPTIONS')
    go.add_option('--library-path', default=None, help=_('Path to the calibre library. Default is to use the path stored in the settings.'))

    return parser

def get_db(dbpath, options):
    if options.library_path is not None:
        dbpath = options.library_path
    dbpath = os.path.abspath(dbpath)
    return LibraryDatabase2(dbpath)

def do_list(db, fields, sort_by, ascending, search_text, line_width, separator,
            prefix, output_format, subtitle='Books in the calibre database'):
    if sort_by:
        db.sort(sort_by, ascending)
    if search_text:
        db.search(search_text)
    authors_to_string = output_format in ['stanza', 'text']
    data = db.get_data_as_dict(prefix, authors_as_string=authors_to_string)
    fields = ['id'] + fields
    if output_format == 'text':
        for f in data:
            fmts = [x for x in f['formats'] if x is not None]
            f['formats'] = u'[%s]'%u','.join(fmts)
        widths = list(map(lambda x : 0, fields))
        for record in data:
            for f in record.keys():
                if hasattr(record[f], 'isoformat'):
                    record[f] = isoformat(record[f], as_utc=False)
                else:
                    record[f] = unicode(record[f])
                record[f] = record[f].replace('\n', ' ')
        for i in data:
            for j, field in enumerate(fields):
                widths[j] = max(widths[j], len(unicode(i[str(field)])))

        screen_width = terminal_controller.COLS if line_width < 0 else line_width
        if not screen_width:
            screen_width = 80
        field_width = screen_width//len(fields)
        base_widths = map(lambda x: min(x+1, field_width), widths)

        while sum(base_widths) < screen_width:
            adjusted = False
            for i in range(len(widths)):
                if base_widths[i] < widths[i]:
                    base_widths[i] += min(screen_width-sum(base_widths), widths[i]-base_widths[i])
                    adjusted = True
                    break
            if not adjusted:
                break

        widths = list(base_widths)
        titles = map(lambda x, y: '%-*s%s'%(x-len(separator), y, separator), widths, fields)
        print terminal_controller.GREEN + ''.join(titles)+terminal_controller.NORMAL

        wrappers = map(lambda x: TextWrapper(x-1), widths)
        o = cStringIO.StringIO()

        for record in data:
            text = [wrappers[i].wrap(unicode(record[field]).encode('utf-8')) for i, field in enumerate(fields)]
            lines = max(map(len, text))
            for l in range(lines):
                for i, field in enumerate(text):
                    ft = text[i][l] if l < len(text[i]) else ''
                    filler = '%*s'%(widths[i]-len(ft)-1, '')
                    o.write(ft)
                    o.write(filler+separator)
                print >>o
        return o.getvalue()
    elif output_format == 'xml':
        template = MarkupTemplate(XML_TEMPLATE)
        return template.generate(data=data, os=os).render('xml')
    elif output_format == 'stanza':
        data = [i for i in data if i.has_key('fmt_epub')]
        for x in data:
            if isinstance(x['fmt_epub'], unicode):
                x['fmt_epub'] = x['fmt_epub'].encode('utf-8')
        template = MarkupTemplate(STANZA_TEMPLATE)
        return template.generate(id="urn:calibre:main", data=data, subtitle=subtitle,
                sep=os.sep, quote=quote, updated=db.last_modified()).render('xml')

def list_option_parser():
    parser = get_parser(_(
'''\
%prog list [options]

List the books available in the calibre database.
'''
                            ))
    parser.add_option('-f', '--fields', default='title,authors',
                      help=_('The fields to display when listing books in the database. Should be a comma separated list of fields.\nAvailable fields: %s\nDefault: %%default. The special field "all" can be used to select all fields. Only has effect in the text output format.')%','.join(FIELDS))
    parser.add_option('--sort-by', default=None,
                      help=_('The field by which to sort the results.\nAvailable fields: %s\nDefault: %%default')%','.join(FIELDS))
    parser.add_option('--ascending', default=False, action='store_true',
                      help=_('Sort results in ascending order'))
    parser.add_option('-s', '--search', default=None,
                      help=_('Filter the results by the search query. For the format of the search query, please see the search related documentation in the User Manual. Default is to do no filtering.'))
    parser.add_option('-w', '--line-width', default=-1, type=int,
                      help=_('The maximum width of a single line in the output. Defaults to detecting screen size.'))
    parser.add_option('--separator', default=' ', help=_('The string used to separate fields. Default is a space.'))
    parser.add_option('--prefix', default=None, help=_('The prefix for all file paths. Default is the absolute path to the library folder.'))
    of = ['text', 'xml', 'stanza']
    parser.add_option('--output-format', choices=of, default='text',
                      help=_('The format in which to output the data. Available choices: %s. Defaults is text.')%of)
    return parser


def command_list(args, dbpath):
    parser = list_option_parser()
    opts, args = parser.parse_args(sys.argv[:1] + args)
    fields = [str(f.strip().lower()) for f in opts.fields.split(',')]
    if 'all' in fields:
        fields = sorted(list(FIELDS))
    if not set(fields).issubset(FIELDS):
        parser.print_help()
        print
        print >>sys.stderr, _('Invalid fields. Available fields:'), ','.join(sorted(FIELDS))
        return 1

    db = get_db(dbpath, opts)
    if not opts.sort_by in FIELDS and opts.sort_by is not None:
        parser.print_help()
        print
        print >>sys.stderr, _('Invalid sort field. Available fields:'), ','.join(FIELDS)
        return 1

    print do_list(db, fields, opts.sort_by, opts.ascending, opts.search, opts.line_width, opts.separator,
            opts.prefix, opts.output_format)
    return 0


class DevNull(object):

    def write(self, msg):
        pass
NULL = DevNull()

def do_add(db, paths, one_book_per_directory, recurse, add_duplicates):
    orig = sys.stdout
    #sys.stdout = NULL
    try:
        files, dirs = [], []
        for path in paths:
            path = os.path.abspath(path)
            if os.path.isdir(path):
                dirs.append(path)
            else:
                if os.path.exists(path):
                    files.append(path)
                else:
                    print path, 'not found'

        formats, metadata = [], []
        for book in files:
            format = os.path.splitext(book)[1]
            format = format[1:] if format else None
            if not format:
                continue
            stream = open(book, 'rb')
            mi = get_metadata(stream, stream_type=format, use_libprs_metadata=True)
            if not mi.title:
                mi.title = os.path.splitext(os.path.basename(book))[0]
            if not mi.authors:
                mi.authors = [_('Unknown')]

            formats.append(format)
            metadata.append(mi)

        file_duplicates = []
        if files:
            file_duplicates = db.add_books(files, formats, metadata,
                                           add_duplicates=add_duplicates)
            if file_duplicates:
                file_duplicates = file_duplicates[0]


        dir_dups = []
        for dir in dirs:
            if recurse:
                dir_dups.extend(db.recursive_import(dir, single_book_per_directory=one_book_per_directory))
            else:
                func = db.import_book_directory if one_book_per_directory else db.import_book_directory_multiple
                dups = func(dir)
                if not dups:
                    dups = []
                dir_dups.extend(dups)

        sys.stdout = sys.__stdout__

        if add_duplicates:
            for mi, formats in dir_dups:
                db.import_book(mi, formats)
        else:
            if dir_dups or file_duplicates:
                print >>sys.stderr, _('The following books were not added as '
                                      'they already exist in the database '
                                      '(see --duplicates option):')
            for mi, formats in dir_dups:
                title = mi.title
                if isinstance(title, unicode):
                    title = title.encode(preferred_encoding)
                print >>sys.stderr, '\t', title + ':'
                for path in formats:
                    print >>sys.stderr, '\t\t ', path
            if file_duplicates:
                for path, mi in zip(file_duplicates[0], file_duplicates[2]):
                    title = mi.title
                    if isinstance(title, unicode):
                        title = title.encode(preferred_encoding)
                    print >>sys.stderr, '\t', title+':'
                    print >>sys.stderr, '\t\t ', path

        send_message()
    finally:
        sys.stdout = orig

def add_option_parser():
    parser = get_parser(_(
'''\
%prog add [options] file1 file2 file3 ...

Add the specified files as books to the database. You can also specify directories, see
the directory related options below.
'''
                            ))
    parser.add_option('-1', '--one-book-per-directory', action='store_true', default=False,
                      help=_('Assume that each directory has only a single logical book and that all files in it are different e-book formats of that book'))
    parser.add_option('-r', '--recurse', action='store_true', default=False,
                      help=_('Process directories recursively'))
    parser.add_option('-d', '--duplicates', action='store_true', default=False,
                      help=_('Add books to database even if they already exist. Comparison is done based on book titles.'))
    return parser


def command_add(args, dbpath):
    parser = add_option_parser()
    opts, args = parser.parse_args(sys.argv[:1] + args)
    if len(args) < 2:
        parser.print_help()
        print
        print >>sys.stderr, _('You must specify at least one file to add')
        return 1
    do_add(get_db(dbpath, opts), args[1:], opts.one_book_per_directory, opts.recurse, opts.duplicates)
    return 0

def do_remove(db, ids):
    for x in ids:
        if isinstance(x, int):
            db.delete_book(x)
        else:
            for y in x:
                db.delete_book(y)

        send_message()

def remove_option_parser():
    return get_parser(_(
'''\
%prog remove ids

Remove the books identified by ids from the database. ids should be a comma separated \
list of id numbers (you can get id numbers by using the list command). For example, \
23,34,57-85
'''))

def command_remove(args, dbpath):
    parser = remove_option_parser()
    opts, args = parser.parse_args(sys.argv[:1] + args)
    if len(args) < 2:
        parser.print_help()
        print
        print >>sys.stderr, _('You must specify at least one book to remove')
        return 1

    ids = []
    for x in args[1].split(','):
        y = x.split('-')
        if len(y) > 1:
            ids.append(range(int(y[0], int(y[1]))))
        else:
            ids.append(int(y[0]))

    do_remove(get_db(dbpath, opts), set(ids))

    return 0

def do_add_format(db, id, fmt, path):
    db.add_format_with_hooks(id, fmt.upper(), path, index_is_id=True)

def add_format_option_parser():
    return get_parser(_(
'''\
%prog add_format [options] id ebook_file

Add the ebook in ebook_file to the available formats for the logical book identified \
by id. You can get id by using the list command. If the format already exists, it is replaced.
'''))


def command_add_format(args, dbpath):
    parser = add_format_option_parser()
    opts, args = parser.parse_args(sys.argv[:1] + args)
    if len(args) < 3:
        parser.print_help()
        print
        print >>sys.stderr, _('You must specify an id and an ebook file')
        return 1

    id, path, fmt = int(args[1]), args[2], os.path.splitext(args[2])[-1]
    if not fmt:
        print _('ebook file must have an extension')
    do_add_format(get_db(dbpath, opts), id, fmt[1:], path)
    return 0

def do_remove_format(db, id, fmt):
    db.remove_format(id, fmt, index_is_id=True)

def remove_format_option_parser():
    return get_parser(_(
'''
%prog remove_format [options] id fmt

Remove the format fmt from the logical book identified by id. \
You can get id by using the list command. fmt should be a file extension \
like LRF or TXT or EPUB. If the logical book does not have fmt available, \
do nothing.
'''))


def command_remove_format(args, dbpath):
    parser = remove_format_option_parser()
    opts, args = parser.parse_args(sys.argv[:1] + args)
    if len(args) < 3:
        parser.print_help()
        print
        print >>sys.stderr, _('You must specify an id and a format')
        return 1

    id, fmt = int(args[1]), args[2].upper()
    do_remove_format(get_db(dbpath, opts), id, fmt)
    return 0

def do_show_metadata(db, id, as_opf):
    if not db.has_id(id):
        raise ValueError('Id #%d is not present in database.'%id)
    mi = db.get_metadata(id, index_is_id=True)
    if as_opf:
        mi = OPFCreator(os.getcwd(), mi)
        mi.render(sys.stdout)
    else:
        print unicode(mi).encode(preferred_encoding)

def show_metadata_option_parser():
    parser = get_parser(_(
'''
%prog show_metadata [options] id

Show the metadata stored in the calibre database for the book identified by id.
id is an id number from the list command.
'''))
    parser.add_option('--as-opf', default=False, action='store_true',
                      help=_('Print metadata in OPF form (XML)'))
    return parser

def command_show_metadata(args, dbpath):
    parser = show_metadata_option_parser()
    opts, args = parser.parse_args(sys.argv[1:]+args)
    if len(args) < 2:
        parser.print_help()
        print
        print >>sys.stderr, _('You must specify an id')
        return 1
    id = int(args[1])
    do_show_metadata(get_db(dbpath, opts), id, opts.as_opf)
    return 0

def do_set_metadata(db, id, stream):
    mi = OPF(stream)
    db.set_metadata(id, mi)
    do_show_metadata(db, id, False)
    send_message()

def set_metadata_option_parser():
    return get_parser(_(
'''
%prog set_metadata [options] id /path/to/metadata.opf

Set the metadata stored in the calibre database for the book identified by id
from the OPF file metadata.opf. id is an id number from the list command. You
can get a quick feel for the OPF format by using the --as-opf switch to the
show_metadata command.
'''))

def command_set_metadata(args, dbpath):
    parser = set_metadata_option_parser()
    opts, args = parser.parse_args(sys.argv[1:]+args)
    if len(args) < 3:
        parser.print_help()
        print
        print >>sys.stderr, _('You must specify an id and a metadata file')
        return 1
    id, opf = int(args[1]), open(args[2], 'rb')
    do_set_metadata(get_db(dbpath, opts), id, opf)
    return 0

def do_export(db, ids, dir, opts):
    if ids is None:
        ids = list(db.all_ids())
    from calibre.library.save_to_disk import save_to_disk
    failures = save_to_disk(db, ids, dir, opts=opts)

    if failures:
        prints('Failed to save the following books:')
        for id, title, tb in failures:
            prints(str(id)+':', title)
            prints('\t'+'\n\t'.join(tb.splitlines()))
            prints(' ')

def export_option_parser():
    parser = get_parser(_('''\
%prog export [options] ids

Export the books specified by ids (a comma separated list) to the filesystem.
The export operation saves all formats of the book, its cover and metadata (in
an opf file). You can get id numbers from the list command.
'''))
    parser.add_option('--all', default=False, action='store_true',
                      help=_('Export all books in database, ignoring the list of ids.'))
    parser.add_option('--to-dir', default='.',
                      help=(_('Export books to the specified directory. Default is')+' %default'))
    parser.add_option('--single-dir', default=False, action='store_true',
                      help=_('Export all books into a single directory'))
    from calibre.library.save_to_disk import config
    c = config()
    for pref in ['asciiize', 'update_metadata', 'write_opf', 'save_cover']:
        opt = c.get_option(pref)
        switch = '--dont-'+pref.replace('_', '-')
        parser.add_option(switch, default=True, action='store_false',
                help=opt.help+' '+_('Specifying this switch will turn '
                    'this behavior off.'), dest=pref)

    for pref in ['timefmt', 'template', 'formats']:
        opt = c.get_option(pref)
        switch = '--'+pref
        parser.add_option(switch, default=opt.default,
                help=opt.help, dest=pref)

    for pref in ('replace_whitespace', 'to_lowercase'):
        opt = c.get_option(pref)
        switch = '--'+pref.replace('_', '-')
        parser.add_option(switch, default=False, action='store_true',
                help=opt.help)

    return parser

def command_export(args, dbpath):
    parser = export_option_parser()
    opts, args = parser.parse_args(sys.argv[1:]+args)
    if (len(args) < 2 and not opts.all):
        parser.print_help()
        print
        print >>sys.stderr, _('You must specify some ids or the %s option')%'--all'
        return 1
    ids = None if opts.all else map(int, args[1].split(','))
    dir = os.path.abspath(os.path.expanduser(opts.to_dir))
    do_export(get_db(dbpath, opts), ids, dir, opts)
    return 0

def catalog_option_parser(args):
    from calibre.customize.ui import available_catalog_formats, plugin_for_catalog_format
    from calibre.utils.logging import Log

    def add_plugin_parser_options(fmt, parser, log):

        # Fetch the extension-specific CLI options from the plugin
        plugin = plugin_for_catalog_format(fmt)
        for option in plugin.cli_options:
            if option.action:
                parser.add_option(option.option,
                                  default=option.default,
                                  dest=option.dest,
                                  action=option.action,
                                  help=option.help)
            else:
                parser.add_option(option.option,
                                  default=option.default,
                                  dest=option.dest,
                                  help=option.help)

        return plugin

    def print_help(parser, log):
        help = parser.format_help().encode(preferred_encoding, 'replace')
        log(help)

    def validate_command_line(parser, args, log):
        # calibredb catalog path/to/destination.[epub|csv|xml|...] [options]

        # Validate form
        if not len(args) or args[0].startswith('-'):
            print_help(parser, log)
            log.error("\n\nYou must specify a catalog output file of the form 'path/to/destination.extension'\n"
            "To review options for an output format, type 'calibredb catalog <.extension> --help'\n"
            "For example, 'calibredb catalog .xml --help'\n")
            raise SystemExit(1)

        # Validate plugin exists for specified output format
        output = os.path.abspath(args[0])
        file_extension = output[output.rfind('.') + 1:].lower()

        if not file_extension in available_catalog_formats():
            print_help(parser, log)
            log.error("No catalog plugin available for extension '%s'.\n" % file_extension +
                      "Catalog plugins available for %s\n" % ', '.join(available_catalog_formats()) )
            raise SystemExit(1)

        return output, file_extension

    # Entry point
    log = Log()
    parser = get_parser(_(
    '''
    %prog catalog /path/to/destination.(csv|epub|mobi|xml ...) [options]

    Export a catalog in format specified by path/to/destination extension.
    Options control how entries are displayed in the generated catalog ouput.
    '''))

    # Confirm that a plugin handler exists for specified output file extension
    # Will raise SystemExit(1) if no plugin matching file_extension
    output, fmt = validate_command_line(parser, args, log)

    # Add options common to all catalog plugins
    parser.add_option('-i', '--ids', default=None, dest='ids',
                      help=_("Comma-separated list of database IDs to catalog.\n"
                      "If declared, --search is ignored.\n"
                             "Default: all"))
    parser.add_option('-s', '--search', default=None, dest='search_text',
                      help=_("Filter the results by the search query. "
                          "For the format of the search query, please see "
                          "the search-related documentation in the User Manual.\n"
                      "Default: no filtering"))
    parser.add_option('-v','--verbose', default=False, action='store_true',
                      dest='verbose',
                      help=_('Show detailed output information. Useful for debugging'))

    # Add options specific to fmt plugin
    plugin = add_plugin_parser_options(fmt, parser, log)

    return parser, plugin, log

def command_catalog(args, dbpath):
    parser, plugin, log = catalog_option_parser(args)
    opts, args = parser.parse_args(sys.argv[1:])
    if len(args) < 2:
        parser.print_help()
        print
        print >>sys.stderr, _('Error: You must specify a catalog output file')
        return 1
    if opts.ids:
        opts.ids = [int(id) for id in opts.ids.split(',')]

    # No support for connected device in CLI environment
    # Parallel initialization in calibre.gui2.tools:generate_catalog()
    opts.connected_device = { 'storage':None,'serial':None,'save_template':None,'name':None}

    with plugin:
        plugin.run(args[1], opts, get_db(dbpath, opts))
    return 0

# end of GR additions

COMMANDS = ('list', 'add', 'remove', 'add_format', 'remove_format',
                'show_metadata', 'set_metadata', 'export', 'catalog')


def option_parser():
    parser = OptionParser(_(
'''\
%%prog command [options] [arguments]

%%prog is the command line interface to the calibre books database.

command is one of:
  %s

For help on an individual command: %%prog command --help
'''
                          )%'\n  '.join(COMMANDS))
    return parser


def main(args=sys.argv):
    parser = option_parser()
    if len(args) < 2:
        parser.print_help()
        return 1
    if args[1] not in COMMANDS:
        if args[1] == '--version':
            parser.print_version()
            return 0
        parser.print_help()
        return 1

    command = eval('command_'+args[1])
    dbpath = prefs['library_path']

    return command(args[2:], dbpath)

if __name__ == '__main__':
    sys.exit(main())
