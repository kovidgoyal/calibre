#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2013, Kovid Goyal <kovid at kovidgoyal.net>
 Released under the GPLv3 License
###


if window?.calibre_utils
    log = window.calibre_utils.log

is_hidden = (elem) ->
    while elem
        if (elem.style && (elem.style.visibility == 'hidden' || elem.style.display == 'none'))
            return true
        elem = elem.parentNode
    return false

is_block = (elem) ->
    style = window.getComputedStyle(elem)
    return style.display in ['block', 'flex-box', 'box']

in_table = (elem) ->
    while elem
        if elem.tagName?.toLowerCase() == 'table'
            return true
        elem = elem.parentNode
    return false

find_containing_block = (elem) ->
    while elem and elem.getAttribute('data-is-block') != '1'
        elem = elem.parentNode
    return elem

INHERITED_PROPS = {  # {{{
		'azimuth':						'2',
		'border-collapse':				'2',
		'border-spacing':				'2',
		'caption-side':					'2',
		'color':						'2',
		'cursor':						'2',
		'direction':					'2',
		'elevation':					'2',
		'empty-cells':					'2',
		'fit':							'3',
		'fit-position':					'3',
		'font':							'2',
		'font-family':					'2',
		'font-size':					'2',
		'font-size-adjust':				'2',
		'font-stretch':					'2',
		'font-style':					'2',
		'font-variant':					'2',
		'font-weight':					'2',
		'hanging-punctuation':			'3',
		'hyphenate-after':				'3',
		'hyphenate-before':				'3',
		'hyphenate-character':			'3',
		'hyphenate-lines':				'3',
		'hyphenate-resource':			'3',
		'hyphens':						'3',
		'image-resolution':				'3',
		'letter-spacing':				'2',
		'line-height':					'2',
		'line-stacking':				'3',
		'line-stacking-ruby':			'3',
		'line-stacking-shift':			'3',
		'line-stacking-strategy':		'3',
		'list-style':					'2',
		'list-style-image':				'2',
		'list-style-position':			'2',
		'list-style-type':				'2',
		'marquee-direction':			'3',
		'orphans':						'2',
		'overflow-style':				'3',
		'page':							'2',
		'page-break-inside':			'2',
		'pitch':						'2',
		'pitch-range':					'2',
		'presentation-level':			'3',
		'punctuation-trim':				'3',
		'quotes':						'2',
		'richness':						'2',
		'ruby-align':					'3',
		'ruby-overhang':				'3',
		'ruby-position':				'3',
		'speak':						'2',
		'speak-header':					'2',
		'speak-numeral':				'2',
		'speak-punctuation':			'2',
		'speech-rate':					'2',
		'stress':						'2',
		'text-align':					'2',
		'text-align-last':				'3',
		'text-emphasis':				'3',
		'text-height':					'3',
		'text-indent':					'2',
		'text-justify':					'3',
		'text-outline':					'3',
		'text-replace':					'?',
		'text-shadow':					'3',
		'text-transform':				'2',
		'text-wrap':					'3',
		'visibility':					'2',
		'voice-balance':				'3',
		'voice-family':					'2',
		'voice-rate':					'3',
		'voice-pitch':					'3',
		'voice-pitch-range':			'3',
		'voice-stress':					'3',
		'voice-volume':					'3',
		'volume':						'2',
		'white-space':					'2',
		'white-space-collapse':			'3',
		'widows':						'2',
		'word-break':					'3',
		'word-spacing':					'2',
		'word-wrap':					'3',

        # the mozilla extensions are all proprietary properties
		'-moz-force-broken-image-icon':	'm',
		'-moz-image-region':			'm',
		'-moz-stack-sizing':			'm',
		'-moz-user-input':				'm',
		'-x-system-font':				'm',

        # the opera extensions are all draft implementations of CSS3 properties
		'-xv-voice-balance':			'o',
		'-xv-voice-pitch':				'o',
		'-xv-voice-pitch-range':		'o',
		'-xv-voice-rate':				'o',
		'-xv-voice-stress':				'o',
		'-xv-voice-volume':				'o',

        # the explorer extensions are all draft implementations of CSS3 properties
		'-ms-text-align-last':			'e',
		'-ms-text-justify':				'e',
		'-ms-word-break':				'e',
		'-ms-word-wrap':				'e'
}  # }}}

get_sourceline_address = (node) ->
    sourceline = parseInt(node.getAttribute('data-lnum'))
    tags = []
    for elem in document.querySelectorAll('[data-lnum="' + sourceline + '"]')
        tags.push(elem.tagName.toLowerCase())
        if elem is node
            break
    return [sourceline, tags]

get_color = (property, val) ->
    color = null
    if property.indexOf('color') > -1
        try
            color = parseCSSColor(val)  # Use the csscolor library to get an rgba 4-tuple
        catch error
            color = null
    return color

get_style_properties = (style, all_properties, node_style, is_ancestor) ->
    i = 0
    properties = []
    while i < style.length
        property = style.item(i)?.toLowerCase()
        val = style.getPropertyValue(property)
        if property and val and (not is_ancestor or INHERITED_PROPS.hasOwnProperty(property))
            properties.push([property, val, style.getPropertyPriority(property), get_color(property, val)])
            if not all_properties.hasOwnProperty(property)
                cval = node_style.getPropertyValue(property)
                all_properties[property] = [cval, get_color(property, cval)]
        i += 1
    return properties

process_rules = (node, cssRules, address, sheet, sheet_index, matching_selectors, all_properties, node_style, is_ancestor, ans) ->
    for rule, rule_index in cssRules
        rule_address = address.concat([rule_index])
        if rule.type == CSSRule.MEDIA_RULE
            process_rules(node, rule.cssRules, rule_address, sheet, sheet_index, matching_selectors, all_properties, node_style, is_ancestor, ans)
            continue
        if rule.type != CSSRule.STYLE_RULE
            continue
        # As a performance improvement, instead of running the match on every
        # rule, we simply check if its selector is one of the matching
        # selectors returned by getMatchedCSSRules. However,
        # getMatchedCSSRules ignores rules in media queries that dont apply, so we check them manually
        st = rule.selectorText
        if st and (matching_selectors.hasOwnProperty(st) or (rule_address.length > 1 and node.webkitMatchesSelector(st)))
            type = 'sheet'
            href = sheet.href
            if href == null
                href = get_sourceline_address(sheet.ownerNode)
                type = 'elem'
            parts = st.split(',')  # We only want the first matching selector
            if parts.length > 1
                for q in parts
                    if node.webkitMatchesSelector(q)
                        st = q
                        break
            properties = get_style_properties(rule.style, all_properties, node_style, is_ancestor)
            if properties.length > 0
                data = {'selector':st, 'type':type, 'href':href, 'properties':properties, 'rule_address':rule_address, 'sheet_index':sheet_index}
                ans.push(data)

get_matched_css = (node, is_ancestor, all_properties) ->
    # WebKit sets parentStyleSheet == null for rules returned by getMatchedCSSRules so we cannot use them directly
    rules = node.ownerDocument.defaultView.getMatchedCSSRules(node, '')
    if not rules
        rules = []
    matching_selectors = {}
    for rule in rules
        matching_selectors[rule.selectorText] = true
    ans = []
    node_style = window.getComputedStyle(node)

    for sheet, sheet_index in document.styleSheets
        if sheet.disabled or not sheet.cssRules
            continue
        process_rules(node, sheet.cssRules, [], sheet, sheet_index, matching_selectors, all_properties, node_style, is_ancestor, ans)

    if node.getAttribute('style')
        properties = get_style_properties(node.style, all_properties, node_style, is_ancestor)
        if properties.length > 0
            data = {'selector':null, 'type':'inline', 'href':get_sourceline_address(node), 'properties':properties, 'rule_address':null, 'sheet_index':null}
            ans.push(data)

    return ans.reverse()

scroll_to_node = (node) ->
    if node is document.body
        window.scrollTo(0, 0)
    else
        node.scrollIntoView()

class PreviewIntegration

    ###
    # Namespace to expose all the functions used for integration with the Tweak
    # Book Preview Panel.
    ###

    constructor: () ->
        if not this instanceof arguments.callee
            throw new Error('PreviewIntegration constructor called as function')
        this.blocks_found = false
        this.in_split_mode = false

    go_to_line: (lnum) =>
        for node in document.querySelectorAll('[data-lnum="' + lnum + '"]')
            if is_hidden(node)
                continue
            scroll_to_node(node)

    go_to_sourceline_address: (sourceline, tags) =>
        for node, index in document.querySelectorAll('[data-lnum="' + sourceline + '"]')
            if index >= tags.length or node.tagName.toLowerCase() != tags[index]
                break
            if index == tags.length - 1 and not is_hidden(node)
                return scroll_to_node(node)
        this.go_to_line(sourceline)

    line_numbers: () =>
        found_body = false
        ans = []
        for node in document.getElementsByTagName('*')
            if not found_body and node.tagName.toLowerCase() == "body"
                found_body = true
            if found_body
                ans.push(node.getAttribute("data-lnum"))
        return ans

    find_blocks: () =>
        if this.blocks_found
            return
        for elem in document.body.getElementsByTagName('*')
            if is_block(elem) and not in_table(elem)
                elem.setAttribute('data-is-block', '1')
        this.blocks_found = true

    split_mode: (enabled) =>
        this.in_split_mode = enabled
        document.body.setAttribute('data-in-split-mode', if enabled then '1' else '0')
        if enabled
            this.find_blocks()

    report_split: (node) =>
        loc = []
        totals = []
        parent = find_containing_block(node)
        while parent and parent.tagName.toLowerCase() != 'body'
            totals.push(parent.parentNode.children.length)
            num = 0
            sibling = parent.previousElementSibling
            while sibling
                num += 1
                sibling = sibling.previousElementSibling
            loc.push(num)
            parent = parent.parentNode
        loc.reverse()
        totals.reverse()
        window.py_bridge.request_split(JSON.stringify(loc), JSON.stringify(totals))

    onload: () =>
        window.document.body.addEventListener('click', this.onclick, true)

    onclick: (event) =>
        event.preventDefault()
        if this.in_split_mode
            this.report_split(event.target)
        else
            e = event.target
            address = get_sourceline_address(e)
            # Find the closest containing link, if any
            href = tn = ''
            while e and e != document.body and e != document and (tn != 'a' or not href)
                tn = e.tagName?.toLowerCase()
                href = e.getAttribute('href')
                e = e.parentNode
            window.py_bridge.request_sync(tn, href, JSON.stringify(address))
        return false

    go_to_anchor: (anchor, lnum) =>
        elem = document.getElementById(anchor)
        if not elem
            elem = document.querySelector('[name="' + anchor + '"]')
        if elem
            elem.scrollIntoView()
            address = get_sourceline_address(elem)
        window.py_bridge.request_sync('', '', address)

    live_css: (sourceline, tags) =>
        target = null
        i = 0
        for node in document.querySelectorAll('[data-lnum="' + sourceline + '"]')
            if node.tagName?.toLowerCase() != tags[i]
                return JSON.stringify(null)
            i += 1
            target = node
            if i >= tags.length
                break
        all_properties = {}
        original_target = target
        ans = {'nodes':[], 'computed_css':all_properties}
        is_ancestor = false
        while target and target.ownerDocument
            css = get_matched_css(target, is_ancestor, all_properties)
            # We want to show the Matched CSS rules header even if no rules matched
            if css.length > 0 or not is_ancestor
                ans['nodes'].push({'name':target.tagName?.toLowerCase(), 'css':css, 'is_ancestor':is_ancestor, 'sourceline':target.getAttribute('data-lnum')})
            target = target.parentNode
            is_ancestor = true
        return JSON.stringify(ans)


window.calibre_preview_integration = new PreviewIntegration()
window.onload = window.calibre_preview_integration.onload
