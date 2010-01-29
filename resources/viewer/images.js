/*
 * images management
 * Copyright 2008 Kovid Goyal
 * License: GNU GPL v3
 */

function scale_images() {
    $("img:visible").each(function() {
        var offset = $(this).offset();
        //window.py_bridge.debug(window.getComputedStyle(this, '').getPropertyValue('max-width'));
        $(this).css("max-width", (window.innerWidth-offset.left-5)+"px");
        $(this).css("max-height", (window.innerHeight-5)+"px");
    });
}

function setup_image_scaling_handlers() {
   scale_images();
   $(window).resize(function(){
        scale_images();
   });
}

function extract_svged_images() {
    $("svg").each(function() {
        var children = $(this).children("img");
        if (children.length == 1) {
            var img = $(children[0]);
            var href = img.attr('xlink:href');
            if (href != undefined) {
                $(this).replaceWith('<div style="text-align:center; margin: 0; padding: 0"><img style="height: 98%" alt="SVG Image" src="' + href +'"></img></div>');
            }
        }
    });
}

$(document).ready(function() {
   //extract_svged_images();
});

