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


