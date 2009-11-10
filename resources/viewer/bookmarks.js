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
    return sel;
}

function find_closest_enclosing_block(top) {
    var START = top-1000;
    var STOP = top;
    var matches = [];
    var elem, temp;
    var width = 1000;

    for (y = START; y < STOP; y += 20) {
        for ( x = 0; x < width; x += 20) {
            elem = document.elementFromPoint(x, y);
            try {
                elem = $(elem);
                temp = elem.offset().top
                matches.push(elem);
                if (Math.abs(temp - START) < 25) { y = STOP; break}
            } catch(error) {}
        }
    }

    var miny = Math.abs(matches[0].offset().top - START), min_elem = matches[0];

    for (i = 1; i < matches.length; i++) {
        elem = matches[i];
        temp = Math.abs(elem.offset().top - START);
        if ( temp < miny ) { miny = temp; min_elem = elem; }
    }
    return min_elem;
}

function calculate_bookmark(y) {
    var elem = find_closest_enclosing_block(y);
    var sel = selector(elem);
    var ratio = (y - elem.offset().top)/elem.height();
    if (ratio > 1) { ratio = 1; }
    if (ratio < 0) { ratio = 0; }
    return sel + "|" + ratio;
}

function animated_scrolling_done() {
    window.py_bridge.animated_scroll_done();
}

function scroll_to_bookmark(bookmark) {
    bm = bookmark.split("|");
    var ratio = 0.7 * parseFloat(bm[1]);
    $.scrollTo($(bm[0]), 1000,
        {over:ratio, onAfter:function(){window.py_bridge.animated_scroll_done()}});
}

