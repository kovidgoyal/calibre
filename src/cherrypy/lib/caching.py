"""
CherryPy implements a simple caching system as a pluggable Tool. This tool tries
to be an (in-process) HTTP/1.1-compliant cache. It's not quite there yet, but
it's probably good enough for most sites.

In general, GET responses are cached (along with selecting headers) and, if
another request arrives for the same resource, the caching Tool will return 304
Not Modified if possible, or serve the cached response otherwise. It also sets
request.cached to True if serving a cached representation, and sets
request.cacheable to False (so it doesn't get cached again).

If POST, PUT, or DELETE requests are made for a cached resource, they invalidate
(delete) any cached response.

Usage
=====

Configuration file example::

    [/]
    tools.caching.on = True
    tools.caching.delay = 3600

You may use a class other than the default
:class:`MemoryCache<cherrypy.lib.caching.MemoryCache>` by supplying the config
entry ``cache_class``; supply the full dotted name of the replacement class
as the config value. It must implement the basic methods ``get``, ``put``,
``delete``, and ``clear``.

You may set any attribute, including overriding methods, on the cache
instance by providing them in config. The above sets the
:attr:`delay<cherrypy.lib.caching.MemoryCache.delay>` attribute, for example.
"""

import datetime
import sys
import threading
import time

import cherrypy
from cherrypy.lib import cptools, httputil
from cherrypy._cpcompat import copyitems, ntob, set_daemon, sorted


class Cache(object):
    """Base class for Cache implementations."""
    
    def get(self):
        """Return the current variant if in the cache, else None."""
        raise NotImplemented
    
    def put(self, obj, size):
        """Store the current variant in the cache."""
        raise NotImplemented
    
    def delete(self):
        """Remove ALL cached variants of the current resource."""
        raise NotImplemented
    
    def clear(self):
        """Reset the cache to its initial, empty state."""
        raise NotImplemented



# ------------------------------- Memory Cache ------------------------------- #


class AntiStampedeCache(dict):
    """A storage system for cached items which reduces stampede collisions."""
    
    def wait(self, key, timeout=5, debug=False):
        """Return the cached value for the given key, or None.
        
        If timeout is not None, and the value is already
        being calculated by another thread, wait until the given timeout has
        elapsed. If the value is available before the timeout expires, it is
        returned. If not, None is returned, and a sentinel placed in the cache
        to signal other threads to wait.
        
        If timeout is None, no waiting is performed nor sentinels used.
        """
        value = self.get(key)
        if isinstance(value, threading._Event):
            if timeout is None:
                # Ignore the other thread and recalc it ourselves.
                if debug:
                    cherrypy.log('No timeout', 'TOOLS.CACHING')
                return None
            
            # Wait until it's done or times out.
            if debug:
                cherrypy.log('Waiting up to %s seconds' % timeout, 'TOOLS.CACHING')
            value.wait(timeout)
            if value.result is not None:
                # The other thread finished its calculation. Use it.
                if debug:
                    cherrypy.log('Result!', 'TOOLS.CACHING')
                return value.result
            # Timed out. Stick an Event in the slot so other threads wait
            # on this one to finish calculating the value.
            if debug:
                cherrypy.log('Timed out', 'TOOLS.CACHING')
            e = threading.Event()
            e.result = None
            dict.__setitem__(self, key, e)
            
            return None
        elif value is None:
            # Stick an Event in the slot so other threads wait
            # on this one to finish calculating the value.
            if debug:
                cherrypy.log('Timed out', 'TOOLS.CACHING')
            e = threading.Event()
            e.result = None
            dict.__setitem__(self, key, e)
        return value
    
    def __setitem__(self, key, value):
        """Set the cached value for the given key."""
        existing = self.get(key)
        dict.__setitem__(self, key, value)
        if isinstance(existing, threading._Event):
            # Set Event.result so other threads waiting on it have
            # immediate access without needing to poll the cache again.
            existing.result = value
            existing.set()


class MemoryCache(Cache):
    """An in-memory cache for varying response content.
    
    Each key in self.store is a URI, and each value is an AntiStampedeCache.
    The response for any given URI may vary based on the values of
    "selecting request headers"; that is, those named in the Vary
    response header. We assume the list of header names to be constant
    for each URI throughout the lifetime of the application, and store
    that list in ``self.store[uri].selecting_headers``.
    
    The items contained in ``self.store[uri]`` have keys which are tuples of
    request header values (in the same order as the names in its
    selecting_headers), and values which are the actual responses.
    """
    
    maxobjects = 1000
    """The maximum number of cached objects; defaults to 1000."""
    
    maxobj_size = 100000
    """The maximum size of each cached object in bytes; defaults to 100 KB."""
    
    maxsize = 10000000
    """The maximum size of the entire cache in bytes; defaults to 10 MB."""
    
    delay = 600
    """Seconds until the cached content expires; defaults to 600 (10 minutes)."""
    
    antistampede_timeout = 5
    """Seconds to wait for other threads to release a cache lock."""
    
    expire_freq = 0.1
    """Seconds to sleep between cache expiration sweeps."""
    
    debug = False
    
    def __init__(self):
        self.clear()
        
        # Run self.expire_cache in a separate daemon thread.
        t = threading.Thread(target=self.expire_cache, name='expire_cache')
        self.expiration_thread = t
        set_daemon(t, True)
        t.start()
    
    def clear(self):
        """Reset the cache to its initial, empty state."""
        self.store = {}
        self.expirations = {}
        self.tot_puts = 0
        self.tot_gets = 0
        self.tot_hist = 0
        self.tot_expires = 0
        self.tot_non_modified = 0
        self.cursize = 0
    
    def expire_cache(self):
        """Continuously examine cached objects, expiring stale ones.
        
        This function is designed to be run in its own daemon thread,
        referenced at ``self.expiration_thread``.
        """
        # It's possible that "time" will be set to None
        # arbitrarily, so we check "while time" to avoid exceptions.
        # See tickets #99 and #180 for more information.
        while time:
            now = time.time()
            # Must make a copy of expirations so it doesn't change size
            # during iteration
            for expiration_time, objects in copyitems(self.expirations):
                if expiration_time <= now:
                    for obj_size, uri, sel_header_values in objects:
                        try:
                            del self.store[uri][tuple(sel_header_values)]
                            self.tot_expires += 1
                            self.cursize -= obj_size
                        except KeyError:
                            # the key may have been deleted elsewhere
                            pass
                    del self.expirations[expiration_time]
            time.sleep(self.expire_freq)
    
    def get(self):
        """Return the current variant if in the cache, else None."""
        request = cherrypy.serving.request
        self.tot_gets += 1
        
        uri = cherrypy.url(qs=request.query_string)
        uricache = self.store.get(uri)
        if uricache is None:
            return None
        
        header_values = [request.headers.get(h, '')
                         for h in uricache.selecting_headers]
        variant = uricache.wait(key=tuple(sorted(header_values)),
                                timeout=self.antistampede_timeout,
                                debug=self.debug)
        if variant is not None:
            self.tot_hist += 1
        return variant
    
    def put(self, variant, size):
        """Store the current variant in the cache."""
        request = cherrypy.serving.request
        response = cherrypy.serving.response
        
        uri = cherrypy.url(qs=request.query_string)
        uricache = self.store.get(uri)
        if uricache is None:
            uricache = AntiStampedeCache()
            uricache.selecting_headers = [
                e.value for e in response.headers.elements('Vary')]
            self.store[uri] = uricache
        
        if len(self.store) < self.maxobjects:
            total_size = self.cursize + size
            
            # checks if there's space for the object
            if (size < self.maxobj_size and total_size < self.maxsize):
                # add to the expirations list
                expiration_time = response.time + self.delay
                bucket = self.expirations.setdefault(expiration_time, [])
                bucket.append((size, uri, uricache.selecting_headers))
                
                # add to the cache
                header_values = [request.headers.get(h, '')
                                 for h in uricache.selecting_headers]
                uricache[tuple(sorted(header_values))] = variant
                self.tot_puts += 1
                self.cursize = total_size
    
    def delete(self):
        """Remove ALL cached variants of the current resource."""
        uri = cherrypy.url(qs=cherrypy.serving.request.query_string)
        self.store.pop(uri, None)


def get(invalid_methods=("POST", "PUT", "DELETE"), debug=False, **kwargs):
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
    request = cherrypy.serving.request
    response = cherrypy.serving.response
    
    if not hasattr(cherrypy, "_cache"):
        # Make a process-wide Cache object.
        cherrypy._cache = kwargs.pop("cache_class", MemoryCache)()
        
        # Take all remaining kwargs and set them on the Cache object.
        for k, v in kwargs.items():
            setattr(cherrypy._cache, k, v)
        cherrypy._cache.debug = debug
    
    # POST, PUT, DELETE should invalidate (delete) the cached copy.
    # See http://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html#sec13.10.
    if request.method in invalid_methods:
        if debug:
            cherrypy.log('request.method %r in invalid_methods %r' %
                         (request.method, invalid_methods), 'TOOLS.CACHING')
        cherrypy._cache.delete()
        request.cached = False
        request.cacheable = False
        return False
    
    if 'no-cache' in [e.value for e in request.headers.elements('Pragma')]:
        request.cached = False
        request.cacheable = True
        return False
    
    cache_data = cherrypy._cache.get()
    request.cached = bool(cache_data)
    request.cacheable = not request.cached
    if request.cached:
        # Serve the cached copy.
        max_age = cherrypy._cache.delay
        for v in [e.value for e in request.headers.elements('Cache-Control')]:
            atoms = v.split('=', 1)
            directive = atoms.pop(0)
            if directive == 'max-age':
                if len(atoms) != 1 or not atoms[0].isdigit():
                    raise cherrypy.HTTPError(400, "Invalid Cache-Control header")
                max_age = int(atoms[0])
                break
            elif directive == 'no-cache':
                if debug:
                    cherrypy.log('Ignoring cache due to Cache-Control: no-cache',
                                 'TOOLS.CACHING')
                request.cached = False
                request.cacheable = True
                return False
        
        if debug:
            cherrypy.log('Reading response from cache', 'TOOLS.CACHING')
        s, h, b, create_time = cache_data
        age = int(response.time - create_time)
        if (age > max_age):
            if debug:
                cherrypy.log('Ignoring cache due to age > %d' % max_age,
                             'TOOLS.CACHING')
            request.cached = False
            request.cacheable = True
            return False
        
        # Copy the response headers. See http://www.cherrypy.org/ticket/721.
        response.headers = rh = httputil.HeaderMap()
        for k in h:
            dict.__setitem__(rh, k, dict.__getitem__(h, k))
        
        # Add the required Age header
        response.headers["Age"] = str(age)
        
        try:
            # Note that validate_since depends on a Last-Modified header;
            # this was put into the cached copy, and should have been
            # resurrected just above (response.headers = cache_data[1]).
            cptools.validate_since()
        except cherrypy.HTTPRedirect:
            x = sys.exc_info()[1]
            if x.status == 304:
                cherrypy._cache.tot_non_modified += 1
            raise
        
        # serve it & get out from the request
        response.status = s
        response.body = b
    else:
        if debug:
            cherrypy.log('request is not cached', 'TOOLS.CACHING')
    return request.cached


def tee_output():
    """Tee response output to cache storage. Internal."""
    # Used by CachingTool by attaching to request.hooks
    
    request = cherrypy.serving.request
    if 'no-store' in request.headers.values('Cache-Control'):
        return
    
    def tee(body):
        """Tee response.body into a list."""
        if ('no-cache' in response.headers.values('Pragma') or
            'no-store' in response.headers.values('Cache-Control')):
            for chunk in body:
                yield chunk
            return
        
        output = []
        for chunk in body:
            output.append(chunk)
            yield chunk
        
        # save the cache data
        body = ntob('').join(output)
        cherrypy._cache.put((response.status, response.headers or {},
                             body, response.time), len(body))
    
    response = cherrypy.serving.response
    response.body = tee(response.body)


def expires(secs=0, force=False, debug=False):
    """Tool for influencing cache mechanisms using the 'Expires' header.

    secs
        Must be either an int or a datetime.timedelta, and indicates the
        number of seconds between response.time and when the response should
        expire. The 'Expires' header will be set to response.time + secs.
        If secs is zero, the 'Expires' header is set one year in the past, and
        the following "cache prevention" headers are also set:
        
            * Pragma: no-cache
            * Cache-Control': no-cache, must-revalidate

    force
        If False, the following headers are checked:
        
            * Etag
            * Last-Modified
            * Age
            * Expires
        
        If any are already present, none of the above response headers are set.
    
    """
    
    response = cherrypy.serving.response
    headers = response.headers
    
    cacheable = False
    if not force:
        # some header names that indicate that the response can be cached
        for indicator in ('Etag', 'Last-Modified', 'Age', 'Expires'):
            if indicator in headers:
                cacheable = True
                break
    
    if not cacheable and not force:
        if debug:
            cherrypy.log('request is not cacheable', 'TOOLS.EXPIRES')
    else:
        if debug:
            cherrypy.log('request is cacheable', 'TOOLS.EXPIRES')
        if isinstance(secs, datetime.timedelta):
            secs = (86400 * secs.days) + secs.seconds
        
        if secs == 0:
            if force or ("Pragma" not in headers):
                headers["Pragma"] = "no-cache"
            if cherrypy.serving.request.protocol >= (1, 1):
                if force or "Cache-Control" not in headers:
                    headers["Cache-Control"] = "no-cache, must-revalidate"
            # Set an explicit Expires date in the past.
            expiry = httputil.HTTPDate(1169942400.0)
        else:
            expiry = httputil.HTTPDate(response.time + secs)
        if force or "Expires" not in headers:
            headers["Expires"] = expiry
