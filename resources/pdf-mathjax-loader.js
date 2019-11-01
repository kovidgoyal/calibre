/* vim:fileencoding=utf-8
 * 
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPLv3 license
 */
/*jshint esversion: 6 */

(function() {
"use strict";

    function init_mathjax() {
        var orig = window.MathJax.Ajax.fileURL.bind(window.MathJax.Ajax);

        window.MathJax.Ajax.fileURL = function(mathjax_name) {
            var ans = orig(mathjax_name);
            if (mathjax_name.startsWith('[MathJax]/../fonts')) {
                ans = ans.replace('/../fonts', '/fonts');
            }
            return ans;
        };
    }

    var base = document.currentScript.getAttribute('data-mathjax-path');
    if (!base.endsWith('/')) base += '/';

    var script = document.createElement('script');
    script.type = 'text/javascript';
    script.setAttribute('async', 'async');
    script.onerror = function (ev) {
        console.log('Failed to load MathJax script: ' + ev.target.src);
    };
    script.src = base + 'MathJax.js';
    window.MathJax = {AuthorInit:  init_mathjax};
    script.text = `
        document.title = 'mathjax-load-started';
        MathJax.Hub.signal.Interest(function (message) {if (String(message).match(/error/i)) {console.log(message)}});
        MathJax.Hub.Config({
            positionToHash: false,
            showMathMenu: false,
            extensions: ["tex2jax.js", "asciimath2jax.js", "mml2jax.js"],
            jax: ["input/TeX", "input/MathML", "input/AsciiMath", "output/CommonHTML"],
            TeX: {
                extensions: ["AMSmath.js", "AMSsymbols.js", "noErrors.js", "noUndefined.js"]
            }
                });
        MathJax.Hub.Startup.onload();
        MathJax.Hub.Register.StartupHook("End", function() { document.title = "mathjax-load-complete"; });
    `.trim();
    document.head.appendChild(script);
})();
