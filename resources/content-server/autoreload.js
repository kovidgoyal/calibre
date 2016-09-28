/* vim:fileencoding=utf-8
 * 
 * Copyright (C) 2015 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPLv3 license
 */

(function(autoreload_port) {
    "use strict";
    var host = document.location.host.split(':')[0];
    var url = 'ws://' + host + ':' + autoreload_port;
    var MAX_RETRIES = 10;

    function ReconnectingWebSocket() {
        self = this;
        self.retries = 0;
        self.interval = 100;
        self.disable = false;
        self.opened_at_least_once = false;

        self.reconnect = function() {
            self.ws = new WebSocket(url);

            self.ws.onopen = function(event) {
                self.retries = 0;
                self.opened_at_least_once = true;
                self.interval = 100;
                console.log('Connected to reloading WebSocket server at: ' + url);
                window.addEventListener('beforeunload', function (event) {
                    console.log('Shutting down connection to reload server, before page unload');
                    self.disable = true;
                    self.ws.close();
                });
            };

            self.ws.onmessage = function(event) {
                if (event.data !== 'ping') console.log('Received mesasge from reload server: ' + event.data);
                if (event.data === 'reload') window.location.reload(true);
            };

            self.ws.onclose = function(event) {
                if (self.disable || !self.opened_at_least_once) return;
                console.log('Connection to reload server closed with code: ' + event.code + ' and reason: ' + event.reason);
                self.retries += 1;
                if (self.retries < MAX_RETRIES) {
                    setTimeout(self.reconnect, self.interval);
                } else window.location.reload(true);
            };
        };
        self.reconnect();
    }

    var sock = new ReconnectingWebSocket();
})(AUTORELOAD_PORT);

