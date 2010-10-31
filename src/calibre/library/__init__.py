__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
''' Code to manage ebook library'''

def db(path=None):
    from calibre.library.database2 import LibraryDatabase2
    from calibre.utils.config import prefs
    return LibraryDatabase2(path if path else prefs['library_path'])
