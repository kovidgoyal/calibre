// License: GPL v3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>
// This file is a plain-JS template with version/hash placeholders substituted
// by compile_service_worker() via set_data() at build time.
// It is intentionally NOT compiled via RapydScript: the SW runs in a
// ServiceWorkerGlobalScope where the RapydScript runtime throws on evaluation.
'use strict';

var CACHE_NAME = 'calibre-app-__CALIBRE_VERSION__-__CACHE_HASH__';

// No pre-caching in install: cache.addAll(['/']) would make a bare fetch()
// that cannot replay the server's Digest-auth challenge and would always get
// a 401, causing the install event to fail.  The fetch handler below caches
// the authenticated response on the first successful navigation instead.
self.addEventListener('install', function(event) {
    event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', function(event) {
    event.waitUntil(
        caches.keys().then(function(keys) {
            return Promise.all(
                keys.filter(function(key) { return key !== CACHE_NAME; })
                    .map(function(key) { return caches.delete(key); })
            );
        }).then(function() {
            return self.clients.claim();
        })
    );
});

// Network-first for /: navigation fetches go through the browser's full auth
// stack so the Digest challenge is replayed and the SW receives a 200.  Cache
// it so the next offline load is served from cache.  Every online load also
// refreshes the cache automatically.
self.addEventListener('fetch', function(event) {
    if (event.request.method !== 'GET') return;
    var url = new URL(event.request.url);
    if (url.origin !== self.location.origin) return;
    if (url.pathname !== '/') return;
    event.respondWith(
        fetch(event.request).then(function(response) {
            if (response.ok) {
                caches.open(CACHE_NAME).then(function(cache) {
                    cache.put(event.request.url, response.clone());
                });
            }
            return response;
        }).catch(function() {
            return caches.match(event.request.url);
        })
    );
});
