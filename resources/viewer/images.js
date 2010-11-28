/*
 * images management
 * Copyright 2008 Kovid Goyal
 * License: GNU GPL v3
 */

function scale_images() {
    $("img:visible").each(function() {
        var img = $(this);
        var offset = img.offset();
        var avail_width = window.innerWidth - offset.left - 5;
        var avail_height = window.innerHeight - 5;
        img.css('width', img.data('orig-width'));
        img.css('height', img.data('orig-height'));
        var width = img.width();
        var height = img.height();
        var ratio = 0;

        if (width > avail_width) {
            ratio = avail_width / width;
            img.css('width', avail_width+'px');
            img.css('height', (ratio*height) + 'px');
            height = height * ratio;
            width = width * ratio;
        }

        if (height > avail_height) {
            ratio = avail_height / height;
            img.css('height', avail_height);
            img.css('width', width * ratio);
        }
        //window.py_bridge.debug(window.getComputedStyle(this, '').getPropertyValue('max-width'));
    });
}

function store_original_size_attributes() {
    $("img").each(function() {
        var img = $(this);
        img.data('orig-width', img.css('width'));
        img.data('orig-height', img.css('height'));
    });
}

function setup_image_scaling_handlers() {
   store_original_size_attributes();
   scale_images();
   $(window).resize(function(){
        scale_images();
   });
}


