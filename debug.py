#!c:/Python27/python.exe
import os
os.environ['CALIBRE_CONFIG_DIRECTORY']='C:/Users/juamp/AppData/Roaming/calibre'
import sys
sys.path.append('C:/Users/juamp/github/calibre/src')

from calibre.db.legacy import create_backend
from calibre.db.cache import Cache
#db=Cache(create_backend("B:/Develop/Bilbio", load_user_formatter_functions=True))
db=Cache(create_backend("C:/Users/juamp/Develop/Biblio", None))
db.init()
db.fields['languages'].book_value_map
db.data_for_find_identical_books()
