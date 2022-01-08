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

    var break_avoid_block_styles = {
        "run-in":1, "block":1, "table-row-group":1, "table-column":1, "table-column-group":1,
        "table-header-group":1, "table-footer-group":1, "table-row":1, "table-cell":1,
        "table-caption":1, // page-break-avoid does not work for inline-block either
    };

    function avoid_page_breaks_inside(node) {
        node.style.pageBreakInside = 'avoid';
        node.style.breakInside = 'avoid';
    }

    for (const img of document.images) {
        var style = window.getComputedStyle(img);
        if (style.maxHeight === 'none') img.style.maxHeight = '100vh';
        if (style.maxWidth === 'none') img.style.maxWidth = '100vw';

        var is_block = break_avoid_block_styles[style.display];
        if (is_block) avoid_page_breaks_inside(img);
        else if (img.parentNode && img.parentNode.childElementCount === 1) avoid_page_breaks_inside(img.parentNode);
    }
    // Change the hyphenate character to a plain ASCII minus (U+002d) the default
    // is U+2010 but that does not render with the default Times font on macOS as of Monterey
    // and Qt 15.5 See https://bugs.launchpad.net/bugs/1951467 and can be easily reproduced
    // by converting a plain text file with the --pdf-hyphenate option
    // https://bugs.chromium.org/p/chromium/issues/detail?id=1267606 (fix released Feb 1 2022 v98)
    // See also settings.pyj
    if (HYPHEN_CHAR) {
        for (const elem of document.getElementsByTagName('*')) {
            if (elem.style) {
                elem.style.setProperty('-webkit-hyphenate-character', '"-"', 'important');
            }
        }
    }
})();


