/* vim:fileencoding=utf-8
 * 
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPLv3 license
 */
/*jshint esversion: 6 */

(function() {
"use strict";
    // wrap up long words that dont fit in the page
    document.body.style.overflowWrap = 'break-word';

    var block_styles = {
        "run-in":1, "block":1, "table-row-group":1, "table-column":1, "table-column-group":1,
        "table-header-group":1, "table-footer-group":1, "table-row":1, "table-cell":1,
        "table-caption":1, "inline-block:":1
    };
    for (const img of document.images) {
        var style = window.getComputedStyle(img);
        if (style.maxHeight === 'none') img.style.maxHeight = '100vh';
        if (style.maxWidth === 'none') img.style.maxWidth = '100vw';
        if (block_styles[style.display]) {
            img.style.pageBreakInside = 'avoid';
            img.style.breakInside = 'avoid';
        }
    }

})();


