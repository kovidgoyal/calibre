/* vim:fileencoding=utf-8
 *
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPLv3 license
 */
/*jshint esversion: 6 */

(function() {
"use strict";
    // wrap up long words that don't fit in the page
    document.body.style.overflowWrap = 'break-word';

    // Propagate a vertical writing mode from body to the root element,
    // otherwise body is an orthogonal flow inside the root and Chromium >= 134
    // renders content from multiple pages overlapping each other when printing.
    // See https://bugs.launchpad.net/calibre/+bug/2146979
    // This is needed only for Qt 6.10.x it seems to be fixed in Qt 6.11 but is
    // fairly harmless anyway, so kept around.
    var root = document.documentElement;
    var body_wm = window.getComputedStyle(document.body).writingMode;
    if (body_wm !== 'horizontal-tb' && window.getComputedStyle(root).writingMode === 'horizontal-tb') {
        root.style.writingMode = body_wm;
    }

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
