#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

PATCHED_MATHJAX = '''

function postprocess_mathjax(link_uid) {
    Array.prototype.forEach.call(document.getElementsByTagName('a'), function(a) {
        var href = a.getAttribute('href');
        if (href && href.startsWith('#')) {
            a.setAttribute('href', 'javascript: void(0)')
            a.setAttribute('data-' + link_uid, JSON.stringify({'frag':href.slice(1)}))
        }
    });
    document.documentElement.dispatchEvent(new CustomEvent("calibre-mathjax-init-done"));
}

function monkeypatch(mathjax_files) {
    var orig = window.MathJax.Ajax.fileURL.bind(window.MathJax.Ajax);
    var StyleString = window.MathJax.Ajax.StyleString.bind(window.MathJax.Ajax);

    window.MathJax.Ajax.StyleString = function(styles) {
        return StyleString(styles).replace(/url\\('?(.*?)'?\\)/g, function(match, url) {
            if (!url.endsWith('.woff')) return match;
            url = mathjax_files[url];
            if (!url) return match;
            if (typeof url != "string") {
                url = window.URL.createObjectURL(url);
                mathjax_files[name] = url;
            }
            return "url('" + url + "')";
        });
    }

    window.MathJax.Ajax.fileURL = function(mathjax_name) {
        var ans = orig(mathjax_name);
        var name = ans.replace(/^\\//g, '');
        if (name.startsWith('../fonts')) name = name.slice(3);
        ans = mathjax_files[name];
        if (!ans) ans = name;
        if (typeof ans !== 'string') {
            mathjax_files[name] = window.URL.createObjectURL(ans);
            ans = mathjax_files[name];
        }
        if (ans === name && !name.startsWith('blob:') && !name.endsWith('/eot') && !name.endsWith('/woff') && !name.endsWith('/otf')) {
            if (ans.endsWith('.eot') || ans.endsWith('.otf')) ans = '';
            else console.log('WARNING: Failed to resolve MathJax file: ' + mathjax_name);
        }
        return ans;
    }
    window.MathJax.Ajax.fileRev = function(mathjax_name) { return ''; }
}

function init_mathjax(link_uid, mathjax_files) {
    monkeypatch(mathjax_files);
    window.MathJax.Hub.Register.StartupHook("End", postprocess_mathjax.bind(this, link_uid))
}

document.documentElement.addEventListener("calibre-mathjax-init", function(ev) {

window.MathJax = ev.detail.MathJax;
window.MathJax.AuthorInit = init_mathjax.bind(this, ev.detail.link_uid, ev.detail.mathjax_files);

__SRC__
});
'''


def monkeypatch_mathjax(src):
    return PATCHED_MATHJAX.replace('__SRC__', src, 1)
