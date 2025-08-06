/* vim:fileencoding=utf-8
 *
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPLv3 license
 */

(function() {
    "use strict";

    var num_tries = 0;
    var style_id = 'a' + Math.random().toString(36).slice(2);

    function fix_google_markup() {
        try {
            var cc = document.getElementById('center_col');
            if (!cc) {
                if (++num_tries > 10) return;
                return setTimeout(fix_google_markup, 100);
            }

            // figure out if they actually got a dictionary card
            var is_dictionary_result = !!document.querySelector('.lr_container, .lr_dct_ent');
            // grab the raw query
            var q = new URLSearchParams(location.search.slice(1)).get('q') || ''

            if (is_dictionary_result) {
                // Only add styles once to prevent duplication
                if (!document.getElementById(style_id)) {
                var style = document.createElement('style');
                    style.id = style_id;
                    style.textContent = `
                        * {
                            column-gap: 0!important;
                            -webkit-column-gap: 0!important;
                        }
                        #center_col {
                            position: absolute !important;
                            top: 1px !important; /* Using your preferred 1px value */
                            left: 0 !important;
                            z-index: 100;
                        }
                        #cnt {
                            position: relative;
                            min-height: 100vh;
                        }
                        /* Clear the space where search form was */
                        #searchform, #appbar, #before-appbar {
                            display: none !important;
                        }
                    `;
                    document.head.appendChild(style);
                }

                var maxW = 'calc(100vw - 25px)';
                cc.style.maxWidth   = maxW;
                cc.style.marginLeft = '0';

                ['rcnt','cnt','search']
                .forEach(function(id) {
                    var e = document.getElementById(id);
                    if (e) {
                        if (id==='search') e.style.maxWidth = maxW;
                        else if (id==='cnt')  e.style.paddingTop = '0';
                        else                  e.style.marginLeft = '0';
                    }
                });

                cc.style.paddingLeft  = '0';
                cc.style.paddingRight = '6px';

                // constrain define text
                document.querySelectorAll('[data-topic]')
                    .forEach(e => e.style.maxWidth = maxW);

                // Ensure footer stays at bottom - with null check
                var cnt = document.getElementById('cnt');
                if (cnt) cnt.style.minHeight = '100vh';
            }

            // hide bunch of useful UI elements
            ['sfcnt', 'top_nav', 'easter-egg', 'topstuff', 'searchform', 'appbar', 'before-appbar']
            .forEach(function(id){
                var e = document.getElementById(id);
                if (e && e.style) e.style.display = 'none';
            });
            // remove that promo sidebar, wrap rest nicely
            var promo = document.getElementById('promos');
            if (promo) promo.remove();

            document.querySelectorAll('[data-ved]')
            .forEach(e => e.style.maxWidth = '100%');

            document.querySelectorAll('cite')
            .forEach(c => {
                var wrap = c.closest('div');
                if (wrap) wrap.style.position = 'static';
            });
        } catch(e) {
            console.error("fix_google_markup() failed with error:");
            console.error(e);
        }
    }

    if (location.hostname === 'www.google.com') {
        window.addEventListener('DOMContentLoaded', fix_google_markup);

        // Re-run on resize to handle Google's dynamic layout changes
        window.addEventListener('resize', function() {
            // Reset try counter to handle DOM changes
            num_tries = 0;
            fix_google_markup();
        });
    }
})();
