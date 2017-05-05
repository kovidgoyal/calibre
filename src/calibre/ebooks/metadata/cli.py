from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
ebook-meta
'''
import sys, os

from calibre.utils.config import StringConfig
from calibre.customize.ui import metadata_readers, metadata_writers, force_identifiers
from calibre.ebooks.metadata.meta import get_metadata, set_metadata
from calibre.ebooks.metadata import string_to_authors, authors_to_sort_string, \
                    title_sort, MetaInformation
from calibre.ebooks.lrf.meta import LRFMetaFile
from calibre import prints
from calibre.utils.date import parse_date

USAGE=_('%prog ebook_file [options]\n') + \
_('''
Read/Write metadata from/to e-book files.

Supported formats for reading metadata: {0}

Supported formats for writing metadata: {1}

Different file types support different kinds of metadata. If you try to set
some metadata on a file type that does not support it, the metadata will be
silently ignored.
''')


def config():
    c = StringConfig('')
    c.add_opt('title', ['-t', '--title'],
              help=_('Set the title.'))
    c.add_opt('authors', ['-a', '--authors'],
              help=_('Set the authors. Multiple authors should be separated '
                     'by the & character. Author names should be in the order '
                     'Firstname Lastname.'))
    c.add_opt('title_sort', ['--title-sort'],
              help=_('The version of the title to be used for sorting. '
                     'If unspecified, and the title is specified, it will '
                     'be auto-generated from the title.'))
    c.add_opt('author_sort', ['--author-sort'],
              help=_('String to be used when sorting by author. '
                     'If unspecified, and the author(s) are specified, it will '
                     'be auto-generated from the author(s).'))
    c.add_opt('cover', ['--cover'],
              help=_('Set the cover to the specified file.'))
    c.add_opt('comments', ['-c', '--comments'],
              help=_('Set the e-book description.'))
    c.add_opt('publisher', ['-p', '--publisher'],
              help=_('Set the e-book publisher.'))
    c.add_opt('category', ['--category'],
              help=_('Set the book category.'))
    c.add_opt('series', ['-s', '--series'],
              help=_('Set the series this e-book belongs to.'))
    c.add_opt('series_index', ['-i', '--index'],
              help=_('Set the index of the book in this series.'))
    c.add_opt('rating', ['-r', '--rating'],
              help=_('Set the rating. Should be a number between 1 and 5.'))
    c.add_opt('isbn', ['--isbn'],
              help=_('Set the ISBN of the book.'))
    c.add_opt('identifiers', ['--identifier'], action='append',
              help=_('Set the identifiers for the book, can be specified multiple times.'
                     ' For example: --identifier uri:http://acme.com --identifier isbn:12345'
                     ' To remove an identifier, specify no value, --identifier isbn:'
                     ' Note that for EPUB files, an identifier marked as the package identifier cannot be removed.'))
    c.add_opt('tags', ['--tags'],
              help=_('Set the tags for the book. Should be a comma separated list.'))
    c.add_opt('book_producer', ['-k', '--book-producer'],
              help=_('Set the book producer.'))
    c.add_opt('language', ['-l', '--language'],
              help=_('Set the language.'))
    c.add_opt('pubdate', ['-d', '--date'],
              help=_('Set the published date.'))

    c.add_opt('get_cover', ['--get-cover'],
              help=_('Get the cover from the e-book and save it at as the '
                     'specified file.'))
    c.add_opt('to_opf', ['--to-opf'],
              help=_('Specify the name of an OPF file. The metadata will '
                     'be written to the OPF file.'))
    c.add_opt('from_opf', ['--from-opf'],
              help=_('Read metadata from the specified OPF file and use it to '
                     'set metadata in the e-book. Metadata specified on the '
                     'command line will override metadata read from the OPF file'))

    c.add_opt('lrf_bookid', ['--lrf-bookid'],
              help=_('Set the BookID in LRF files'))
    return c


def filetypes():
    readers = set([])
    for r in metadata_readers():
        readers = readers.union(set(r.file_types))
    return readers


def option_parser():
    writers = set([])
    for w in metadata_writers():
        writers = writers.union(set(w.file_types))
    ft, w = ', '.join(sorted(filetypes())), ', '.join(sorted(writers))
    return config().option_parser(USAGE.format(ft, w))


def do_set_metadata(opts, mi, stream, stream_type):
    mi = MetaInformation(mi)
    for x in ('guide', 'toc', 'manifest', 'spine'):
        setattr(mi, x, None)

    from_opf = getattr(opts, 'from_opf', None)
    if from_opf is not None:
        from calibre.ebooks.metadata.opf2 import OPF
        opf_mi = OPF(open(from_opf, 'rb')).to_book_metadata()
        mi.smart_update(opf_mi)

    for pref in config().option_set.preferences:
        if pref.name in ('to_opf', 'from_opf', 'authors', 'title_sort',
                         'author_sort', 'get_cover', 'cover', 'tags',
                         'lrf_bookid', 'identifiers'):
            continue
        val = getattr(opts, pref.name, None)
        if val is not None:
            setattr(mi, pref.name, val)
    if getattr(opts, 'authors', None) is not None:
        mi.authors = string_to_authors(opts.authors)
        mi.author_sort = authors_to_sort_string(mi.authors)
    if getattr(opts, 'author_sort', None) is not None:
        mi.author_sort = opts.author_sort
    if getattr(opts, 'title_sort', None) is not None:
        mi.title_sort = opts.title_sort
    elif getattr(opts, 'title', None) is not None:
        mi.title_sort = title_sort(opts.title)
    if getattr(opts, 'tags', None) is not None:
        mi.tags = [t.strip() for t in opts.tags.split(',')]
    if getattr(opts, 'series', None) is not None:
        mi.series = opts.series.strip()
    if getattr(opts, 'series_index', None) is not None:
        mi.series_index = float(opts.series_index.strip())
    if getattr(opts, 'pubdate', None) is not None:
        mi.pubdate = parse_date(opts.pubdate, assume_utc=False, as_utc=False)
    if getattr(opts, 'identifiers', None):
        val = {k.strip():v.strip() for k, v in (x.partition(':')[0::2] for x in opts.identifiers)}
        if val:
            orig = mi.get_identifiers()
            orig.update(val)
            val = {k:v for k, v in orig.iteritems() if k and v}
            mi.set_identifiers(val)

    if getattr(opts, 'cover', None) is not None:
        ext = os.path.splitext(opts.cover)[1].replace('.', '').upper()
        mi.cover_data = (ext, open(opts.cover, 'rb').read())

    with force_identifiers:
        set_metadata(stream, mi, stream_type)


def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) < 2:
        parser.print_help()
        prints(_('No file specified'), file=sys.stderr)
        return 1
    path = args[1]
    stream_type = os.path.splitext(path)[1].replace('.', '').lower()

    trying_to_set = False
    for pref in config().option_set.preferences:
        if pref.name in ('to_opf', 'get_cover'):
            continue
        if getattr(opts, pref.name) is not None:
            trying_to_set = True
            break
    with open(path, 'rb') as stream:
        mi = get_metadata(stream, stream_type, force_read_metadata=True)
    if trying_to_set:
        prints(_('Original metadata')+'::')
    metadata = unicode(mi)
    if trying_to_set:
        metadata = '\t'+'\n\t'.join(metadata.split('\n'))
    prints(metadata, safe_encode=True)

    if trying_to_set:
        with open(path, 'r+b') as stream:
            do_set_metadata(opts, mi, stream, stream_type)
            stream.seek(0)
            stream.flush()
            lrf = None
            if stream_type == 'lrf':
                if opts.lrf_bookid is not None:
                    lrf = LRFMetaFile(stream)
                    lrf.book_id = opts.lrf_bookid
            mi = get_metadata(stream, stream_type, force_read_metadata=True)
        prints('\n' + _('Changed metadata') + '::')
        metadata = unicode(mi)
        metadata = '\t'+'\n\t'.join(metadata.split('\n'))
        prints(metadata, safe_encode=True)
        if lrf is not None:
            prints('\tBookID:', lrf.book_id)

    if opts.to_opf is not None:
        from calibre.ebooks.metadata.opf2 import OPFCreator
        opf = OPFCreator(os.getcwdu(), mi)
        with open(opts.to_opf, 'wb') as f:
            opf.render(f)
        prints(_('OPF created in'), opts.to_opf)

    if opts.get_cover is not None:
        if mi.cover_data and mi.cover_data[1]:
            with open(opts.get_cover, 'wb') as f:
                f.write(mi.cover_data[1])
                prints(_('Cover saved to'), f.name)
        else:
            prints(_('No cover found'), file=sys.stderr)

    return 0


if __name__ == '__main__':
    sys.exit(main())
