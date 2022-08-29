/* vim:fileencoding=utf-8
 * 
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPLv3 license
 */

(function() {
    "use strict";

    var num_tries = 0;

    function fix_google_markup() {
        var cc = document.getElementById('center_col');
        var max_width = 'calc(100vw - 25px)';
        if (!cc) {
            if (++num_tries > 10) return;
            setTimeout(fix_google_markup, 100);
            return;
        }
        cc.style.maxWidth = max_width;
        cc.style.marginLeft = '0';
        var rcnt = document.getElementById('rcnt');
        if (rcnt) rcnt.style.marginLeft = '0';
        cc = document.getElementById('cnt');
        if (cc) cc.style.paddingTop = '0';
        var s = document.getElementById('search');
        if (s) s.style.maxWidth = max_width;
        var params = new URLSearchParams(document.location.search.substring(1));
        var q = params.get('q');
        if (q && q.startsWith('define:')) {
            cc.style.position = 'absolute';
            cc.style.top = '0';
            cc.style.left = '0';
            cc.style.paddingLeft = '6px';
            cc.style.paddingRight = '6px';
            var remove = ['sfcnt', 'top_nav', 'before-appbar', 'appbar', 'searchform', 'easter-egg', 'topstuff'];
            remove.forEach(function(id) {
                var elem = document.getElementById(id);
                if (elem) elem.style.display = 'none';
            });
            // make definitions text wrap
            document.querySelectorAll('[data-topic]').forEach(function(elem) { elem.style.maxWidth = max_width; });
        }
        var promo = document.getElementById('promos');
        if (promo) promo.parentNode.removeChild(promo);

        // make search results wrap
        document.querySelectorAll('[data-ved]').forEach(function(elem) { elem.style.maxWidth = max_width; });

        // the above wrapping causing overlapping text of the 
        // search results and the citation, fix that
        document.querySelectorAll('cite').forEach(function(elem) { 
            var d = elem.closest('div');
            if (d) d.style.position = 'static';
        });
    }

    if (window.location.hostname === 'www.google.com') {
        window.addEventListener('DOMContentLoaded', fix_google_markup);
    }
})();
