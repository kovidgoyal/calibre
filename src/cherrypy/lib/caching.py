import datetime
import threading
import time

import cherrypy
from cherrypy.lib import cptools, http


class MemoryCache:
    
    maxobjects = 1000
    maxobj_size = 100000
    maxsize = 10000000
    delay = 600
    
    def __init__(self):
        self.clear()
        t = threading.Thread(target=self.expire_cache, name='expire_cache')
        self.expiration_thread = t
        t.setDaemon(True)
        t.start()
    
    def clear(self):
        """Reset the cache to its initial, empty state."""
        self.cache = {}
        self.expirations = {}
        self.tot_puts = 0
        self.tot_gets = 0
        self.tot_hist = 0
        self.tot_expires = 0
        self.tot_non_modified = 0
        self.cursize = 0
    
    def key(self):
        return cherrypy.url(qs=cherrypy.request.query_string)
    
    def expire_cache(self):
        # expire_cache runs in a separate thread which the servers are
        # not aware of. It's possible that "time" will be set to None
        # arbitrarily, so we check "while time" to avoid exceptions.
        # See tickets #99 and #180 for more information.
        while time:
            now = time.time()
            for expiration_time, objects in self.expirations.items():
                if expiration_time <= now:
                    for obj_size, obj_key in objects:
                        try:
                            del self.cache[obj_key]
                            self.tot_expires += 1
                            self.cursize -= obj_size
                        except KeyError:
                            # the key may have been deleted elsewhere
                            pass
                    del self.expirations[expiration_time]
            time.sleep(0.1)
    
    def get(self):
        """Return the object if in the cache, else None."""
        self.tot_gets += 1
        cache_item = self.cache.get(self.key(), None)
        if cache_item:
            self.tot_hist += 1
            return cache_item
        else:
            return None
    
    def put(self, obj):
        if len(self.cache) < self.maxobjects:
            # Size check no longer includes header length
            obj_size = len(obj[2])
            total_size = self.cursize + obj_size
            
            # checks if there's space for the object
            if (obj_size < self.maxobj_size and total_size < self.maxsize):
                # add to the expirations list and cache
                expiration_time = cherrypy.response.time + self.delay
                obj_key = self.key()
                bucket = self.expirations.setdefault(expiration_time, [])
                bucket.append((obj_size, obj_key))
                self.cache[obj_key] = obj
                self.tot_puts += 1
                self.cursize = total_size
    
    def delete(self):
        self.cache.pop(self.key(), None)


def get(invalid_methods=("POST", "PUT", "DELETE"), **kwargs):
    """Try to obtain cached output. If fresh enough, raise HTTPError(304).
    
    If POST, PUT, or DELETE:
        * invalidates (deletes) any cached response for this resource
        * sets request.cached = False
        * sets request.cacheable = False
    
    else if a cached copy exists:
        * sets request.cached = True
        * sets request.cacheable = False
        * sets response.headers to the cached values
        * checks the cached Last-Modified response header against the
            current If-(Un)Modified-Since request headers; raises 304
            if necessary.
        * sets response.status and response.body to the cached values
        * returns True
    
    otherwise:
        * sets request.cached = False
        * sets request.cacheable = True
        * returns False
    """
    request = cherrypy.request
    
    # POST, PUT, DELETE should invalidate (delete) the cached copy.
    # See http://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html#sec13.10.
    if request.method in invalid_methods:
        cherrypy._cache.delete()
        request.cached = False
        request.cacheable = False
        return False
    
    cache_data = cherrypy._cache.get()
    request.cached = c = bool(cache_data)
    request.cacheable = not c
    if c:
        response = cherrypy.response
        s, h, b, create_time, original_req_headers = cache_data
        
        # Check 'Vary' selecting headers. If any headers mentioned in "Vary"
        # differ between the cached and current request, bail out and
        # let the rest of CP handle the request. This should properly
        # mimic the behavior of isolated caches as RFC 2616 assumes:
        # "If the selecting request header fields for the cached entry
        # do not match the selecting request header fields of the new
        # request, then the cache MUST NOT use a cached entry to satisfy
        # the request unless it first relays the new request to the origin
        # server in a conditional request and the server responds with
        # 304 (Not Modified), including an entity tag or Content-Location
        # that indicates the entity to be used.
        # TODO: can we store multiple variants based on Vary'd headers?
        for header_element in h.elements('Vary'):
            key = header_element.value
            if original_req_headers[key] != request.headers.get(key, 'missing'):
                request.cached = False
                request.cacheable = True
                return False
        
        # Copy the response headers. See http://www.cherrypy.org/ticket/721.
        response.headers = rh = http.HeaderMap()
        for k in h:
            dict.__setitem__(rh, k, dict.__getitem__(h, k))
        
        # Add the required Age header
        response.headers["Age"] = str(int(response.time - create_time))
        
        try:
            # Note that validate_since depends on a Last-Modified header;
            # this was put into the cached copy, and should have been
            # resurrected just above (response.headers = cache_data[1]).
            cptools.validate_since()
        except cherrypy.HTTPRedirect, x:
            if x.status == 304:
                cherrypy._cache.tot_non_modified += 1
            raise
        
        # serve it & get out from the request
        response.status = s
        response.body = b
    return c


def tee_output():
    def tee(body):
        """Tee response.body into a list."""
        output = []
        for chunk in body:
            output.append(chunk)
            yield chunk
        
        # Might as well do this here; why cache if the body isn't consumed?
        if response.headers.get('Pragma', None) != 'no-cache':
            # save the cache data
            body = ''.join(output)
            vary = [he.value for he in
                    cherrypy.response.headers.elements('Vary')]
            if vary:
                sel_headers = dict([(k, v) for k, v
                                    in cherrypy.request.headers.iteritems()
                                    if k in vary])
            else:
                sel_headers = {}
            cherrypy._cache.put((response.status, response.headers or {},
                                 body, response.time, sel_headers))
    
    response = cherrypy.response
    response.body = tee(response.body)


def expires(secs=0, force=False):
    """Tool for influencing cache mechanisms using the 'Expires' header.
    
    'secs' must be either an int or a datetime.timedelta, and indicates the
    number of seconds between response.time and when the response should
    expire. The 'Expires' header will be set to (response.time + secs).
    
    If 'secs' is zero, the 'Expires' header is set one year in the past, and
    the following "cache prevention" headers are also set:
       'Pragma': 'no-cache'
       'Cache-Control': 'no-cache, must-revalidate'
    
    If 'force' is False (the default), the following headers are checked:
    'Etag', 'Last-Modified', 'Age', 'Expires'. If any are already present,
    none of the above response headers are set.
    """
    
    response = cherrypy.response
    headers = response.headers
    
    cacheable = False
    if not force:
        # some header names that indicate that the response can be cached
        for indicator in ('Etag', 'Last-Modified', 'Age', 'Expires'):
            if indicator in headers:
                cacheable = True
                break
    
    if not cacheable:
        if isinstance(secs, datetime.timedelta):
            secs = (86400 * secs.days) + secs.seconds
        
        if secs == 0:
            if force or "Pragma" not in headers:
                headers["Pragma"] = "no-cache"
            if cherrypy.request.protocol >= (1, 1):
                if force or "Cache-Control" not in headers:
                    headers["Cache-Control"] = "no-cache, must-revalidate"
            # Set an explicit Expires date in the past.
            expiry = http.HTTPDate(1169942400.0)
        else:
            expiry = http.HTTPDate(response.time + secs)
        if force or "Expires" not in headers:
            headers["Expires"] = expiry
