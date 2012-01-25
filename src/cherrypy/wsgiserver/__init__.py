__all__ = ['HTTPRequest', 'HTTPConnection', 'HTTPServer',
           'SizeCheckWrapper', 'KnownLengthRFile', 'ChunkedRFile',
           'MaxSizeExceeded', 'NoSSLError', 'FatalSSLAlert',
           'WorkerThread', 'ThreadPool', 'SSLAdapter',
           'CherryPyWSGIServer',
           'Gateway', 'WSGIGateway', 'WSGIGateway_10', 'WSGIGateway_u0',
           'WSGIPathInfoDispatcher', 'get_ssl_adapter_class']

import sys
if sys.version_info < (3, 0):
    from wsgiserver2 import *
else:
    # Le sigh. Boo for backward-incompatible syntax.
    exec('from .wsgiserver3 import *')
