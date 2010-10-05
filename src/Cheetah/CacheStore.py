'''
Provides several CacheStore backends for Cheetah's caching framework.  The
methods provided by these classes have the same semantics as those in the
python-memcached API, except for their return values:

set(key, val, time=0)
  set the value unconditionally
add(key, val, time=0)
  set only if the server doesn't already have this key
replace(key, val, time=0)
  set only if the server already have this key
get(key, val)
  returns val or raises a KeyError
delete(key)
  deletes or raises a KeyError
'''
import time

class Error(Exception):
    pass

class AbstractCacheStore(object):

    def set(self, key, val, time=None):
        raise NotImplementedError

    def add(self, key, val, time=None):
        raise NotImplementedError

    def replace(self, key, val, time=None):
        raise NotImplementedError

    def delete(self, key):
        raise NotImplementedError

    def get(self, key):
        raise NotImplementedError

class MemoryCacheStore(AbstractCacheStore):
    def __init__(self):
        self._data = {}

    def set(self, key, val, time=0):
        self._data[key] = (val, time)

    def add(self, key, val, time=0):
        if key in self._data:
            raise Error('a value for key %r is already in the cache'%key)
        self._data[key] = (val, time)

    def replace(self, key, val, time=0):
        if key in self._data:
            raise Error('a value for key %r is already in the cache'%key)
        self._data[key] = (val, time)

    def delete(self, key):
        del self._data[key]
        
    def get(self, key):
        (val, exptime) = self._data[key]
        if exptime and time.time() > exptime:
            del self._data[key]
            raise KeyError(key)
        else:
            return val

    def clear(self):
        self._data.clear()        
                  
class MemcachedCacheStore(AbstractCacheStore):
    servers = ('127.0.0.1:11211')
    def __init__(self, servers=None, debug=False):
        if servers is None:
            servers = self.servers
        from memcache import Client as MemcachedClient
        self._client = MemcachedClient(servers, debug)

    def set(self, key, val, time=0):
        self._client.set(key, val, time)

    def add(self, key, val, time=0):
        res = self._client.add(key, val, time)        
        if not res:
            raise Error('a value for key %r is already in the cache'%key)
        self._data[key] = (val, time)

    def replace(self, key, val, time=0):
        res = self._client.replace(key, val, time)        
        if not res:
            raise Error('a value for key %r is already in the cache'%key)
        self._data[key] = (val, time)

    def delete(self, key):
        res = self._client.delete(key, time=0)        
        if not res:
            raise KeyError(key)
        
    def get(self, key):
        val = self._client.get(key)
        if val is None:
            raise KeyError(key)
        else:
            return val

    def clear(self):
        self._client.flush_all()        
