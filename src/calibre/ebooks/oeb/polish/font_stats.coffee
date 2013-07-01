#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2013, Kovid Goyal <kovid at kovidgoyal.net>
 Released under the GPLv3 License
###


if window?.calibre_utils
    log = window.calibre_utils.log

font_dict = (style, computed=false) ->
    if computed
        fams = []
        family = style.getPropertyCSSValue('font-family')
        if family.cssValueType == CSSValue.CSS_PRIMITIVE_VALUE
            fams.push(family.getStringValue())
        else
            for f in family
                fams.push(f.getStringValue())
    else
        fams = style.getPropertyValue('font-family')
    return {
        'font-family':fams,
        'font-weight':style.getPropertyValue('font-weight'),
        'font-style':style.getPropertyValue('font-style'),
        'font-stretch':style.getPropertyValue('font-stretch'),
    }

font_usage = (node) ->
    style = window.getComputedStyle(node, null)
    ans = font_dict(style, true)
    text = []
    for child in node.childNodes
        if child.nodeType == Node.TEXT_NODE
            text.push(child.nodeValue)
    ans['text'] = text
    return ans

class FontStats
    # This class is a namespace to expose functions via the
    # window.font_stats object.

    constructor: () ->
        if not this instanceof arguments.callee
            throw new Error('FontStats constructor called as function')

    get_font_face_rules: () ->
        font_faces = []
        for sheet in document.styleSheets
            for rule in sheet.cssRules
                if rule.type == rule.FONT_FACE_RULE
                    fd = font_dict(rule.style)
                    fd['src'] = rule.style.getPropertyValue('src')
                    font_faces.push(fd)
        py_bridge.value = font_faces

    get_font_usage: () ->
        ans = []
        busage = font_usage(document.body)
        if busage != null
            ans.push(busage)
        for node in document.body.getElementsByTagName('*')
            usage = font_usage(node)
            if usage != null
                ans.push(usage)
        py_bridge.value = ans

    get_font_families: () ->
        ans = {}
        for node in document.getElementsByTagName('*')
            rules = document.defaultView.getMatchedCSSRules(node, '')
            if rules
                for rule in rules
                    style = rule.style
                    family = style.getPropertyValue('font-family')
                    if family
                        ans[family] = true
        py_bridge.value = ans

if window?
    window.font_stats = new FontStats()

