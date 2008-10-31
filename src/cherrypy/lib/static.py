import mimetypes
mimetypes.init()
mimetypes.types_map['.dwg']='image/x-dwg'
mimetypes.types_map['.ico']='image/x-icon'

import os
import re
import stat
import time
import urllib

import cherrypy
from cherrypy.lib import cptools, http


def serve_file(path, content_type=None, disposition=None, name=None):
    """Set status, headers, and body in order to serve the given file.
    
    The Content-Type header will be set to the content_type arg, if provided.
    If not provided, the Content-Type will be guessed by the file extension
    of the 'path' argument.
    
    If disposition is not None, the Content-Disposition header will be set
    to "<disposition>; filename=<name>". If name is None, it will be set
    to the basename of path. If disposition is None, no Content-Disposition
    header will be written.
    """
    
    response = cherrypy.response
    
    # If path is relative, users should fix it by making path absolute.
    # That is, CherryPy should not guess where the application root is.
    # It certainly should *not* use cwd (since CP may be invoked from a
    # variety of paths). If using tools.static, you can make your relative
    # paths become absolute by supplying a value for "tools.static.root".
    if not os.path.isabs(path):
        raise ValueError("'%s' is not an absolute path." % path)
    
    try:
        st = os.stat(path)
    except OSError:
        raise cherrypy.NotFound()
    
    # Check if path is a directory.
    if stat.S_ISDIR(st.st_mode):
        # Let the caller deal with it as they like.
        raise cherrypy.NotFound()
    
    # Set the Last-Modified response header, so that
    # modified-since validation code can work.
    response.headers['Last-Modified'] = http.HTTPDate(st.st_mtime)
    cptools.validate_since()
    
    if content_type is None:
        # Set content-type based on filename extension
        ext = ""
        i = path.rfind('.')
        if i != -1:
            ext = path[i:].lower()
        content_type = mimetypes.types_map.get(ext, "text/plain")
    response.headers['Content-Type'] = content_type
    
    if disposition is not None:
        if name is None:
            name = os.path.basename(path)
        cd = '%s; filename="%s"' % (disposition, name)
        response.headers["Content-Disposition"] = cd
    
    # Set Content-Length and use an iterable (file object)
    #   this way CP won't load the whole file in memory
    c_len = st.st_size
    bodyfile = open(path, 'rb')
    
    # HTTP/1.0 didn't have Range/Accept-Ranges headers, or the 206 code
    if cherrypy.request.protocol >= (1, 1):
        response.headers["Accept-Ranges"] = "bytes"
        r = http.get_ranges(cherrypy.request.headers.get('Range'), c_len)
        if r == []:
            response.headers['Content-Range'] = "bytes */%s" % c_len
            message = "Invalid Range (first-byte-pos greater than Content-Length)"
            raise cherrypy.HTTPError(416, message)
        if r:
            if len(r) == 1:
                # Return a single-part response.
                start, stop = r[0]
                r_len = stop - start
                response.status = "206 Partial Content"
                response.headers['Content-Range'] = ("bytes %s-%s/%s" %
                                                       (start, stop - 1, c_len))
                response.headers['Content-Length'] = r_len
                bodyfile.seek(start)
                response.body = bodyfile.read(r_len)
            else:
                # Return a multipart/byteranges response.
                response.status = "206 Partial Content"
                import mimetools
                boundary = mimetools.choose_boundary()
                ct = "multipart/byteranges; boundary=%s" % boundary
                response.headers['Content-Type'] = ct
                if response.headers.has_key("Content-Length"):
                    # Delete Content-Length header so finalize() recalcs it.
                    del response.headers["Content-Length"]
                
                def file_ranges():
                    # Apache compatibility:
                    yield "\r\n"
                    
                    for start, stop in r:
                        yield "--" + boundary
                        yield "\r\nContent-type: %s" % content_type
                        yield ("\r\nContent-range: bytes %s-%s/%s\r\n\r\n"
                               % (start, stop - 1, c_len))
                        bodyfile.seek(start)
                        yield bodyfile.read(stop - start)
                        yield "\r\n"
                    # Final boundary
                    yield "--" + boundary + "--"
                    
                    # Apache compatibility:
                    yield "\r\n"
                response.body = file_ranges()
        else:
            response.headers['Content-Length'] = c_len
            response.body = bodyfile
    else:
        response.headers['Content-Length'] = c_len
        response.body = bodyfile
    return response.body

def serve_download(path, name=None):
    """Serve 'path' as an application/x-download attachment."""
    # This is such a common idiom I felt it deserved its own wrapper.
    return serve_file(path, "application/x-download", "attachment", name)


def _attempt(filename, content_types):
    try:
        # you can set the content types for a
        # complete directory per extension
        content_type = None
        if content_types:
            r, ext = os.path.splitext(filename)
            content_type = content_types.get(ext[1:], None)
        serve_file(filename, content_type=content_type)
        return True
    except cherrypy.NotFound:
        # If we didn't find the static file, continue handling the
        # request. We might find a dynamic handler instead.
        return False

def staticdir(section, dir, root="", match="", content_types=None, index=""):
    """Serve a static resource from the given (root +) dir.
    
    If 'match' is given, request.path_info will be searched for the given
    regular expression before attempting to serve static content.
    
    If content_types is given, it should be a Python dictionary of
    {file-extension: content-type} pairs, where 'file-extension' is
    a string (e.g. "gif") and 'content-type' is the value to write
    out in the Content-Type response header (e.g. "image/gif").
    
    If 'index' is provided, it should be the (relative) name of a file to
    serve for directory requests. For example, if the dir argument is
    '/home/me', the Request-URI is 'myapp', and the index arg is
    'index.html', the file '/home/me/myapp/index.html' will be sought.
    """
    if match and not re.search(match, cherrypy.request.path_info):
        return False
    
    # Allow the use of '~' to refer to a user's home directory.
    dir = os.path.expanduser(dir)

    # If dir is relative, make absolute using "root".
    if not os.path.isabs(dir):
        if not root:
            msg = "Static dir requires an absolute dir (or root)."
            raise ValueError(msg)
        dir = os.path.join(root, dir)
    
    # Determine where we are in the object tree relative to 'section'
    # (where the static tool was defined).
    if section == 'global':
        section = "/"
    section = section.rstrip(r"\/")
    branch = cherrypy.request.path_info[len(section) + 1:]
    branch = urllib.unquote(branch.lstrip(r"\/"))
    
    # If branch is "", filename will end in a slash
    filename = os.path.join(dir, branch)
    
    # There's a chance that the branch pulled from the URL might
    # have ".." or similar uplevel attacks in it. Check that the final
    # filename is a child of dir.
    if not os.path.normpath(filename).startswith(os.path.normpath(dir)):
        raise cherrypy.HTTPError(403) # Forbidden
    
    handled = _attempt(filename, content_types)
    if not handled:
        # Check for an index file if a folder was requested.
        if index:
            handled = _attempt(os.path.join(filename, index), content_types)
            if handled:
                cherrypy.request.is_index = filename[-1] in (r"\/")
    return handled

def staticfile(filename, root=None, match="", content_types=None):
    """Serve a static resource from the given (root +) filename.
    
    If 'match' is given, request.path_info will be searched for the given
    regular expression before attempting to serve static content.
    
    If content_types is given, it should be a Python dictionary of
    {file-extension: content-type} pairs, where 'file-extension' is
    a string (e.g. "gif") and 'content-type' is the value to write
    out in the Content-Type response header (e.g. "image/gif").
    """
    if match and not re.search(match, cherrypy.request.path_info):
        return False
    
    # If filename is relative, make absolute using "root".
    if not os.path.isabs(filename):
        if not root:
            msg = "Static tool requires an absolute filename (got '%s')." % filename
            raise ValueError(msg)
        filename = os.path.join(root, filename)
    
    return _attempt(filename, content_types)
