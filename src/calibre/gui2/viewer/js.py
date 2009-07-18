bookmarks = '''

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

'''

referencing = '''
var reference_old_bgcol = "transparent";
var reference_prefix = "1.";

function show_reference_panel(ref) {
    panel = $("#calibre_reference_panel");
    if (panel.length < 1) {
        $(document.body).append('<div id="calibre_reference_panel" style="top:20px; left:20px; padding-left:30px; padding-right:30px; font:monospace normal;text-align:center; z-index:10000; background: beige; border:red ridge 2px; position:absolute;"><h5>Paragraph</h5><p style="text-indent:0pt">None</p></div>')
        panel = $("#calibre_reference_panel");
    }
    $("> p", panel).text(ref);
    panel.css({top:(window.pageYOffset+20)+"px"});
    panel.fadeIn(500);
}

function toggle_reference(e) {
    p = $(this);
    if (e.type == "mouseenter") {
        reference_old_bgcol = p.css("background-color");
        p.css({backgroundColor:"beige"});
        var i = 0;
        var paras = $("p");
        for (j = 0; j < paras.length; j++,i++) {
            if (paras[j] == p[0]) break;
        }
        show_reference_panel(reference_prefix+(i+1) );
    } else {
        p.css({backgroundColor:reference_old_bgcol});
        panel = $("#calibre_reference_panel").hide();
    }
    return false;
}

function enter_reference_mode() {
    $("p").bind("mouseenter mouseleave", toggle_reference);
}

function leave_reference_mode() {
    $("p").unbind("mouseenter mouseleave", toggle_reference);
}

function goto_reference(ref) {
    var tokens = ref.split(".");
    if (tokens.length != 2) {alert("Invalid reference: "+ref); return;}
    var num = parseInt(tokens[1]);
    if (isNaN(num)) {alert("Invalid reference: "+ref); return;}
    num -= 1;
    if (num < 0) {alert("Invalid reference: "+ref); return;}
    var p = $("p");
    if (num >= p.length) {alert("Reference not found: "+ref); return;}
    $.scrollTo($(p[num]), 1000,
        {onAfter:function(){window.py_bridge.animated_scroll_done()}});
}

'''

test = '''
$(document.body).click(function(e) {
    bm = calculate_bookmark(e.pageY);
    scroll_to_bookmark(bm);
});

$(document).ready(enter_reference_mode);

'''

hyphenation = '''
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
'''
