/* vim:fileencoding=utf-8
 * 
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPLv3 license
 */
(function() {
    "use strict";
    var com_id = "COM_ID";
    var com_counter = 0;

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
            style = window.getComputedStyle(elem);
            if (style.display === 'block' || style.display === 'flex-box' || style.display === 'box') {
                elem.classList.add("calibre_toc_hover");
                elem.onclick = onclick;
            }
        }
    }

    var style = document.createElement('style');
    style.innerText = 'body { background-color: white  }' + '.calibre_toc_hover:hover { cursor: pointer !important; border-top: solid 5px green !important }' + '::selection {background:#ffff00; color:#000;}';
    document.documentElement.appendChild(style);
    find_blocks();
})();
