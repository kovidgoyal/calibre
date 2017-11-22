#!c:/Python27/python.exe
import os
os.environ['CALIBRE_CONFIG_DIRECTORY']='C:/Users/juamp/AppData/Roaming/calibre'
import sys
sys.path.append('C:/Users/juamp/github/calibre/src')
sys.path.append('C:/Python27/Lib/site-packages/')
from calibre.db.legacy import create_backend
from calibre.db.cache import Cache
db=Cache(create_backend("B:/Develop/Bilbio", load_user_formatter_functions=True))
db.init()
db.fields['languages'].book_value_map
