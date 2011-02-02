/*
 * bookmarks management
 * Copyright 2008 Kovid Goyal
 * License: GNU GPL v3
 */

function selector_in_parent(elem) {
    var num = elem.prevAll().length;
    var sel = " > *:eq("+num+") ";
    return sel;
}

function selector(elem) {
    var obj = elem;
    var sel = "";
    while (obj[0] != document) {
        sel = selector_in_parent(obj) + sel;
        obj = obj.parent();
    }
    if (sel.length > 2  && sel.charAt(1) == ">") sel = sel.substring(2);
    return sel;
}

function calculate_bookmark(y, node) {
    var elem = $(node);
    var sel = selector(elem);
    var ratio = (y - elem.offset().top)/elem.height();
    if (ratio > 1) { ratio = 1; }
    if (ratio < 0) { ratio = 0; }
    sel = sel + "|" + ratio;
    return sel;
}

function animated_scrolling_done() {
    window.py_bridge.animated_scroll_done();
}

function scroll_to_bookmark(bookmark) {
    bm = bookmark.split("|");
    var ratio = 0.7 * parseFloat(bm[1]);
    $.scrollTo($(bm[0]), 1000,
        {
            over:ratio,
            axis: 'y', // Do not scroll in the x direction
            onAfter:function(){window.py_bridge.animated_scroll_done()}
        }
    );
}

