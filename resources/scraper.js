/* vim:fileencoding=utf-8
 *
 * Copyright (C) 2022 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPLv3 license
 */


(function() {
    "use strict";

    var messages = [];
    var live_requests = {};

    function send_msg(data) {
        const token = 'TOKEN';
        const msg = token + '  ' + JSON.stringify(data);
        console.log(msg);
    }

    function notify_that_messages_are_available() {
        send_msg({type: 'messages_available', count: messages.length});
    }

    function notify(type, msg) {
        msg.type = type;
        messages.push(msg);
        notify_that_messages_are_available();
    }

    async function* stream_to_async_iterable(stream) {
        const reader = stream.getReader()
        try {
            while (true) {
                const {done, value} = await reader.read()
                if (done) return
                yield value
            }
        } finally {
            reader.releaseLock()
        }
    }

    async function download(req, data) {
        try {
            const controller = new AbortController();
            live_requests[req.id] = controller;
            var fetch_options = {
                method: req.method.toUpperCase(),
                signal: controller.signal,
            };
            const response = await fetch(req.url, fetch_options);
            var headers = [];
            for (const pair of response.headers) {
                headers.push(pair);
            }
            notify('metadata_received', {
                status_code: response.status, status_msg: response.statusText,
                url: response.url, headers: headers, response_type: response.type,
            })
            for await (const chunk of stream_to_async_iterable(response.body)) {
                notify('chunk_received', {chunk: chunk})
            }
            delete live_requests[req.id];
            notify('finished', {})
        } catch (error) {
            notify('error', {error: error.message});
        }
    }

    function abort_download(req_id) {
        var controller = live_requests[req_id];
        if (controller) {
            controller.abort();
            return true;
        }
        return false;
    }

    function get_messages() {
        var ans = messages;
        messages = [];
        return ans;
    }

    window.get_messages = get_messages;
    window.abort_download = abort_download;
    const payload = JSON.parse(document.getElementById('payload').textContent);
    download(payload.req, payload.data);
})();
