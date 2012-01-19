import warnings
warnings.warn('cherrypy.lib.http has been deprecated and will be removed '
              'in CherryPy 3.3 use cherrypy.lib.httputil instead.',
              DeprecationWarning)

from cherrypy.lib.httputil import *

