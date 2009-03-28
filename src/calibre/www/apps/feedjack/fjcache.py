# -*- coding: utf-8 -*-

"""
feedjack
Gustavo Picón
fjcache.py
"""

import md5

from django.core.cache import cache

from django.conf import settings


T_HOST = 1
T_ITEM = 2
T_META = 3


def str2md5(key):
    """ Returns the md5 hash of a string.
    """
    ctx = md5.new()
    ctx.update(key.encode('utf-8'))
    return ctx.hexdigest()

def getkey(stype, site_id=None, key=None):
    """ Returns the cache key depending on it's type.
    """
    base = '%s.feedjack' % (settings.CACHE_MIDDLEWARE_KEY_PREFIX)
    if stype == T_HOST:
        return '%s.hostcache' % base
    elif stype == T_ITEM:
        return '%s.%d.item.%s' % (base, site_id, str2md5(key))
    elif stype == T_META:
        return '%s.%d.meta' % (base, site_id)


def hostcache_get():
    """ Retrieves the hostcache dictionary
    """
    return cache.get(getkey(T_HOST))

def hostcache_set(value):
    """ Sets the hostcache dictionary
    """
    cache.set(getkey(T_HOST), value)

def cache_get(site_id, key):
    """ Retrieves cache data from a site.
    """
    return cache.get(getkey(T_ITEM, site_id, key))

def cache_set(site, key, data):
    """ Sets cache data for a site.
    
    All keys related to a site are stored in a meta key. This key is per-site.
    """
    tkey = getkey(T_ITEM, site.id, key)
    mkey = getkey(T_META, site.id)
    tmp = cache.get(mkey)
    longdur = 365*24*60*60
    if not tmp:
        tmp = [tkey]
        cache.set(mkey, [tkey], longdur)
    elif tkey not in tmp:
        tmp.append(tkey)
        cache.set(mkey, tmp, longdur)
    cache.set(tkey, data, site.cache_duration)

def cache_delsite(site_id):
    """ Removes all cache data from a site.
    """
    mkey = getkey(T_META, site_id)
    tmp = cache.get(mkey)
    if not tmp:
        return
    for tkey in tmp:
        cache.delete(tkey)
    cache.delete(mkey)


