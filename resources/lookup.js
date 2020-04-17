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
        if (!cc) {
            if (++num_tries > 10) return;
            setTimeout(fix_google_markup, 100);
            return;
        }
        cc.style.marginLeft = '0';
        cc = document.getElementById('cnt');
        if (cc) cc.style.paddingTop = '0';
        var params = new URLSearchParams(document.location.search.substring(1));
        var q = params.get('q');
        if (q && q.startsWith('define:')) {
            cc.style.position = 'absolute';
            cc.style.top = '0';
            cc.style.left = '0';
            var remove = ['sfcnt', 'top_nav', 'before-appbar', 'appbar', 'searchform', 'easter-egg'];
            remove.forEach(function(id) {
                var elem = document.getElementById(id);
                if (elem) elem.style.display = 'none';
            });
        }
        var promo = document.getElementById('promos');
        if (promo) promo.parentNode.removeChild(promo);
    }

    if (window.location.hostname === 'www.google.com') {
        window.addEventListener('DOMContentLoaded', fix_google_markup);
    }
})();
