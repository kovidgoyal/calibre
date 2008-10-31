import cherrypy


class MultipartWrapper(object):
    """Wraps a file-like object, returning '' when Content-Length is reached.
    
    The cgi module's logic for reading multipart MIME messages doesn't
    allow the parts to know when the Content-Length for the entire message
    has been reached, and doesn't allow for multipart-MIME messages that
    omit the trailing CRLF (Flash 8's FileReference.upload(url), for example,
    does this). The read_lines_to_outerboundary function gets stuck in a loop
    until the socket times out.
    
    This rfile wrapper simply monitors the incoming stream. When a read is
    attempted past the Content-Length, it returns an empty string rather
    than timing out (of course, if the last read *overlaps* the C-L, you'll
    get the last bit of data up to C-L, and then the next read will return
    an empty string).
    """
    
    def __init__(self, rfile, clen):
        self.rfile = rfile
        self.clen = clen
        self.bytes_read = 0
    
    def read(self, size = None):
        if self.clen:
            # Return '' if we've read all the data.
            if self.bytes_read >= self.clen:
                return ''
            
            # Reduce 'size' if it's over our limit.
            new_bytes_read = self.bytes_read + size
            if new_bytes_read > self.clen:
                size = self.clen - self.bytes_read
        
        data = self.rfile.read(size)
        self.bytes_read += len(data)
        return data
    
    def readline(self, size = None):
        if size is not None:
            if self.clen:
                # Return '' if we've read all the data.
                if self.bytes_read >= self.clen:
                    return ''
                
                # Reduce 'size' if it's over our limit.
                new_bytes_read = self.bytes_read + size
                if new_bytes_read > self.clen:
                    size = self.clen - self.bytes_read
            
            data = self.rfile.readline(size)
            self.bytes_read += len(data)
            return data
        
        # User didn't specify a size ...
        # We read the line in chunks to make sure it's not a 100MB line !
        res = []
        size = 256
        while True:
            if self.clen:
                # Return if we've read all the data.
                if self.bytes_read >= self.clen:
                    return ''.join(res)
                
                # Reduce 'size' if it's over our limit.
                new_bytes_read = self.bytes_read + size
                if new_bytes_read > self.clen:
                    size = self.clen - self.bytes_read
            
            data = self.rfile.readline(size)
            self.bytes_read += len(data)
            res.append(data)
            # See http://www.cherrypy.org/ticket/421
            if len(data) < size or data[-1:] == "\n":
                return ''.join(res)
    
    def readlines(self, sizehint = 0):
        # Shamelessly stolen from StringIO
        total = 0
        lines = []
        line = self.readline()
        while line:
            lines.append(line)
            total += len(line)
            if 0 < sizehint <= total:
                break
            line = self.readline()
        return lines
    
    def close(self):
        self.rfile.close()
    
    def __iter__(self):
        return self.rfile
    
    def next(self):
        if self.clen:
            # Return '' if we've read all the data.
            if self.bytes_read >= self.clen:
                return ''
        
        data = self.rfile.next()
        self.bytes_read += len(data)
        return data


def safe_multipart(flash_only=False):
    """Wrap request.rfile in a reader that won't crash on no trailing CRLF."""
    h = cherrypy.request.headers
    if not h.get('Content-Type').startswith('multipart/'):
        return
    if flash_only and not 'Shockwave Flash' in h.get('User-Agent', ''):
        return
    
    clen = h.get('Content-Length', '0')
    try:
        clen = int(clen)
    except ValueError:
        return
    cherrypy.request.rfile = MultipartWrapper(cherrypy.request.rfile, clen)

def init():
    """Create a Tool for safe_multipart and add it to cherrypy.tools."""
    cherrypy.tools.safe_multipart = cherrypy.Tool('before_request_body',
                                                   safe_multipart)

