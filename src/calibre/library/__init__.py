__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
''' Code to manage ebook library'''

def db():
    from calibre.library.database2 import LibraryDatabase2
    from calibre.utils.config import prefs
    return LibraryDatabase2(prefs['library_path'])
