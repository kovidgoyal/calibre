/* vim:fileencoding=utf-8
 * 
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPLv3 license
 */
/*jshint esversion: 6 */

(function() {
"use strict";
    var base = document.currentScript ? document.currentScript.getAttribute('data-mathjax-path') : null;
    var for_pdf_renderer = !!base;

    function on_mathjax_finish() {
        if (for_pdf_renderer) document.title = "mathjax-load-complete";
        else document.documentElement.dispatchEvent(new CustomEvent("calibre-mathjax-typeset-done"));
    }
    // also do any changes in mathjax.pyj for the in-browser reader
    window.MathJax = {};
    window.MathJax.options = {
        renderActions: {
            // disable the mathjax context menu
            addMenu: [0, '', ''],
        },
    };
    window.MathJax.loader = {
        load: ['input/tex-full', 'input/asciimath', 'input/mml', 'output/chtml'],
    };
    window.MathJax.startup = {
        ready: () => {
            MathJax.startup.defaultReady();
            MathJax.startup.promise.then(on_mathjax_finish);
        },
    };
    for (const s of document.scripts) {
        if (s.type === "text/x-mathjax-config") {
            var es = document.createElement('script');
            es.text = s.text;
            document.head.appendChild(es);
            document.head.removeChild(es);
        }
    }
    if (for_pdf_renderer) {
        if (!base.endsWith('/')) base += '/';
        var script = document.createElement('script');
        script.type = 'text/javascript';
        script.setAttribute('async', 'async');
        script.onerror = function (ev) {
            console.log('Failed to load MathJax script: ' + ev.target.src);
        };
        script.src = base + 'startup.js';
        document.head.appendChild(script);
    }
})();
