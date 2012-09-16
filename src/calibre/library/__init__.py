__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
''' Code to manage ebook library'''

def db(path=None, read_only=False):
    from calibre.library.database2 import LibraryDatabase2
    from calibre.utils.config import prefs
    return LibraryDatabase2(path if path else prefs['library_path'],
            read_only=read_only)


def generate_test_db(library_path, # {{{
        num_of_records=20000,
        num_of_authors=6000,
        num_of_tags=10000,
        tag_length=7,
        author_length=7,
        title_length=10,
        max_authors=10,
        max_tags=10
        ):
    import random, string, os, sys, time
    from calibre.constants import preferred_encoding

    if not os.path.exists(library_path):
        os.makedirs(library_path)

    letters = string.letters.decode(preferred_encoding)

    def randstr(length):
        return ''.join(random.choice(letters) for i in
                xrange(length))

    all_tags = [randstr(tag_length) for j in xrange(num_of_tags)]
    print 'Generated', num_of_tags, 'tags'
    all_authors = [randstr(author_length) for j in xrange(num_of_authors)]
    print 'Generated', num_of_authors, 'authors'
    all_titles = [randstr(title_length) for j in xrange(num_of_records)]
    print 'Generated', num_of_records, 'titles'

    testdb = db(library_path)

    print 'Creating', num_of_records, 'records...'

    start = time.time()

    for i, title in enumerate(all_titles):
        print i+1,
        sys.stdout.flush()
        authors = random.randint(1, max_authors)
        authors = [random.choice(all_authors) for i in xrange(authors)]
        tags = random.randint(0, max_tags)
        tags = [random.choice(all_tags) for i in xrange(tags)]
        from calibre.ebooks.metadata.book.base import Metadata
        mi = Metadata(title, authors)
        mi.tags = tags
        testdb.import_book(mi, [])

    t = time.time() - start
    print '\nGenerated', num_of_records, 'records in:', t, 'seconds'
    print 'Time per record:', t/float(num_of_records)
# }}}

def current_library_path():
    from calibre.utils.config import prefs
    path = prefs['library_path']
    if path:
        path = path.replace('\\', '/')
        while path.endswith('/'):
            path = path[:-1]
        return path

def current_library_name():
    import posixpath
    path = current_library_path()
    if path:
        return posixpath.basename(path)

