/*
 * reference management
 * Copyright 2008 Kovid Goyal
 * License: GNU GPL v3
 */

var reference_old_bgcol = "transparent";
var reference_prefix = "1.";
var reference_last_highlighted_para = null;

function show_reference_panel(ref) {
    panel = $("#calibre_reference_panel");
    if (panel.length < 1) {
        $(document.body).append('<div id="calibre_reference_panel" style="top:20px; left:20px; padding-left:30px; padding-right:30px; font:monospace normal;text-align:center; z-index:10000; background: beige; border:red ridge 2px; position:absolute;"><h5>Paragraph</h5><p style="text-indent:0pt">None</p></div>')
        panel = $("#calibre_reference_panel");
    }
    $("> p", panel).text(ref);
    panel.css({top:(window.pageYOffset+20)+"px", left:(window.pageXOffset+20)+"px"});
    panel.fadeIn(500);
}

function toggle_reference(e) {
    p = $(this);
    if (e.type == "mouseenter") {
        reference_old_bgcol = p.css("background-color");
        reference_last_highlighted_para = p;
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
        reference_last_highlighted_para = null;
    }
    return false;
}

function enter_reference_mode() {
    $("p").bind("mouseenter mouseleave", toggle_reference);
}

function leave_reference_mode() {
    $("p").unbind("mouseenter mouseleave", toggle_reference);
    panel = $("#calibre_reference_panel");
    if (panel.length > 0) panel.hide();
    if (reference_last_highlighted_para != null) 
        reference_last_highlighted_para.css({backgroundColor:reference_old_bgcol});
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
    var dest = $(p[num]);
    if (window.paged_display.in_paged_mode) {
        var xpos = dest.offset().left;
        window.paged_display.scroll_to_xpos(xpos, true, true, 1000);
    } else 
        $.scrollTo(dest, 1000,
            {onAfter:function(){window.py_bridge.animated_scroll_done()}});
}


