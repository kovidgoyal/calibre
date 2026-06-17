// License: GPL v3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>
// Plain-JS template; version/hash placeholders substituted at serve time.
// Not compiled via RapydScript: the SW runs in a ServiceWorkerGlobalScope
// where the RapydScript runtime throws during evaluation.
'use strict';

const CACHE_NAME = 'calibre-server-index';

self.addEventListener('install', function(event) {
    event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', function(event) {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', function(event) {
    if (event.request.method !== 'GET') return;
    const url = new URL(event.request.url);
    if (url.origin !== self.location.origin) return;
    // console.log("URL: " + event.request.url);
    const service_worker_root = self.location.pathname.substring(0, self.location.pathname.lastIndexOf('/') + 1);
    // console.log("Root: " + service_worker_root);
    if (!url.pathname.startsWith(service_worker_root)) return;
    const req_rel_path = url.pathname.replace(service_worker_root, '');
    // console.log("Relpath: " + req_rel_path);
    if (req_rel_path !== '') return;

    event.respondWith(
        fetch(event.request)
        .then((response) => {
            if (response.ok) {
                // Network succeeded — update the cache and return the response
                const clone = response.clone();
                caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
            }
            return response;
        })
        .catch((err) => {
            // Network failed — serve from cache
            const OFFLINE_RESPONSE = new Response(
                'Failed to contact server and no cached offline version present.' +
                ' Error from contacting server:\n\n' + `${err}`, {
                    status: 200, headers: { 'Content-Type': 'text/plain' },
            });
            return caches.match(event.request)
                .then((cached) => cached || OFFLINE_RESPONSE)
                .catch(() => OFFLINE_RESPONSE);
        })
    );
});
