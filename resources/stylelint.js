/* vim:fileencoding=utf-8
 * 
 * Copyright (C) 2023 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPLv3 license
 */
/*jshint esversion: 6 */
(function() {
"use strict";

window.stylelint_results = [];

window.check_css =  function(src, fix) {
    stylelint.lint({
        code: src,
        fix: fix,
        config: {
            rules: {
                'annotation-no-unknown': true,
                'at-rule-no-unknown': true,
                'block-no-empty': true,
                'color-no-invalid-hex': true,
                'comment-no-empty': true,
                'custom-property-no-missing-var-function': true,
                'declaration-block-no-duplicate-custom-properties': true,
                'declaration-block-no-duplicate-properties': [
                    true,
                    {
                        ignore: ['consecutive-duplicates-with-different-values'],
                    },
                ],
                'declaration-block-no-shorthand-property-overrides': true,
                'font-family-no-duplicate-names': true,
                'font-family-no-missing-generic-family-keyword': true,
                'function-calc-no-unspaced-operator': true,
                'function-linear-gradient-no-nonstandard-direction': true,
                'function-no-unknown': true,
                'keyframe-block-no-duplicate-selectors': true,
                'keyframe-declaration-no-important': true,
                'media-feature-name-no-unknown': true,
                'named-grid-areas-no-invalid': true,
                'no-descending-specificity': true,
                'no-duplicate-at-import-rules': true,
                'no-duplicate-selectors': true,
                'no-empty-source': true,
                'no-extra-semicolons': true,
                'no-invalid-double-slash-comments': true,
                'no-invalid-position-at-import-rule': true,
                'no-irregular-whitespace': true,
                'property-no-unknown': true,
                'selector-pseudo-class-no-unknown': true,
                'selector-pseudo-element-no-unknown': true,
                'selector-type-no-unknown': [
                    true,
                    {
                        ignore: ['custom-elements'],
                    },
                ],
                'string-no-newline': true,
                'unit-no-unknown': true,
            },
        },
        formatter: (results, returnValue) => {
            var r = results[0];
            r._postcssResult = undefined;
            r.source = undefined;
            return JSON.stringify({results:r, rule_metadata: returnValue.ruleMetadata});
        },
    })
    .then((results) => {
        window.stylelint_results.push({type: 'results', 'results':results});
        document.title = 'checked:' + window.performance.now();
    })
    .catch((err) => {
        window.stylelint_results.push({type: 'error', 'error':'' + err});
        console.error(err.stack);
        document.title = 'checked:' + window.performance.now();
    }) ;
};

window.get_css_results = function(src) {
    var ans = window.stylelint_results;
    window.stylelint_results = [];
    return ans;
};
document.title = 'ready:' + window.performance.now();
})();


