/*
 * bookmarks management
 * Copyright 2008 Kovid Goyal
 * License: GNU GPL v3
 */

function init_hyphenate() {
    window.py_bridge.init_hyphenate();
}

document.addEventListener("DOMContentLoaded", init_hyphenate, false);

function do_hyphenation(lang) {
    Hyphenator.config(
        {
        'minwordlength'    : 6,
        //'hyphenchar'     : '|',
        'displaytogglebox' : false,
        'remoteloading'    : false,
        'onerrorhandler'   : function (e) {
                                window.py_bridge.debug(e);
                            }
        });
    Hyphenator.hyphenate(document.body, lang);
}

