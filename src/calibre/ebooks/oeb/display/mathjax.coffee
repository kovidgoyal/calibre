#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2012, Kovid Goyal <kovid at kovidgoyal.net>
 Released under the GPLv3 License
###


log = window.calibre_utils.log

class MathJax
    # This class is a namespace to expose functions via the
    # window.mathjax object. The most important functions are:
    #

    constructor: () ->
        if not this instanceof arguments.callee
            throw new Error('MathJax constructor called as function')
        this.base = null
        this.math_present = false
        this.math_loaded = false
        this.pending_cfi = null
        this.hub = null

    load_mathjax: (user_config) ->
        if this.base == null
            log('You must specify the path to the MathJax installation before trying to load MathJax')
            return null

        script = document.createElement('script')

        script.type = 'text/javascript'
        script.src = 'file://' + this.base + '/MathJax.js'
        script.text = user_config + '''
        MathJax.Hub.signal.Interest(function (message) {if (String(message).match(/error/i)) {console.log(message)}});
        MathJax.Hub.Config({
            positionToHash: false,
            showMathMenu: false,
            extensions: ["tex2jax.js", "asciimath2jax.js", "mml2jax.js"],
            jax: ["input/TeX","input/MathML","input/AsciiMath","output/SVG"],
            TeX: {
                extensions: ["AMSmath.js","AMSsymbols.js","noErrors.js","noUndefined.js"]
            }
                });
        MathJax.Hub.Startup.onload();
        MathJax.Hub.Register.StartupHook("End", window.mathjax.load_finished);
        window.mathjax.hub = MathJax.Hub
        '''
        document.head.appendChild(script)

    load_finished: () =>
        log('MathJax load finished!')
        this.math_loaded = true
        if this.pending_cfi != null
            [cfi, callback] = this.pending_cfi
            this.pending_cfi = null
            window.cfi.scroll_to(cfi, callback)

    check_for_math: () ->
        script = null
        this.math_present = false
        this.math_loaded = false
        this.pending_cfi = null
        user_config = ''
        for c in document.getElementsByTagName('script')
            if c.getAttribute('type') == 'text/x-mathjax-config'
                if c.text
                    user_config += c.text
                script = c
                c.parentNode.removeChild(c)

        if script != null or document.getElementsByTagName('math').length > 0
            this.math_present = true
            this.load_mathjax(user_config)

    after_resize: () ->
        if not this.math_present or this.hub == null
            return
        # SVG output does not dynamically reflow on resize, so we manually
        # rerender, this is slow, but neccessary for tables and equation
        # numbers.
        this.hub.Queue(["Rerender",this.hub])

if window?
    window.mathjax = new MathJax()


