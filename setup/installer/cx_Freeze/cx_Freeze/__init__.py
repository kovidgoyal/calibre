version = "4.0.1"

import sys
from dist import *
if sys.platform == "win32" and sys.version_info[:2] >= (2, 5):
    from windist import *
from finder import *
from freezer import *
from main import *

del dist
del finder
del freezer

