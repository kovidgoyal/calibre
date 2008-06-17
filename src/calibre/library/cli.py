#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Command line interface to the calibre database.
'''

import sys, os
from textwrap import TextWrapper

from calibre import OptionParser, Settings, terminal_controller, preferred_encoding
from calibre.gui2 import SingleApplication
from calibre.ebooks.metadata.meta import get_metadata
from calibre.ebooks.metadata.opf import OPFCreator, OPFReader
from calibre.library.database import LibraryDatabase, text_to_tokens

FIELDS = set(['title', 'authors', 'publisher', 'rating', 'timestamp', 'size', 'tags', 'comments', 'series', 'series_index', 'formats'])

def get_parser(usage):
    parser = OptionParser(usage)
    go = parser.add_option_group('GLOBAL OPTIONS')
    go.add_option('--database', default=None, help=_('Path to the calibre database. Default is to use the path stored in the settings.'))
    return parser

def get_db(dbpath, options):
    if options.database is not None:
        dbpath = options.database
    dbpath = os.path.abspath(dbpath)
    return LibraryDatabase(dbpath, row_factory=True)

def do_list(db, fields, sort_by, ascending, search_text):
    db.refresh(sort_by, ascending)
    if search_text:
        filters, OR = text_to_tokens(search_text)
        db.filter(filters, False, OR)
    fields = ['id'] + fields
    widths = list(map(lambda x : 0, fields))
    for i in db.data:
        for j, field in enumerate(fields):
            widths[j] = max(widths[j], len(unicode(i[field])))
    
    screen_width = terminal_controller.COLS
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
    titles = map(lambda x, y: '%-*s'%(x, y), widths, fields)
    print terminal_controller.GREEN + ''.join(titles)+terminal_controller.NORMAL
    
    wrappers = map(lambda x: TextWrapper(x-1), widths)
    
    for record in db.data:
        text = [wrappers[i].wrap(unicode(record[field]).encode('utf-8')) for i, field in enumerate(fields)]
        lines = max(map(len, text))
        for l in range(lines):
            for i, field in enumerate(text):
                ft = text[i][l] if l < len(text[i]) else ''
                filler = '%*s'%(widths[i]-len(ft), '')
                sys.stdout.write(ft)
                sys.stdout.write(filler)
            print
        

def command_list(args, dbpath):
    parser = get_parser(_(
'''\
%prog list [options]

List the books available in the calibre database. 
'''                      
                            ))
    parser.add_option('-f', '--fields', default='title,authors', 
                      help=_('The fields to display when listing books in the database. Should be a comma separated list of fields.\nAvailable fields: %s\nDefault: %%default')%','.join(FIELDS))
    parser.add_option('--sort-by', default='timestamp', 
                      help=_('The field by which to sort the results.\nAvailable fields: %s\nDefault: %%default')%','.join(FIELDS))
    parser.add_option('--ascending', default=False, action='store_true',
                      help=_('Sort results in ascending order'))
    parser.add_option('-s', '--search', default=None, 
                      help=_('Filter the results by the search query. For the format of the search query, please see the search related documentation in the User Manual. Default is to do no filtering.'))
    opts, args = parser.parse_args(sys.argv[:1] + args)
    fields = [f.strip().lower() for f in opts.fields.split(',')]
    
    if not set(fields).issubset(FIELDS):
        parser.print_help()
        print
        print _('Invalid fields. Available fields:'), ','.join(FIELDS)
        return 1
    
    db = get_db(dbpath, opts)
    if not opts.sort_by in FIELDS:
        parser.print_help()
        print
        print _('Invalid sort field. Available fields:'), ','.join(FIELDS)
        return 1
    
    do_list(db, fields, opts.sort_by, opts.ascending, opts.search)
    return 0
        

class DevNull(object):
    
    def write(self, msg):
        pass
NULL = DevNull()

def do_add(db, paths, one_book_per_directory, recurse, add_duplicates):
    sys.stdout = NULL
    try:
        files, dirs = [], []
        for path in paths:
            path = os.path.abspath(path)
            if os.path.isdir(path):
                dirs.append(path)
            else:
                files.append(path)
                
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
                mi.authors = ['Unknown']
 
            formats.append(format)
            metadata.append(mi)
           
        file_duplicates = db.add_books(files, formats, metadata, add_duplicates=add_duplicates)
        if not file_duplicates:
            file_duplicates = []
        
        
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
            print _('The following books were not added as they already exist in the database (see --duplicates option):')
            for mi, formats in dir_dups:
                title = mi.title
                if isinstance(title, unicode):
                    title = title.encode(preferred_encoding)
                print '\t', title + ':'
                for path in formats:
                    print '\t\t ', path
            if file_duplicates:
                for path, mi in zip(file_duplicates[0], file_duplicates[2]):
                    title = mi.title
                    if isinstance(title, unicode):
                        title = title.encode(preferred_encoding)
                    print '\t', title+':'
                    print '\t\t ', path
                
        if SingleApplication is not None:
            sa = SingleApplication('calibre GUI')
            sa.send_message('refreshdb:')
    finally:
        sys.stdout = sys.__stdout__
            
            
    
def command_add(args, dbpath):
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
    opts, args = parser.parse_args(sys.argv[:1] + args)
    if len(args) < 2:
        parser.print_help()
        print
        print _('You must specify at least one file to add')
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
    
    if SingleApplication is not None:
        sa = SingleApplication('calibre GUI')
        sa.send_message('refreshdb:')

def command_remove(args, dbpath):
    parser = get_parser(_(
'''\
%prog remove ids

Remove the books identified by ids from the database. ids should be a comma separated \
list of id numbers (you can get id numbers by using the list command). For example, \
23,34,57-85
'''))
    opts, args = parser.parse_args(sys.argv[:1] + args)
    if len(args) < 2:
        parser.print_help()
        print
        print _('You must specify at least one book to remove')
        return 1
    
    ids = []
    for x in args[1].split(','):
        y = x.split('-')
        if len(y) > 1:
            ids.append(range(int(y[0], int(y[1]))))
        else:
            ids.append(int(y[0]))
    
    do_remove(get_db(dbpath, opts), ids)
    
    return 0

def do_add_format(db, id, fmt, buffer):
    db.add_format(id, fmt.upper(), buffer, index_is_id=True)


def command_add_format(args, dbpath):
    parser = get_parser(_(
'''\
%prog add_format [options] id ebook_file

Add the ebook in ebook_file to the available formats for the logical book identified \
by id. You can get id by using the list command. If the format already exists, it is replaced.
'''))
    opts, args = parser.parse_args(sys.argv[:1] + args)
    if len(args) < 3:
        parser.print_help()
        print
        print _('You must specify an id and an ebook file')
        return 1
    
    id, file, fmt = int(args[1]), open(args[2], 'rb'), os.path.splitext(args[2])[-1]
    if not fmt:
        print _('ebook file must have an extension')
    do_add_format(get_db(dbpath, opts), id, fmt[1:], file)
    return 0

def do_remove_format(db, id, fmt):
    db.remove_format(id, fmt, index_is_id=True)

def command_remove_format(args, dbpath):
    parser = get_parser(_(
'''
%prog remove_format [options] id fmt

Remove the format fmt from the logical book identified by id. \
You can get id by using the list command. fmt should be a file extension \
like LRF or TXT or EPUB. If the logical book does not have fmt available, \
do nothing.
'''))
    opts, args = parser.parse_args(sys.argv[:1] + args)
    if len(args) < 3:
        parser.print_help()
        print
        print _('You must specify an id and a format')
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
        print mi
    
def command_show_metadata(args, dbpath):
    parser = get_parser(_(
'''
%prog show_metadata [options] id

Show the metadata stored in the calibre database for the book identified by id. 
id is an id number from the list command. 
'''))
    parser.add_option('--as-opf', default=False, action='store_true',
                      help=_('Print metadata in OPF form (XML)'))
    opts, args = parser.parse_args(sys.argv[1:]+args)
    if len(args) < 2:
        parser.print_help()
        print 
        print _('You must specify an id')
        return 1
    id = int(args[1])
    do_show_metadata(get_db(dbpath, opts), id, opts.as_opf)
    return 0

def do_set_metadata(db, id, stream):
    mi = OPFReader(stream)
    db.set_metadata(id, mi)
    do_show_metadata(db, id, False)

def command_set_metadata(args, dbpath):
    parser = get_parser(_(
'''
%prog set_metadata [options] id /path/to/metadata.opf

Set the metadata stored in the calibre database for the book identified by id
from the OPF file metadata.opf. id is an id number from the list command. You 
can get a quick feel for the OPF format by using the --as-opf switch to the
show_metadata command.
'''))
    opts, args = parser.parse_args(sys.argv[1:]+args)
    if len(args) < 3:
        parser.print_help()
        print 
        print _('You must specify an id and a metadata file')
        return 1
    id, opf = int(args[1]), open(args[2], 'rb')
    do_set_metadata(get_db(dbpath, opts), id, opf)
    return 0
    
def main(args=sys.argv):
    commands = ('list', 'add', 'remove', 'add_format', 'remove_format', 
                'show_metadata', 'set_metadata')
    parser = OptionParser(_(
'''\
%%prog command [options] [arguments]

%%prog is the command line interface to the calibre books database. 

command is one of:
  %s
  
For help on an individual command: %%prog command --help
'''
                          )%'\n  '.join(commands))
    if len(args) < 2:
        parser.print_help()
        return 1
    if args[1] not in commands:
        if args[1] == '--version':
            parser.print_version()
            return 0
        parser.print_help()
        return 1
    
    command = eval('command_'+args[1])
    dbpath = Settings().get('database path')
    
    return command(args[2:], dbpath)

if __name__ == '__main__':
    sys.exit(main())
