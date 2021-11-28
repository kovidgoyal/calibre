/* vim:fileencoding=utf-8
 * 
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPLv3 license
 */
/*jshint esversion: 6 */
(function() {
    "use strict";
    var com_id = "COM_ID";
    var com_counter = 0;
    var settings = SETTINGS;

    function onclick(event) {
        // We dont want this event to trigger onclick on this element's parent
        // block, if any.
        event.stopPropagation();
        var frac = window.pageYOffset/document.body.scrollHeight;
        var loc = [];
        var totals = [];
        var block = event.currentTarget;
        var parent = block;
        while (parent && parent.tagName && parent.tagName.toLowerCase() !== 'body') {
            totals.push(parent.parentNode.children.length);
            var num = 0;
            var sibling = parent.previousElementSibling;
            while (sibling) {
                num += 1;
                sibling = sibling.previousElementSibling;
            }
            loc.push(num);
            parent = parent.parentNode;
        }
        loc.reverse();
        totals.reverse();
        com_counter += 1;
        window.calibre_toc_data = [block.tagName.toLowerCase(), block.id, loc, totals, frac];
        document.title = com_id + '-' + com_counter;
    }

    function find_blocks() {
        for (let elem of document.body.getElementsByTagName('*')) {  
            var style = window.getComputedStyle(elem);
            if (style.display === 'block' || style.display === 'flex-box' || style.display === 'box') {
                elem.addEventListener('click', onclick);
                elem.addEventListener('mouseover', function(ev) { this.classList.add('calibre_toc_hover'); ev.stopPropagation(); });
                elem.addEventListener('mouseout', function(ev) { this.classList.remove('calibre_toc_hover'); ev.stopPropagation(); });
            }
        }
    }

    function apply_body_colors(event) {
        if (document.documentElement) {
            if (settings.bg) document.documentElement.style.backgroundColor = settings.bg;
            if (settings.fg) document.documentElement.style.color = settings.fg;
        }
        if (document.body) {
            if (settings.bg) document.body.style.backgroundColor = settings.bg;
            if (settings.fg) document.body.style.color = settings.fg;
        }
    }

    function apply_css() {
        var css = '';
        css += '.calibre_toc_hover:hover { cursor: pointer !important; border-top: solid 5px green !important }\n\n';
        if (settings.link) css += 'html > body :link, html > body :link * { color: ' + settings.link + ' !important; }\n\n';
        if (settings.is_dark_theme) { css = ':root { color-scheme: dark; }' + css; }
        var style = document.createElement('style');
        style.textContent = css;
        document.documentElement.appendChild(style);
    }

    apply_body_colors();

    function apply_all() {
        apply_css();
        apply_body_colors();
        find_blocks();
    }
    document.addEventListener("DOMContentLoaded", apply_all);
})();
