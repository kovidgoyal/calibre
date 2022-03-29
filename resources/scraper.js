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

    if (!document.location.href.startsWith('chrome-error://')) {
        send_msg({type: 'domready', html: new XMLSerializer().serializeToString(document)}); 
    }
})();
