// License: GPL v3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>
// Plain-JS template; version/hash placeholders substituted at build time.
// Not compiled via RapydScript: the SW runs in a ServiceWorkerGlobalScope
// where the RapydScript runtime throws during evaluation.
'use strict';

const CACHE_NAME = 'calibre-app-9.6.0-00a03931';

self.addEventListener('install', function(event) {
    event.waitUntil(self.skipWaiting());
});

// Enable Navigation Preload in activate.
//
// A plain fetch() from SW context never carries Digest-auth credentials, so
// it always gets a 401 instead of the 200 we need to cache. Navigation
// Preload lets the browser make the authenticated navigation fetch in parallel
// with SW activation; the result arrives as event.preloadResponse in the fetch
// handler below — already authenticated, ready to cache.
self.addEventListener('activate', function(event) {
    const preloadEnabled = self.registration.navigationPreload
        ? self.registration.navigationPreload.enable()
        : Promise.resolve();
    const cleanup = preloadEnabled.then(function() {
        return caches.keys().then(function(keys) {
            return Promise.all(
                keys.filter(function(k) { return k !== CACHE_NAME; })
                    .map(function(k) { return caches.delete(k); })
            );
        });
    });
    event.waitUntil(cleanup.then(function() { return self.clients.claim(); }));
});

// event.preloadResponse is the browser's own authenticated navigation fetch.
// When present: use it, cache the 200, return it to the page.
// When absent (navigation preload not yet enabled on first install): return
//   without calling event.respondWith() so the browser handles the request
//   normally, including the Digest-auth challenge-response cycle.
// On network error (offline): serve the cached app shell.
self.addEventListener('fetch', function(event) {
    if (event.request.method !== 'GET') return;
    const url = new URL(event.request.url);
    if (url.origin !== self.location.origin) return;
    const service_worker_root = self.location.pathname.substring(0, self.location.pathname.lastIndexOf('/') + 1);
    if (!url.pathname.startsWith(service_worker_root)) return;
    const req_rel_path = url.pathname.replace(service_worker_root, '');
    if (req_rel_path !== '') return;
    if (!event.preloadResponse) return;  // let browser handle unaided on first install

    event.respondWith(
        event.preloadResponse
            .then(function(response) {
                if (response && response.ok) {
                    const cloned = response.clone();
                    caches.open(CACHE_NAME).then(function(cache) {
                        return cache.put(event.request.url, cloned);
                    }).catch(function() {});
                    return response;
                }
                // Unexpected non-OK preload response — prefer cached copy.
                return caches.match(event.request.url).then(function(cached) {
                    return cached || response;
                });
            })
            .catch(function() {
                // Network error: offline — serve the cached app shell.
                return caches.match(event.request.url);
            })
    );
});
