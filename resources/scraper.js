/* vim:fileencoding=utf-8
 * 
 * Copyright (C) 2022 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPLv3 license
 */


(function() {
    "use strict";

    function send_msg(data) {
        var token = 'TOKEN';
        var msg = token + '  ' + JSON.stringify(data);
        console.log(msg);
    }

    function debug() {
        var args = Array.prototype.slice.call(arguments);
        var text = args.join(' ');
        send_msg({type: 'print', text: text});
    }

    if (document.location && document.location.href && !document.location.href.startsWith('chrome-error:') && !document.location.href.startsWith('about:')) {
        send_msg({type: 'domready', url: document.location.href, html: new XMLSerializer().serializeToString(document)}); 
    }
})();
