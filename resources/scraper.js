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

    function debug() {
        var args = Array.prototype.slice.call(arguments);
        var text = args.join(' ');
        send_msg({type: 'print', text: text});
    }

    function notify_that_messages_are_available() {
        send_msg({type: 'messages_available', count: messages.length});
    }

    async function download(req, data) {
        try {
            const controller = new AbortController();
            var fetch_options = {
                method: req.method.toUpperCase(),
                signal: controller.signal,
            };
            const response = await fetch(req.url, fetch_options);
            var headers = [];
            for (const pair of response.headers) {
                headers.push(pair);
            }
            const body = await response.arrayBuffer();
            delete live_requests[req.id];
            messages.push({type: 'finished', req: req, status_code: response.status, status_msg: response.statusText, url: response.url, headers: headers, type: response.type, body: body});
            notify_that_messages_are_available();
        } catch (error) {
            messages.push({type: 'finished', error: error.message, req: req, url: req.url});
            notify_that_messages_are_available();
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

    const payload = JSON.parse(document.getElementById('payload').textContent);
    window.get_messages = get_messages;
    window.abort_download = abort_download;
    download(payload.req, payload.data);
})();
