/** @license Hyphenator 4.2.0 - client side hyphenation for webbrowsers
 *  Copyright (C) 2013  Mathias Nater, Zürich (mathias at mnn dot ch)
 *  Project and Source hosted on http://code.google.com/p/hyphenator/
 * 
 *  This JavaScript code is free software: you can redistribute
 *  it and/or modify it under the terms of the GNU Lesser
 *  General Public License (GNU LGPL) as published by the Free Software
 *  Foundation, either version 3 of the License, or (at your option)
 *  any later version.  The code is distributed WITHOUT ANY WARRANTY;
 *  without even the implied warranty of MERCHANTABILITY or FITNESS
 *  FOR A PARTICULAR PURPOSE.  See the GNU GPL for more details.
 *
 *  As additional permission under GNU GPL version 3 section 7, you
 *  may distribute non-source (e.g., minimized or compacted) forms of
 *  that code without the copy of the GNU GPL normally required by
 *  section 4, provided you include this license notice and a URL
 *  through which recipients can access the Corresponding Source.
 *
 * 
 *  Hyphenator.js contains code from Bram Steins hypher.js-Project:
 *  https://github.com/bramstein/Hypher
 *  
 *  Code from this project is marked in the source and belongs 
 *  to the following license:
 *  
 *  Copyright (c) 2011, Bram Stein
 *  All rights reserved.
 *  
 *  Redistribution and use in source and binary forms, with or without 
 *  modification, are permitted provided that the following conditions 
 *  are met:
 *   
 *   1. Redistributions of source code must retain the above copyright
 *      notice, this list of conditions and the following disclaimer. 
 *   2. Redistributions in binary form must reproduce the above copyright 
 *      notice, this list of conditions and the following disclaimer in the 
 *      documentation and/or other materials provided with the distribution. 
 *   3. The name of the author may not be used to endorse or promote products 
 *      derived from this software without specific prior written permission. 
 *  
 *  THIS SOFTWARE IS PROVIDED BY THE AUTHOR "AS IS" AND ANY EXPRESS OR IMPLIED 
 *  WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF 
 *  MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO 
 *  EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, 
 *  INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, 
 *  BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, 
 *  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY 
 *  OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING 
 *  NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, 
 *  EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 *  
 */

/* 
 *  Comments are jsdoctoolkit formatted. See http://code.google.com/p/jsdoc-toolkit/
 */

/* The following comment is for JSLint: */
/*global window */
/*jslint browser: true */

/**
 * @constructor
 * @description Provides all functionality to do hyphenation, except the patterns that are loaded
 * externally.
 * @author Mathias Nater, <a href = "mailto:mathias@mnn.ch">mathias@mnn.ch</a>
 * @version 4.2.0
 * @namespace Holds all methods and properties
 * @example
 * &lt;script src = "Hyphenator.js" type = "text/javascript"&gt;&lt;/script&gt;
 * &lt;script type = "text/javascript"&gt;
 *   Hyphenator.run();
 * &lt;/script&gt;
 */
var Hyphenator = (function (window) {
    'use strict';

    /**
     * @name Hyphenator-contextWindow
     * @private
     * @description
     * contextWindow stores the window for the document to be hyphenated.
     * If there are frames this will change.
     * So use contextWindow instead of window!
     */
    var contextWindow = window,

        /**
         * @name Hyphenator-supportedLangs
         * @description
         * A key-value object that stores supported languages and meta data.
         * The key is the bcp47 code of the language and the value
         * is an object containing following informations about the language:
         * file: filename of the pattern file,
         * script: script type of the language (e.g. 'latin' for english), this type is abbreviated by an id,
         * prompt: the sentence prompted to the user, if Hyphenator.js doesn't find a language hint.
         * @type {Object.<string>, Object>}
         * @private
         * @example
         * Check if language lang is supported:
         * if (supportedLangs.hasOwnProperty(lang))
         */
        supportedLangs = (function () {
            var r = {},
                o = function (code, file, script, prompt) {
                    r[code] = {'file': file, 'script': script, 'prompt': prompt};
                };

            //latin:0, cyrillic: 1, arabic: 2, armenian:3, bengali: 4, devangari: 5, greek: 6
            //gujarati: 7, kannada: 8, lao: 9, malayalam: 10, oriya: 11, persian: 12, punjabi: 13, tamil: 14, telugu: 15
            //
            //(language code, file name, script, prompt)
            o('be', 'be.js', 1, 'Мова гэтага сайта не можа быць вызначаны аўтаматычна. Калі ласка пакажыце мову:');
            o('ca', 'ca.js', 0, '');
            o('cs', 'cs.js', 0, 'Jazyk této internetové stránky nebyl automaticky rozpoznán. Určete prosím její jazyk:');
            o('da', 'da.js', 0, 'Denne websides sprog kunne ikke bestemmes. Angiv venligst sprog:');
            o('bn', 'bn.js', 4, '');
            o('de', 'de.js', 0, 'Die Sprache dieser Webseite konnte nicht automatisch bestimmt werden. Bitte Sprache angeben:');
            o('el', 'el-monoton.js', 6, '');
            o('el-monoton', 'el-monoton.js', 6, '');
            o('el-polyton', 'el-polyton.js', 6, '');
            o('en', 'en-us.js', 0, 'The language of this website could not be determined automatically. Please indicate the main language:');
            o('en-gb', 'en-gb.js', 0, 'The language of this website could not be determined automatically. Please indicate the main language:');
            o('en-us', 'en-us.js', 0, 'The language of this website could not be determined automatically. Please indicate the main language:');
            o('eo', 'eo.js', 0, 'La lingvo de ĉi tiu retpaĝo ne rekoneblas aŭtomate. Bonvolu indiki ĝian ĉeflingvon:');
            o('es', 'es.js', 0, 'El idioma del sitio no pudo determinarse autom%E1ticamente. Por favor, indique el idioma principal:');
            o('et', 'et.js', 0, 'Veebilehe keele tuvastamine ebaõnnestus, palun valige kasutatud keel:');
            o('fi', 'fi.js', 0, 'Sivun kielt%E4 ei tunnistettu automaattisesti. M%E4%E4rit%E4 sivun p%E4%E4kieli:');
            o('fr', 'fr.js', 0, 'La langue de ce site n%u2019a pas pu %EAtre d%E9termin%E9e automatiquement. Veuillez indiquer une langue, s.v.p.%A0:');
            o('grc', 'grc.js', 6, '');
            o('gu', 'gu.js', 7, '');
            o('hi', 'hi.js', 5, '');
            o('hu', 'hu.js', 0, 'A weboldal nyelvét nem sikerült automatikusan megállapítani. Kérem adja meg a nyelvet:');
            o('hy', 'hy.js', 3, 'Չհաջողվեց հայտնաբերել այս կայքի լեզուն։ Խնդրում ենք նշեք հիմնական լեզուն՝');
            o('it', 'it.js', 0, 'Lingua del sito sconosciuta. Indicare una lingua, per favore:');
            o('kn', 'kn.js', 8, 'ಜಾಲ ತಾಣದ ಭಾಷೆಯನ್ನು ನಿರ್ಧರಿಸಲು ಸಾಧ್ಯವಾಗುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ಮುಖ್ಯ ಭಾಷೆಯನ್ನು ಸೂಚಿಸಿ:');
            o('la', 'la.js', 0, '');
            o('lt', 'lt.js', 0, 'Nepavyko automatiškai nustatyti šios svetainės kalbos. Prašome įvesti kalbą:');
            o('lv', 'lv.js', 0, 'Šīs lapas valodu nevarēja noteikt automātiski. Lūdzu norādiet pamata valodu:');
            o('ml', 'ml.js', 10, 'ഈ വെ%u0D2C%u0D4D%u200Cസൈറ്റിന്റെ ഭാഷ കണ്ടുപിടിയ്ക്കാ%u0D28%u0D4D%u200D കഴിഞ്ഞില്ല. ഭാഷ ഏതാണെന്നു തിരഞ്ഞെടുക്കുക:');
            o('nb', 'nb-no.js', 0, 'Nettstedets språk kunne ikke finnes automatisk. Vennligst oppgi språk:');
            o('no', 'nb-no.js', 0, 'Nettstedets språk kunne ikke finnes automatisk. Vennligst oppgi språk:');
            o('nb-no', 'nb-no.js', 0, 'Nettstedets språk kunne ikke finnes automatisk. Vennligst oppgi språk:');
            o('nl', 'nl.js', 0, 'De taal van deze website kan niet automatisch worden bepaald. Geef de hoofdtaal op:');
            o('or', 'or.js', 11, '');
            o('pa', 'pa.js', 13, '');
            o('pl', 'pl.js', 0, 'Języka tej strony nie można ustalić automatycznie. Proszę wskazać język:');
            o('pt', 'pt.js', 0, 'A língua deste site não pôde ser determinada automaticamente. Por favor indique a língua principal:');
            o('ru', 'ru.js', 1, 'Язык этого сайта не может быть определен автоматически. Пожалуйста укажите язык:');
            o('sk', 'sk.js', 0, '');
            o('sl', 'sl.js', 0, 'Jezika te spletne strani ni bilo mogoče samodejno določiti. Prosim navedite jezik:');
            o('sr-latn', 'sr-latn.js', 0, 'Jezika te spletne strani ni bilo mogoče samodejno določiti. Prosim navedite jezik:');
            o('sv', 'sv.js', 0, 'Spr%E5ket p%E5 den h%E4r webbplatsen kunde inte avg%F6ras automatiskt. V%E4nligen ange:');
            o('ta', 'ta.js', 14, '');
            o('te', 'te.js', 15, '');
            o('tr', 'tr.js', 0, 'Bu web sitesinin dili otomatik olarak tespit edilememiştir. Lütfen dökümanın dilini seçiniz%A0:');
            o('uk', 'uk.js', 1, 'Мова цього веб-сайту не може бути визначена автоматично. Будь ласка, вкажіть головну мову:');
            o('ro', 'ro.js', 0, 'Limba acestui sit nu a putut fi determinată automat. Alege limba principală:');

            return r;
        }()),


        /**
         * @name Hyphenator-basePath
         * @description
         * A string storing the basepath from where Hyphenator.js was loaded.
         * This is used to load the patternfiles.
         * The basepath is determined dynamically by searching all script-tags for Hyphenator.js
         * If the path cannot be determined http://hyphenator.googlecode.com/svn/trunk/ is used as fallback.
         * @type {string}
         * @private
         * @see Hyphenator-loadPatterns
         */
        basePath = (function () {
            var s = contextWindow.document.getElementsByTagName('script'), i = 0, p, src, t = s[i], r = '';
            while (!!t) {
                if (!!t.src) {
                    src = t.src;
                    p = src.indexOf('Hyphenator.js');
                    if (p !== -1) {
                        r = src.substring(0, p);
                    }
                }
                i += 1;
                t = s[i];
            }
            return !!r ? r : 'http://hyphenator.googlecode.com/svn/trunk/';
        }()),

        /**
         * @name Hyphenator-isLocal
         * @private
         * @description
         * isLocal is true, if Hyphenator is loaded from the same domain, as the webpage, but false, if
         * it's loaded from an external source (i.e. directly from google.code)
         */
        isLocal = (function () {
            var re = false;
            if (window.location.href.indexOf(basePath) !== -1) {
                re = true;
            }
            return re;
        }()),

        /**
         * @name Hyphenator-documentLoaded
         * @private
         * @description
         * documentLoaded is true, when the DOM has been loaded. This is set by runOnContentLoaded
         */
        documentLoaded = false,

        /**
         * @name Hyphenator-persistentConfig
         * @private
         * @description
         * if persistentConfig is set to true (defaults to false), config options and the state of the 
         * toggleBox are stored in DOM-storage (according to the storage-setting). So they haven't to be
         * set for each page.
         */
        persistentConfig = false,

        /**
         * @name Hyphenator-doFrames
         * @private
         * @description
         * switch to control if frames/iframes should be hyphenated, too
         * defaults to false (frames are a bag of hurt!)
         */
        doFrames = false,

        /**
         * @name Hyphenator-dontHyphenate
         * @description
         * A key-value object containing all html-tags whose content should not be hyphenated
         * @type {Object.<string,boolean>}
         * @private
         * @see Hyphenator-hyphenateElement
         */
        dontHyphenate = {'script': true, 'code': true, 'pre': true, 'img': true, 'br': true, 'samp': true, 'kbd': true, 'var': true, 'abbr': true, 'acronym': true, 'sub': true, 'sup': true, 'button': true, 'option': true, 'label': true, 'textarea': true, 'input': true, 'math': true, 'svg': true},

        /**
         * @name Hyphenator-enableCache
         * @description
         * A variable to set if caching is enabled or not
         * @type boolean
         * @default true
         * @private
         * @see Hyphenator.config
         * @see hyphenateWord
         */
        enableCache = true,

        /**
         * @name Hyphenator-storageType
         * @description
         * A variable to define what html5-DOM-Storage-Method is used ('none', 'local' or 'session')
         * @type {string}
         * @default 'local'
         * @private
         * @see Hyphenator.config
         */
        storageType = 'local',

        /**
         * @name Hyphenator-storage
         * @description
         * An alias to the storage-Method defined in storageType.
         * Set by Hyphenator.run()
         * @type {Object|undefined}
         * @default null
         * @private
         * @see Hyphenator.run
         */
        storage,

        /**
         * @name Hyphenator-enableReducedPatternSet
         * @description
         * A variable to set if storing the used patterns is set
         * @type boolean
         * @default false
         * @private
         * @see Hyphenator.config
         * @see hyphenateWord
         * @see Hyphenator.getRedPatternSet
         */
        enableReducedPatternSet = false,

        /**
         * @name Hyphenator-enableRemoteLoading
         * @description
         * A variable to set if pattern files should be loaded remotely or not
         * @type boolean
         * @default true
         * @private
         * @see Hyphenator.config
         * @see Hyphenator-loadPatterns
         */
        enableRemoteLoading = true,

        /**
         * @name Hyphenator-displayToggleBox
         * @description
         * A variable to set if the togglebox should be displayed or not
         * @type boolean
         * @default false
         * @private
         * @see Hyphenator.config
         * @see Hyphenator-toggleBox
         */
        displayToggleBox = false,

        /**
         * @name Hyphenator-onError
         * @description
         * A function that can be called upon an error.
         * @see Hyphenator.config
         * @type {function(Object)}
         * @private
         */
        onError = function (e) {
            window.alert("Hyphenator.js says:\n\nAn Error occurred:\n" + e.message);
        },

        /**
         * @name Hyphenator-createElem
         * @description
         * A function alias to document.createElementNS or document.createElement
         * @type {function(string, Object)}
         * @private
         */
        createElem = function (tagname, context) {
            context = context || contextWindow;
            var el;
            if (window.document.createElementNS) {
                el = context.document.createElementNS('http://www.w3.org/1999/xhtml', tagname);
            } else if (window.document.createElement) {
                el = context.document.createElement(tagname);
            }
            return el;
        },

        /**
         * @name Hyphenator-css3
         * @description
         * A variable to set if css3 hyphenation should be used
         * @type boolean
         * @default false
         * @private
         * @see Hyphenator.config
         */
        css3 = false,

        /**
         * @name Hyphenator-css3_hsupport
         * @description
         * A generated object containing information for CSS3-hyphenation support
         * {
         *   support: boolean,
         *   property: <the property name to access hyphen-settings>,
         *   languages: <an object containing supported languages>
         * }
         * @type object
         * @default undefined
         * @private
         * @see Hyphenator-css3_gethsupport
         */
        css3_h9n,

        /**
         * @name Hyphenator-css3_gethsupport
         * @description
         * This function sets Hyphenator-css3_h9n for the current UA
         * @type function
         * @private
         * @see Hyphenator-css3_h9n
         */
        css3_gethsupport = function () {
            var s,
                createLangSupportChecker = function (prefix) {
                    var testStrings = [
                        //latin: 0
                        'aabbccddeeffgghhiijjkkllmmnnooppqqrrssttuuvvwwxxyyzz',
                        //cyrillic: 1
                        'абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
                        //arabic: 2
                        'أبتثجحخدذرزسشصضطظعغفقكلمنهوي',
                        //armenian: 3
                        'աբգդեզէըթժիլխծկհձղճմյնշոչպջռսվտրցւփքօֆ',
                        //bengali: 4
                        'ঁংঃঅআইঈউঊঋঌএঐওঔকখগঘঙচছজঝঞটঠডঢণতথদধনপফবভমযরলশষসহ়ঽািীুূৃৄেৈোৌ্ৎৗড়ঢ়য়ৠৡৢৣ',
                        //devangari: 5
                        'ँंःअआइईउऊऋऌएऐओऔकखगघङचछजझञटठडढणतथदधनपफबभमयरलळवशषसहऽािीुूृॄेैोौ्॒॑ॠॡॢॣ',
                        //greek: 6
                        'αβγδεζηθικλμνξοπρσςτυφχψω',
                        //gujarati: 7
                        'બહઅઆઇઈઉઊઋૠએઐઓઔાિીુૂૃૄૢૣેૈોૌકખગઘઙચછજઝઞટઠડઢણતથદધનપફસભમયરલળવશષ',
                        //kannada: 8
                        'ಂಃಅಆಇಈಉಊಋಌಎಏಐಒಓಔಕಖಗಘಙಚಛಜಝಞಟಠಡಢಣತಥದಧನಪಫಬಭಮಯರಱಲಳವಶಷಸಹಽಾಿೀುೂೃೄೆೇೈೊೋೌ್ೕೖೞೠೡ',
                        //lao: 9
                        'ກຂຄງຈຊຍດຕຖທນບປຜຝພຟມຢຣລວສຫອຮະັາິີຶືຸູົຼເແໂໃໄ່້໊໋ໜໝ',
                        //malayalam: 10
                        'ംഃഅആഇഈഉഊഋഌഎഏഐഒഓഔകഖഗഘങചഛജഝഞടഠഡഢണതഥദധനപഫബഭമയരറലളഴവശഷസഹാിീുൂൃെേൈൊോൌ്ൗൠൡൺൻർൽൾൿ',
                        //oriya: 11
                        'ଁଂଃଅଆଇଈଉଊଋଌଏଐଓଔକଖଗଘଙଚଛଜଝଞଟଠଡଢଣତଥଦଧନପଫବଭମଯରଲଳଵଶଷସହାିୀୁୂୃେୈୋୌ୍ୗୠୡ',
                        //persian: 12
                        'أبتثجحخدذرزسشصضطظعغفقكلمنهوي',
                        //punjabi: 13
                        'ਁਂਃਅਆਇਈਉਊਏਐਓਔਕਖਗਘਙਚਛਜਝਞਟਠਡਢਣਤਥਦਧਨਪਫਬਭਮਯਰਲਲ਼ਵਸ਼ਸਹਾਿੀੁੂੇੈੋੌ੍ੰੱ',
                        //tamil: 14
                        'ஃஅஆஇஈஉஊஎஏஐஒஓஔகஙசஜஞடணதநனபமயரறலளழவஷஸஹாிீுூெேைொோௌ்ௗ',
                        //telugu: 15
                        'ఁంఃఅఆఇఈఉఊఋఌఎఏఐఒఓఔకఖగఘఙచఛజఝఞటఠడఢణతథదధనపఫబభమయరఱలళవశషసహాిీుూృౄెేైొోౌ్ౕౖౠౡ'
                    ],
                        f = function (lang) {
                            var shadow,
                                computedHeight,
                                bdy = window.document.getElementsByTagName('body')[0],
                                r = false;

                            if (supportedLangs.hasOwnProperty(lang)) {
                                //create and append shadow-test-element
                                shadow = createElem('div', window);
                                shadow.id = 'Hyphenator_LanguageChecker';
                                shadow.style.width = '5em';
                                shadow.style[prefix] = 'auto';
                                shadow.style.hyphens = 'auto';
                                shadow.style.fontSize = '12px';
                                shadow.style.lineHeight = '12px';
                                shadow.style.visibility = 'hidden';
                                shadow.lang = lang;
                                shadow.style['-webkit-locale'] = "'" + lang + "'";
                                shadow.innerHTML = testStrings[supportedLangs[lang].script];
                                bdy.appendChild(shadow);
                                //measure its height
                                computedHeight = shadow.offsetHeight;
                                //remove shadow element
                                bdy.removeChild(shadow);
                                r = (computedHeight > 12) ? true : false;
                            } else {
                                r = false;
                            }
                            return r;
                        };
                    return f;
                },
                r = {
                    support: false,
                    property: '',
                    checkLangSupport: function () {}
                };

            if (window.getComputedStyle) {
                s = contextWindow.getComputedStyle(contextWindow.document.getElementsByTagName('body')[0], null);
            } else {
                //ancient Browsers don't support CSS3 anyway
                css3_h9n = r;
                return;
            }

            if (s['-webkit-hyphens'] !== undefined) {
                r.support = true;
                r.property = '-webkit-hyphens';
                r.checkLangSupport = createLangSupportChecker('-webkit-hyphens');
            } else if (s.MozHyphens !== undefined) {
                r.support = true;
                r.property = '-moz-hyphens';
                r.checkLangSupport = createLangSupportChecker('MozHyphens');
            } else if (s['-ms-hyphens'] !== undefined) {
                r.support = true;
                r.property = '-ms-hyphens';
                r.checkLangSupport = createLangSupportChecker('-ms-hyphens');
            }
            css3_h9n = r;
        },

        /**
         * @name Hyphenator-hyphenateClass
         * @description
         * A string containing the css-class-name for the hyphenate class
         * @type {string}
         * @default 'hyphenate'
         * @private
         * @example
         * &lt;p class = "hyphenate"&gt;Text&lt;/p&gt;
         * @see Hyphenator.config
         */
        hyphenateClass = 'hyphenate',

        /**
         * @name Hyphenator-classPrefix
         * @description
         * A string containing a unique className prefix to be used
         * whenever Hyphenator sets a CSS-class
         * @type {string}
         * @private
         */
        classPrefix = 'Hyphenator' + Math.round(Math.random() * 1000),

        /**
         * @name Hyphenator-hideClass
         * @description
         * The name of the class that hides elements
         * @type {string}
         * @private
         */
        hideClass = classPrefix + 'hide',

        /**
         * @name Hyphenator-hideClassRegExp
         * @description
         * RegExp to remove hideClass from a list of classes
         * @type {RegExp}
         * @private
         */
        hideClassRegExp = new RegExp("\\s?\\b" + hideClass + "\\b", "g"),

        /**
         * @name Hyphenator-hideClass
         * @description
         * The name of the class that unhides elements
         * @type {string}
         * @private
         */
        unhideClass = classPrefix + 'unhide',

        /**
         * @name Hyphenator-hideClassRegExp
         * @description
         * RegExp to remove unhideClass from a list of classes
         * @type {RegExp}
         * @private
         */
        unhideClassRegExp = new RegExp("\\s?\\b" + unhideClass + "\\b", "g"),

        /**
         * @name Hyphenator-css3hyphenateClass
         * @description
         * The name of the class that hyphenates elements with css3
         * @type {string}
         * @private
         */
        css3hyphenateClass = classPrefix + 'css3hyphenate',

        /**
         * @name Hyphenator-css3hyphenateClass
         * @description
         * The var where CSSEdit class is stored
         * @type {Object}
         * @private
         */
        css3hyphenateClassHandle,

        /**
         * @name Hyphenator-dontHyphenateClass
         * @description
         * A string containing the css-class-name for elements that should not be hyphenated
         * @type {string}
         * @default 'donthyphenate'
         * @private
         * @example
         * &lt;p class = "donthyphenate"&gt;Text&lt;/p&gt;
         * @see Hyphenator.config
         */
        dontHyphenateClass = 'donthyphenate',

        /**
         * @name Hyphenator-min
         * @description
         * A number wich indicates the minimal length of words to hyphenate.
         * @type {number}
         * @default 6
         * @private
         * @see Hyphenator.config
         */
        min = 6,

        /**
         * @name Hyphenator-orphanControl
         * @description
         * Control how the last words of a line are handled:
         * level 1 (default): last word is hyphenated
         * level 2: last word is not hyphenated
         * level 3: last word is not hyphenated and last space is non breaking
         * @type {number}
         * @default 1
         * @private
         */
        orphanControl = 1,

        /**
         * @name Hyphenator-isBookmarklet
         * @description
         * Indicates if Hyphanetor runs as bookmarklet or not.
         * @type boolean
         * @default false
         * @private
         */
        isBookmarklet = (function () {
            var loc = null,
                re = false,
                scripts = contextWindow.document.getElementsByTagName('script'),
                i = 0,
                l = scripts.length;
            while (!re && i < l) {
                loc = scripts[i].getAttribute('src');
                if (!!loc && loc.indexOf('Hyphenator.js?bm=true') !== -1) {
                    re = true;
                }
                i += 1;
            }
            return re;
        }()),

        /**
         * @name Hyphenator-mainLanguage
         * @description
         * The general language of the document. In contrast to {@link Hyphenator-defaultLanguage},
         * mainLanguage is defined by the client (i.e. by the html or by a prompt).
         * @type {string|null}
         * @private
         * @see Hyphenator-autoSetMainLanguage
         */
        mainLanguage = null,

        /**
         * @name Hyphenator-defaultLanguage
         * @description
         * The language defined by the developper. This language setting is defined by a config option.
         * It is overwritten by any html-lang-attribute and only taken in count, when no such attribute can
         * be found (i.e. just before the prompt).
         * @type {string|null}
         * @private
         * @see Hyphenator-autoSetMainLanguage
         */
        defaultLanguage = '',


        /**
         * @name Hyphenator-elements
         * @description
         * An object holding all elements that have to be hyphenated. This var is filled by
         * {@link Hyphenator-gatherDocumentInfos}
         * @type {Array}
         * @private
         */
        elements = (function () {
            var Element = function (element) {
                this.element = element;
                this.hyphenated = false;
                this.treated = false; //collected but not hyphenated (dohyphenation is off)
            },
                ElementCollection = function () {
                    this.count = 0;
                    this.hyCount = 0;
                    this.list = {};
                };
            ElementCollection.prototype = {
                add: function (el, lang) {
                    if (!this.list.hasOwnProperty(lang)) {
                        this.list[lang] = [];
                    }
                    this.list[lang].push(new Element(el));
                    this.count += 1;
                },
                each: function (fn) {
                    var k;
                    for (k in this.list) {
                        if (this.list.hasOwnProperty(k)) {
                            if (fn.length === 2) {
                                fn(k, this.list[k]);
                            } else {
                                fn(this.list[k]);
                            }
                        }
                    }
                }
            };
            return new ElementCollection();
        }()),


        /**
         * @name Hyphenator-exceptions
         * @description
         * An object containing exceptions as comma separated strings for each language.
         * When the language-objects are loaded, their exceptions are processed, copied here and then deleted.
         * @see Hyphenator-prepareLanguagesObj
         * @type {Object}
         * @private
         */
        exceptions = {},

        /**
         * @name Hyphenator-docLanguages
         * @description
         * An object holding all languages used in the document. This is filled by
         * {@link Hyphenator-gatherDocumentInfos}
         * @type {Object}
         * @private
         */
        docLanguages = {},

        /**
         * @name Hyphenator-state
         * @description
         * A number that inidcates the current state of the script
         * 0: not initialized
         * 1: loading patterns
         * 2: ready
         * 3: hyphenation done
         * 4: hyphenation removed
         * @type {number}
         * @private
         */
        state = 0,

        /**
         * @name Hyphenator-url
         * @description
         * A string containing a RegularExpression to match URL's
         * @type {string}
         * @private
         */
        url = '(\\w*:\/\/)?((\\w*:)?(\\w*)@)?((([\\d]{1,3}\\.){3}([\\d]{1,3}))|((www\\.|[a-zA-Z]\\.)?[a-zA-Z0-9\\-\\.]+\\.([a-z]{2,4})))(:\\d*)?(\/[\\w#!:\\.?\\+=&%@!\\-]*)*',
        //      protocoll     usr     pwd                    ip               or                          host                 tld        port               path

        /**
         * @name Hyphenator-mail
         * @description
         * A string containing a RegularExpression to match mail-adresses
         * @type {string}
         * @private
         */
        mail = '[\\w-\\.]+@[\\w\\.]+',

        /**
         * @name Hyphenator-urlRE
         * @description
         * A RegularExpressions-Object for url- and mail adress matching
         * @type {RegExp}
         * @private
         */
        urlOrMailRE = new RegExp('(' + url + ')|(' + mail + ')', 'i'),

        /**
         * @name Hyphenator-zeroWidthSpace
         * @description
         * A string that holds a char.
         * Depending on the browser, this is the zero with space or an empty string.
         * zeroWidthSpace is used to break URLs
         * @type {string}
         * @private
         */
        zeroWidthSpace = (function () {
            var zws, ua = window.navigator.userAgent.toLowerCase();
            zws = String.fromCharCode(8203); //Unicode zero width space
            if (ua.indexOf('msie 6') !== -1) {
                zws = ''; //IE6 doesn't support zws
            }
            if (ua.indexOf('opera') !== -1 && ua.indexOf('version/10.00') !== -1) {
                zws = ''; //opera 10 on XP doesn't support zws
            }
            return zws;
        }()),

        /**
         * @name Hyphenator-onBeforeWordHyphenation
         * @description
         * A method to be called for each word to be hyphenated before it is hyphenated.
         * Takes the word as a first parameter and its language as a second parameter.
         * Returns a string that will replace the word to be hyphenated.
         * @see Hyphenator.config
         * @type {function()}
         * @private
         */
        onBeforeWordHyphenation = function (word) {
            return word;
        },

        /**
         * @name Hyphenator-onAfterWordHyphenation
         * @description
         * A method to be called for each word to be hyphenated after it is hyphenated.
         * Takes the word as a first parameter and its language as a second parameter.
         * Returns a string that will replace the word that has been hyphenated.
         * @see Hyphenator.config
         * @type {function()}
         * @private
         */
        onAfterWordHyphenation = function (word) {
            return word;
        },

        /**
         * @name Hyphenator-onHyphenationDone
         * @description
         * A method to be called, when the last element has been hyphenated
         * @see Hyphenator.config
         * @type {function()}
         * @private
         */
        onHyphenationDone = function () {},

        /**
         * @name Hyphenator-selectorFunction
         * @description
         * A function set by the user that has to return a HTMLNodeList or array of Elements to be hyphenated.
         * By default this is set to false so we can check if a selectorFunction is set…
         * @see Hyphenator.config
         * @type {function()}
         * @private
         */
        selectorFunction = false,

        /**
         * @name Hyphenator-mySelectorFunction
         * @description
         * A function that has to return a HTMLNodeList or array of Elements to be hyphenated.
         * By default it uses the classname ('hyphenate') to select the elements.
         * @type {function()}
         * @private
         */
        mySelectorFunction = function (hyphenateClass) {
            var tmp, el = [], i, l;
            if (window.document.getElementsByClassName) {
                el = contextWindow.document.getElementsByClassName(hyphenateClass);
            } else if (window.document.querySelectorAll) {
                el = contextWindow.document.querySelectorAll('.' + hyphenateClass);
            } else {
                tmp = contextWindow.document.getElementsByTagName('*');
                l = tmp.length;
                for (i = 0; i < l; i += 1) {
                    if (tmp[i].className.indexOf(hyphenateClass) !== -1 && tmp[i].className.indexOf(dontHyphenateClass) === -1) {
                        el.push(tmp[i]);
                    }
                }
            }
            return el;
        },

        /**
         * @name Hyphenator-selectElements
         * @description
         * A function that has to return a HTMLNodeList or array of Elements to be hyphenated.
         * It uses either selectorFunction set by the user (and adds a unique class to each element)
         * or the default mySelectorFunction.
         * @type {function()}
         * @private
         */
        selectElements = function () {
            var elements;
            if (selectorFunction) {
                elements = selectorFunction();
            } else {
                elements = mySelectorFunction(hyphenateClass);
            }

            return elements;
        },

        /**
         * @name Hyphenator-intermediateState
         * @description
         * The value of style.visibility of the text while it is hyphenated.
         * @see Hyphenator.config
         * @type {string}
         * @private
         */
        intermediateState = 'hidden',

        /**
         * @name Hyphenator-unhide
         * @description
         * How hidden elements unhide: either simultaneous (default: 'wait') or progressively.
         * 'wait' makes Hyphenator.js to wait until all elements are hyphenated (one redraw)
         * With 'progressive' Hyphenator.js unhides elements as soon as they are hyphenated.
         * @see Hyphenator.config
         * @type {string}
         * @private
         */
        unhide = 'wait',

        /**
         * @name Hyphenator-CSSEditors
         * @description A container array that holds CSSEdit classes
         * For each window object one CSSEdit class is inserted
         * @see Hyphenator-CSSEdit
         * @type {array}
         * @private
         */
        CSSEditors = [],

        /**
         * @name Hyphenator-CSSEditors
         * @description A custom class with two public methods: setRule() and clearChanges()
         * Rather sets style for CSS-classes then for single elements
         * This is used to hide/unhide elements when they are hyphenated.
         * @see Hyphenator-gatherDocumentInfos
         * @type {function ()}
         * @private
         */
        CSSEdit = function (w) {
            w = w || window;
            var doc = w.document,
                //find/create an accessible StyleSheet
                sheet = (function () {
                    var i,
                        l = doc.styleSheets.length,
                        sheet,
                        element,
                        r = false;
                    for (i = 0; i < l; i += 1) {
                        sheet = doc.styleSheets[i];
                        try {
                            if (!!sheet.cssRules) {
                                r = sheet;
                                break;
                            }
                        } catch (e) {}
                    }
                    if (r === false) {
                        element = doc.createElement('style');
                        element.type = 'text/css';
                        doc.getElementsByTagName('head')[0].appendChild(element);
                        r = doc.styleSheets[doc.styleSheets.length - 1];
                    }
                    return r;
                }()),
                changes = [],
                findRule = function (sel) {
                    var sheet, rule, sheets = window.document.styleSheets, rules, i, j, r = false;
                    for (i = 0; i < sheets.length; i += 1) {
                        sheet = sheets[i];
                        try { //FF has issues here with external CSS (s.o.p)
                            if (!!sheet.cssRules) {
                                rules = sheet.cssRules;
                            } else if (!!sheet.rules) {
                                // IE < 9
                                rules = sheet.rules;
                            }
                        } catch (e) {
                            //do nothing
                            //console.log(e);
                        }
                        if (!!rules && !!rules.length) {
                            for (j = 0; j < rules.length; j += 1) {
                                rule = rules[j];
                                if (rule.selectorText === sel) {
                                    r = {
                                        index: j,
                                        rule: rule
                                    };
                                }
                            }
                        }
                    }
                    return r;
                },
                addRule = function (sel, rulesStr) {
                    var i, r;
                    if (!!sheet.insertRule) {
                        if (!!sheet.cssRules) {
                            i = sheet.cssRules.length;
                        } else {
                            i = 0;
                        }
                        r = sheet.insertRule(sel + '{' + rulesStr + '}', i);
                    } else if (!!sheet.addRule) {
                        // IE < 9
                        if (!!sheet.rules) {
                            i = sheet.rules.length;
                        } else {
                            i = 0;
                        }
                        sheet.addRule(sel, rulesStr, i);
                        r = i;
                    }
                    return r;
                },
                removeRule = function (sheet, index) {
                    if (sheet.deleteRule) {
                        sheet.deleteRule(index);
                    } else {
                        // IE < 9
                        sheet.removeRule(index);
                    }
                };

            return {
                setRule: function (sel, rulesString) {
                    var i, existingRule, cssText;
                    existingRule = findRule(sel);
                    if (!!existingRule) {
                        if (!!existingRule.rule.cssText) {
                            cssText = existingRule.rule.cssText;
                        } else {
                            // IE < 9
                            cssText = existingRule.rule.style.cssText.toLowerCase();
                        }
                        if (cssText === '.' + hyphenateClass + ' { visibility: hidden; }') {
                            //browsers w/o IE < 9 and no additional style defs:
                            //add to [changes] for later removal
                            changes.push({sheet: existingRule.rule.parentStyleSheet, index: existingRule.index});
                        } else if (cssText.indexOf('visibility: hidden') !== -1) {
                            // IE < 9 or additional style defs:
                            // add new rule
                            i = addRule(sel, rulesString);
                            //add to [changes] for later removal
                            changes.push({sheet: sheet, index: i});
                            // clear existing def
                            existingRule.rule.style.visibility = '';
                        } else {
                            addRule(sel, rulesString);
                        }
                    } else {
                        i = addRule(sel, rulesString);
                        changes.push({sheet: sheet, index: i});
                    }
                },
                clearChanges: function () {
                    var change = changes.pop();
                    while (!!change) {
                        removeRule(change.sheet, change.index);
                        change = changes.pop();
                    }
                }
            };
        },

        /**
         * @name Hyphenator-hyphen
         * @description
         * A string containing the character for in-word-hyphenation
         * @type {string}
         * @default the soft hyphen
         * @private
         * @see Hyphenator.config
         */
        hyphen = String.fromCharCode(173),

        /**
         * @name Hyphenator-urlhyphen
         * @description
         * A string containing the character for url/mail-hyphenation
         * @type {string}
         * @default the zero width space
         * @private
         * @see Hyphenator.config
         * @see Hyphenator-zeroWidthSpace
         */
        urlhyphen = zeroWidthSpace,

        /**
         * @name Hyphenator-safeCopy
         * @description
         * Defines wether work-around for copy issues is active or not
         * Not supported by Opera (no onCopy handler)
         * @type boolean
         * @default true
         * @private
         * @see Hyphenator.config
         * @see Hyphenator-registerOnCopy
         */
        safeCopy = true,

        /*
         * runOnContentLoaded is based od jQuery.bindReady()
         * see
         * jQuery JavaScript Library v1.3.2
         * http://jquery.com/
         *
         * Copyright (c) 2009 John Resig
         * Dual licensed under the MIT and GPL licenses.
         * http://docs.jquery.com/License
         *
         * Date: 2009-02-19 17:34:21 -0500 (Thu, 19 Feb 2009)
         * Revision: 6246
         */
        /**
         * @name Hyphenator-runOnContentLoaded
         * @description
         * A crossbrowser solution for the DOMContentLoaded-Event based on jQuery
         * <a href = "http://jquery.com/</a>
         * I added some functionality: e.g. support for frames and iframes…
         * @param {Object} w the window-object
         * @param {function()} f the function to call onDOMContentLoaded
         * @private
         */
        runOnContentLoaded = function (w, f) {
            var
                toplevel, hyphRunForThis = {},
                add = window.document.addEventListener ? 'addEventListener' : 'attachEvent',
                rem = window.document.addEventListener ? 'removeEventListener' : 'detachEvent',
                pre = window.document.addEventListener ? '' : 'on',

                init = function (context) {
                    contextWindow = context || window;
                    if (!hyphRunForThis[contextWindow.location.href] && (!documentLoaded || !!contextWindow.frameElement)) {
                        documentLoaded = true;
                        f();
                        hyphRunForThis[contextWindow.location.href] = true;
                    }
                },

                doScrollCheck = function () {
                    try {
                        // If IE is used, use the trick by Diego Perini
                        // http://javascript.nwbox.com/IEContentLoaded/
                        contextWindow.document.documentElement.doScroll("left");
                    } catch (error) {
                        window.setTimeout(doScrollCheck, 1);
                        return;
                    }

                    // and execute any waiting functions
                    init(window);
                },

                doOnLoad = function () {
                    var i, haveAccess, fl = window.frames.length;
                    if (doFrames && fl > 0) {
                        for (i = 0; i < fl; i += 1) {
                            haveAccess = undefined;
                            //try catch isn't enough for webkit
                            try {
                                //opera throws only on document.toString-access
                                haveAccess = window.frames[i].document.toString();
                            } catch (e) {
                                haveAccess = undefined;
                            }
                            if (!!haveAccess) {
                                if (window.frames[i].location.href !== 'about:blank') {
                                    init(window.frames[i]);
                                }
                            }
                        }
                        contextWindow = window;
                        f();
                        hyphRunForThis[window.location.href] = true;
                    } else {
                        init(window);
                    }
                },

                // Cleanup functions for the document ready method
                DOMContentLoaded = function (e) {
                    if (e.type === 'readystatechange' && contextWindow.document.readyState !== 'complete') {
                        return;
                    }
                    contextWindow.document[rem](pre + e.type, DOMContentLoaded, false);
                    if (!doFrames && window.frames.length === 0) {
                        init(window);
                    } /* else {
                        //we are in a frameset, so do nothing but wait for onload to fire
                        
                    }*/
                };

            if (documentLoaded && !hyphRunForThis[w.location.href]) {
                f();
                hyphRunForThis[w.location.href] = true;
                return;
            }

            if (contextWindow.document.readyState === "complete" || contextWindow.document.readyState === "interactive") {
                //Running Hyphenator.js if it has been loaded later
                //Thanks to davenewtron http://code.google.com/p/hyphenator/issues/detail?id=158#c10
                window.setTimeout(doOnLoad, 1);
            } else {
                //registering events
                contextWindow.document[add](pre + "DOMContentLoaded", DOMContentLoaded, false);
                contextWindow.document[add](pre + 'readystatechange', DOMContentLoaded, false);
                window[add](pre + 'load', doOnLoad, false);
                toplevel = false;
                try {
                    toplevel = !window.frameElement;
                } catch (e) {}
                if (contextWindow.document.documentElement.doScroll && toplevel) {
                    doScrollCheck();
                }
            }
        },

        /**
         * @name Hyphenator-getLang
         * @description
         * Gets the language of an element. If no language is set, it may use the {@link Hyphenator-mainLanguage}.
         * @param {Object} el The first parameter is an DOM-Element-Object
         * @param {boolean} fallback The second parameter is a boolean to tell if the function should return the {@link Hyphenator-mainLanguage}
         * if there's no language found for the element.
         * @private
         */
        getLang = function (el, fallback) {
            try {
                return !!el.getAttribute('lang') ? el.getAttribute('lang').toLowerCase() :
                        !!el.getAttribute('xml:lang') ? el.getAttribute('xml:lang').toLowerCase() :
                                el.tagName.toLowerCase() !== 'html' ? getLang(el.parentNode, fallback) :
                                        fallback ? mainLanguage :
                                                null;
            } catch (e) {}
        },

        /**
         * @name Hyphenator-autoSetMainLanguage
         * @description
         * Retrieves the language of the document from the DOM.
         * The function looks in the following places:
         * <ul>
         * <li>lang-attribute in the html-tag</li>
         * <li>&lt;meta http-equiv = "content-language" content = "xy" /&gt;</li>
         * <li>&lt;meta name = "DC.Language" content = "xy" /&gt;</li>
         * <li>&lt;meta name = "language" content = "xy" /&gt;</li>
         * </li>
         * If nothing can be found a prompt using {@link Hyphenator-languageHint} and a prompt-string is displayed.
         * If the retrieved language is in the object {@link Hyphenator-supportedLangs} it is copied to {@link Hyphenator-mainLanguage}
         * @private
         */
        autoSetMainLanguage = function (w) {
            w = w || contextWindow;
            var el = w.document.getElementsByTagName('html')[0],
                m = w.document.getElementsByTagName('meta'),
                i,
                getLangFromUser = function () {
                    var mainLanguage,
                        text = '',
                        dH = 300,
                        dW = 450,
                        dX = Math.floor((w.outerWidth - dW) / 2) + window.screenX,
                        dY = Math.floor((w.outerHeight - dH) / 2) + window.screenY,
                        ul = '',
                        languageHint;
                    if (!!window.showModalDialog) {
                        mainLanguage = window.showModalDialog(basePath + 'modalLangDialog.html', supportedLangs, "dialogWidth: " + dW + "px; dialogHeight: " + dH + "px; dialogtop: " + dY + "; dialogleft: " + dX + "; center: on; resizable: off; scroll: off;");
                    } else {
                        languageHint = (function () {
                            var k, r = '';
                            for (k in supportedLangs) {
                                if (supportedLangs.hasOwnProperty(k)) {
                                    r += k + ', ';
                                }
                            }
                            r = r.substring(0, r.length - 2);
                            return r;
                        }());
                        ul = window.navigator.language || window.navigator.userLanguage;
                        ul = ul.substring(0, 2);
                        if (!!supportedLangs[ul] && supportedLangs[ul].prompt !== '') {
                            text = supportedLangs[ul].prompt;
                        } else {
                            text = supportedLangs.en.prompt;
                        }
                        text += ' (ISO 639-1)\n\n' + languageHint;
                        mainLanguage = window.prompt(window.unescape(text), ul).toLowerCase();
                    }
                    return mainLanguage;
                };
            mainLanguage = getLang(el, false);
            if (!mainLanguage) {
                for (i = 0; i < m.length; i += 1) {
                    //<meta http-equiv = "content-language" content="xy">
                    if (!!m[i].getAttribute('http-equiv') && (m[i].getAttribute('http-equiv').toLowerCase() === 'content-language')) {
                        mainLanguage = m[i].getAttribute('content').toLowerCase();
                    }
                    //<meta name = "DC.Language" content="xy">
                    if (!!m[i].getAttribute('name') && (m[i].getAttribute('name').toLowerCase() === 'dc.language')) {
                        mainLanguage = m[i].getAttribute('content').toLowerCase();
                    }
                    //<meta name = "language" content = "xy">
                    if (!!m[i].getAttribute('name') && (m[i].getAttribute('name').toLowerCase() === 'language')) {
                        mainLanguage = m[i].getAttribute('content').toLowerCase();
                    }
                }
            }
            //get lang for frame from enclosing document
            if (!mainLanguage && doFrames && (!!contextWindow.frameElement)) {
                autoSetMainLanguage(window.parent);
            }
            //fallback to defaultLang if set
            if (!mainLanguage && defaultLanguage !== '') {
                mainLanguage = defaultLanguage;
            }
            //ask user for lang
            if (!mainLanguage) {
                mainLanguage = getLangFromUser();
            }
            el.lang = mainLanguage;
        },

        /**
         * @name Hyphenator-gatherDocumentInfos
         * @description
         * This method runs through the DOM and executes the process()-function on:
         * - every node returned by the {@link Hyphenator-selectorFunction}.
         * The process()-function copies the element to the elements-variable, sets its visibility
         * to intermediateState, retrieves its language and recursivly descends the DOM-tree until
         * the child-Nodes aren't of type 1
         * @private
         */
        gatherDocumentInfos = function () {
            var elToProcess, tmp, i = 0,
                process = function (el, lang) {
                    var n, i = 0, hyphenate = true;

                    if (el.lang && typeof (el.lang) === 'string') {
                        lang = el.lang.toLowerCase(); //copy attribute-lang to internal lang
                    } else if (lang) {
                        lang = lang.toLowerCase();
                    } else {
                        lang = getLang(el, true);
                    }
                    //if css3-hyphenation is supported: use it!
                    if (css3 && css3_h9n.support && !!css3_h9n.checkLangSupport(lang)) {
                        css3hyphenateClassHandle =  new CSSEdit(contextWindow);
                        css3hyphenateClassHandle.setRule('.' + css3hyphenateClass, css3_h9n.property + ': auto;');
                        css3hyphenateClassHandle.setRule('.' + dontHyphenateClass, css3_h9n.property + ': none;');
                        css3hyphenateClassHandle.setRule('.' + css3hyphenateClass, '-webkit-locale : ' + lang + ';');

                        el.className = el.className + ' ' + css3hyphenateClass;
                    } else {
                        if (supportedLangs.hasOwnProperty(lang)) {
                            docLanguages[lang] = true;
                        } else {
                            if (supportedLangs.hasOwnProperty(lang.split('-')[0])) { //try subtag
                                lang = lang.split('-')[0];
                                docLanguages[lang] = true;
                            } else if (!isBookmarklet) {
                                hyphenate = false;
                                onError(new Error('Language "' + lang + '" is not yet supported.'));
                            }
                        }
                        if (hyphenate) {
                            if (intermediateState === 'hidden') {
                                el.className = el.className + ' ' + hideClass;
                            }
                            elements.add(el, lang);
                        }
                    }
                    n = el.childNodes[i];
                    while (!!n) {
                        if (n.nodeType === 1 && !dontHyphenate[n.nodeName.toLowerCase()] &&
                                n.className.indexOf(dontHyphenateClass) === -1 && !elToProcess[n]) {
                            process(n, lang);
                        }
                        i += 1;
                        n = el.childNodes[i];
                    }
                };
            if (css3) {
                css3_gethsupport();
            }
            if (isBookmarklet) {
                elToProcess = contextWindow.document.getElementsByTagName('body')[0];
                process(elToProcess, mainLanguage);
            } else {
                if (!css3 && intermediateState === 'hidden') {
                    CSSEditors.push(new CSSEdit(contextWindow));
                    CSSEditors[CSSEditors.length - 1].setRule('.' + hyphenateClass, 'visibility: hidden;');
                    CSSEditors[CSSEditors.length - 1].setRule('.' + hideClass, 'visibility: hidden;');
                    CSSEditors[CSSEditors.length - 1].setRule('.' + unhideClass, 'visibility: visible;');
                }
                elToProcess = selectElements();
                tmp = elToProcess[i];
                while (!!tmp) {
                    process(tmp, '');
                    i += 1;
                    tmp = elToProcess[i];
                }
            }
            if (elements.count === 0) {
                //nothing to hyphenate or all hyphenated by css3
                for (i = 0; i < CSSEditors.length; i += 1) {
                    CSSEditors[i].clearChanges();
                }
                state = 3;
                onHyphenationDone();
            }
        },

        /**
         * @name Hyphenator-createTrie
         * @description
         * converts patterns of the given language in a trie
         * @private
         * @param {string} lang the language whose patterns shall be converted
         */
        convertPatterns = function (lang) {
            /** @license BSD licenced code
             * The following code is based on code from hypher.js and adapted for Hyphenator.js
             * Copyright (c) 2011, Bram Stein
             */
            var size = 0,
                tree = {
                    tpoints: []
                },
                patterns,
                pattern,
                i,
                j,
                k,
                patternObject = Hyphenator.languages[lang].patterns,
                c,
                chars,
                points,
                t,
                p,
                codePoint,
                test = 'in3se',
                rf,
                getPoints = (function () {
                    //IE<9 doesn't act like other browsers: doesn't preserve the separators
                    if (test.split(/\D/).length === 1) {
                        rf = function (pattern) {
                            pattern = pattern.replace(/\D/gi, ' ');
                            return pattern.split(' ');
                        };
                    } else {
                        rf = function (pattern) {
                            return pattern.split(/\D/);
                        };
                    }
                    return rf;
                }());

            for (size in patternObject) {
                if (patternObject.hasOwnProperty(size)) {
                    patterns = patternObject[size].match(new RegExp('.{1,' + (+size) + '}', 'g'));
                    i = 0;
                    pattern = patterns[i];
                    while (!!pattern) {
                        chars = pattern.replace(/[\d]/g, '').split('');
                        points = getPoints(pattern);
                        t = tree;

                        j = 0;
                        c = chars[j];
                        while (!!c) {
                            codePoint = c.charCodeAt(0);

                            if (!t[codePoint]) {
                                t[codePoint] = {};
                            }
                            t = t[codePoint];
                            j += 1;
                            c = chars[j];
                        }

                        t.tpoints = [];
                        for (k = 0; k < points.length; k += 1) {
                            p = points[k];
                            t.tpoints.push((p === "") ? 0 : p);
                        }
                        i += 1;
                        pattern = patterns[i];
                    }
                }
            }
            Hyphenator.languages[lang].patterns = tree;
            /**
             * end of BSD licenced code from hypher.js
             */
        },

        /**
         * @name Hyphenator-recreatePattern
         * @description
         * Recreates the pattern for the reducedPatternSet
         * @private
         */
        recreatePattern = function (pattern, nodePoints) {
            var r = [], c = pattern.split(''), i;
            for (i = 0; i < nodePoints.length; i += 1) {
                if (nodePoints[i] !== 0) {
                    r.push(nodePoints[i]);
                }
                if (c[i]) {
                    r.push(c[i]);
                }
            }
            return r.join('');
        },

        /**
         * @name Hyphenator-convertExceptionsToObject
         * @description
         * Converts a list of comma seprated exceptions to an object:
         * 'Fortran,Hy-phen-a-tion' -> {'Fortran':'Fortran','Hyphenation':'Hy-phen-a-tion'}
         * @private
         * @param {string} exc a comma separated string of exceptions (without spaces)
         */
        convertExceptionsToObject = function (exc) {
            var w = exc.split(', '),
                r = {},
                i,
                l,
                key;
            for (i = 0, l = w.length; i < l; i += 1) {
                key = w[i].replace(/-/g, '');
                if (!r.hasOwnProperty(key)) {
                    r[key] = w[i];
                }
            }
            return r;
        },

        /**
         * @name Hyphenator-loadPatterns
         * @description
         * Checks if the requested file is available in the network.
         * Adds a &lt;script&gt;-Tag to the DOM to load an externeal .js-file containing patterns and settings for the given language.
         * If the given language is not in the {@link Hyphenator-supportedLangs}-Object it returns.
         * One may ask why we are not using AJAX to load the patterns. The XMLHttpRequest-Object 
         * has a same-origin-policy. This makes the Bookmarklet impossible.
         * @param {string} lang The language to load the patterns for
         * @private
         * @see Hyphenator-basePath
         */
        loadPatterns = function (lang) {
            var url, xhr, head, script;
            if (supportedLangs.hasOwnProperty(lang) && !Hyphenator.languages[lang]) {
                url = basePath + 'patterns/' + supportedLangs[lang].file;
            } else {
                return;
            }
            if (isLocal && !isBookmarklet) {
                //check if 'url' is available:
                xhr = null;
                try {
                    // Mozilla, Opera, Safari and Internet Explorer (ab v7)
                    xhr = new window.XMLHttpRequest();
                } catch (e) {
                    try {
                        //IE>=6
                        xhr  = new window.ActiveXObject("Microsoft.XMLHTTP");
                    } catch (e2) {
                        try {
                            //IE>=5
                            xhr  = new window.ActiveXObject("Msxml2.XMLHTTP");
                        } catch (e3) {
                            xhr  = null;
                        }
                    }
                }

                if (xhr) {
                    xhr.open('HEAD', url, true);
                    xhr.setRequestHeader('Cache-Control', 'no-cache');
                    xhr.onreadystatechange = function () {
                        if (xhr.readyState === 4) {
                            if (xhr.status === 404) {
                                onError(new Error('Could not load\n' + url));
                                delete docLanguages[lang];
                                return;
                            }
                        }
                    };
                    xhr.send(null);
                }
            }
            if (createElem) {
                head = window.document.getElementsByTagName('head').item(0);
                script = createElem('script', window);
                script.src = url;
                script.type = 'text/javascript';
                head.appendChild(script);
            }
        },

        /**
         * @name Hyphenator-prepareLanguagesObj
         * @description
         * Adds a cache to each language and converts the exceptions-list to an object.
         * If storage is active the object is stored there.
         * @private
         * @param {string} lang the language ob the lang-obj
         */
        prepareLanguagesObj = function (lang) {
            var lo = Hyphenator.languages[lang], wrd;
            if (!lo.prepared) {
                if (enableCache) {
                    lo.cache = {};
                    //Export
                    //lo['cache'] = lo.cache;
                }
                if (enableReducedPatternSet) {
                    lo.redPatSet = {};
                }
                //add exceptions from the pattern file to the local 'exceptions'-obj
                if (lo.hasOwnProperty('exceptions')) {
                    Hyphenator.addExceptions(lang, lo.exceptions);
                    delete lo.exceptions;
                }
                //copy global exceptions to the language specific exceptions
                if (exceptions.hasOwnProperty('global')) {
                    if (exceptions.hasOwnProperty(lang)) {
                        exceptions[lang] += ', ' + exceptions.global;
                    } else {
                        exceptions[lang] = exceptions.global;
                    }
                }
                //move exceptions from the the local 'exceptions'-obj to the 'language'-object
                if (exceptions.hasOwnProperty(lang)) {
                    lo.exceptions = convertExceptionsToObject(exceptions[lang]);
                    delete exceptions[lang];
                } else {
                    lo.exceptions = {};
                }
                convertPatterns(lang);
                wrd = '[\\w' + lo.specialChars + '@' + String.fromCharCode(173) + String.fromCharCode(8204) + '-]{' + min + ',}';
                lo.genRegExp = new RegExp('(' + url + ')|(' + mail + ')|(' + wrd + ')', 'gi');
                lo.prepared = true;
            }
            if (!!storage) {
                try {
                    storage.setItem(lang, window.JSON.stringify(lo));
                } catch (e) {
                    onError(e);
                }
            }

        },

        /**
         * @name Hyphenator-prepare
         * @description
         * This funtion prepares the Hyphenator-Object: If RemoteLoading is turned off, it assumes
         * that the patternfiles are loaded, all conversions are made and the callback is called.
         * If storage is active the object is retrieved there.
         * If RemoteLoading is on (default), it loads the pattern files and waits until they are loaded,
         * by repeatedly checking Hyphenator.languages. If a patterfile is loaded the patterns are
         * converted to their object style and the lang-object extended.
         * Finally the callback is called.
         * @private
         */
        prepare = function (callback) {
            var lang, interval, tmp1, tmp2;
            if (!enableRemoteLoading) {
                for (lang in Hyphenator.languages) {
                    if (Hyphenator.languages.hasOwnProperty(lang)) {
                        prepareLanguagesObj(lang);
                    }
                }
                state = 2;
                callback('*');
                return;
            }
            // get all languages that are used and preload the patterns
            state = 1;
            for (lang in docLanguages) {
                if (docLanguages.hasOwnProperty(lang)) {
                    if (!!storage && storage.test(lang)) {
                        Hyphenator.languages[lang] = window.JSON.parse(storage.getItem(lang));
                        if (exceptions.hasOwnProperty('global')) {
                            tmp1 = convertExceptionsToObject(exceptions.global);
                            for (tmp2 in tmp1) {
                                if (tmp1.hasOwnProperty(tmp2)) {
                                    Hyphenator.languages[lang].exceptions[tmp2] = tmp1[tmp2];
                                }
                            }
                        }
                        //Replace exceptions since they may have been changed:
                        if (exceptions.hasOwnProperty(lang)) {
                            tmp1 = convertExceptionsToObject(exceptions[lang]);
                            for (tmp2 in tmp1) {
                                if (tmp1.hasOwnProperty(tmp2)) {
                                    Hyphenator.languages[lang].exceptions[tmp2] = tmp1[tmp2];
                                }
                            }
                            delete exceptions[lang];
                        }
                        //Replace genRegExp since it may have been changed:
                        tmp1 = '[\\w' + Hyphenator.languages[lang].specialChars + '@' + String.fromCharCode(173) + String.fromCharCode(8204) + '-]{' + min + ',}';
                        Hyphenator.languages[lang].genRegExp = new RegExp('(' + url + ')|(' + mail + ')|(' + tmp1 + ')', 'gi');

                        delete docLanguages[lang];
                        callback(lang);
                    } else {
                        loadPatterns(lang);
                    }
                }
            }
            // else async wait until patterns are loaded, then hyphenate
            interval = window.setInterval(function () {
                var finishedLoading = true, lang;
                for (lang in docLanguages) {
                    if (docLanguages.hasOwnProperty(lang)) {
                        finishedLoading = false;
                        if (!!Hyphenator.languages[lang]) {
                            delete docLanguages[lang];
                            //do conversion while other patterns are loading:
                            prepareLanguagesObj(lang);
                            callback(lang);
                        }
                    }
                }
                if (finishedLoading) {
                    window.clearInterval(interval);
                    state = 2;
                }
            }, 100);
        },

        /**
         * @name Hyphenator-switchToggleBox
         * @description
         * Creates or hides the toggleBox: a small button to turn off/on hyphenation on a page.
         * @see Hyphenator.config
         * @private
         */
        toggleBox = function () {
            var bdy, myTextNode,
                text = (Hyphenator.doHyphenation ? 'Hy-phen-a-tion' : 'Hyphenation'),
                myBox = contextWindow.document.getElementById('HyphenatorToggleBox');
            if (!!myBox) {
                myBox.firstChild.data = text;
            } else {
                bdy = contextWindow.document.getElementsByTagName('body')[0];
                myBox = createElem('div', contextWindow);
                myBox.setAttribute('id', 'HyphenatorToggleBox');
                myBox.setAttribute('class', dontHyphenateClass);
                myTextNode = contextWindow.document.createTextNode(text);
                myBox.appendChild(myTextNode);
                myBox.onclick =  Hyphenator.toggleHyphenation;
                myBox.style.position = 'absolute';
                myBox.style.top = '0px';
                myBox.style.right = '0px';
                myBox.style.margin = '0';
                myBox.style.backgroundColor = '#AAAAAA';
                myBox.style.color = '#FFFFFF';
                myBox.style.font = '6pt Arial';
                myBox.style.letterSpacing = '0.2em';
                myBox.style.padding = '3px';
                myBox.style.cursor = 'pointer';
                myBox.style.WebkitBorderBottomLeftRadius = '4px';
                myBox.style.MozBorderRadiusBottomleft = '4px';
                myBox.style.borderBottomLeftRadius = '4px';
                bdy.appendChild(myBox);
            }
        },


        /**
         * @name Hyphenator-hyphenateWord
         * @description
         * This function is the heart of Hyphenator.js. It returns a hyphenated word.
         *
         * If there's already a {@link Hyphenator-hypen} in the word, the word is returned as it is.
         * If the word is in the exceptions list or in the cache, it is retrieved from it.
         * If there's a '-' put a zeroWidthSpace after the '-' and hyphenate the parts.
         * @param {string} lang The language of the word
         * @param {string} word The word
         * @returns string The hyphenated word
         * @public
         */
        hyphenateWord = function (lang, word) {
            var lo = Hyphenator.languages[lang], parts, l, subst,
                w, characters, origWord, originalCharacters, wordLength, i, j, k, node, points = [],
                characterPoints = [], nodePoints, nodePointsLength, m = Math.max, trie,
                result = [''], pattern, r;
            word = onBeforeWordHyphenation(word, lang);
            if (word === '') {
                r = '';
            } else if (enableCache && lo.cache.hasOwnProperty(word)) { //the word is in the cache
                r = lo.cache[word];
            } else if (word.indexOf(hyphen) !== -1) {
                //word already contains shy; -> leave at it is!
                r = word;
            } else if (lo.exceptions.hasOwnProperty(word)) { //the word is in the exceptions list
                r = lo.exceptions[word].replace(/-/g, hyphen);
            } else if (word.indexOf('-') !== -1) {
                //word contains '-' -> hyphenate the parts separated with '-'
                parts = word.split('-');
                for (i = 0, l = parts.length; i < l; i += 1) {
                    parts[i] = hyphenateWord(lang, parts[i]);
                }
                r = parts.join('-');
            } else {
                origWord = word;
                w = word = '_' + word + '_';
                if (!!lo.charSubstitution) {
                    for (subst in lo.charSubstitution) {
                        if (lo.charSubstitution.hasOwnProperty(subst)) {
                            w = w.replace(new RegExp(subst, 'g'), lo.charSubstitution[subst]);
                        }
                    }
                }
                if (origWord.indexOf("'") !== -1) {
                    w = w.replace("'", "’"); //replace APOSTROPHE with RIGHT SINGLE QUOTATION MARK (since the latter is used in the patterns)
                }
                /** @license BSD licenced code
                 * The following code is based on code from hypher.js
                 * Copyright (c) 2011, Bram Stein
                 */
                characters = w.toLowerCase().split('');
                originalCharacters = word.split('');
                wordLength = characters.length;
                trie = lo.patterns;
                for (i = 0; i < wordLength; i += 1) {
                    points[i] = 0;
                    characterPoints[i] = characters[i].charCodeAt(0);
                }
                for (i = 0; i < wordLength; i += 1) {
                    pattern = '';
                    node = trie;
                    for (j = i; j < wordLength; j += 1) {
                        node = node[characterPoints[j]];
                        if (node) {
                            if (enableReducedPatternSet) {
                                pattern += String.fromCharCode(characterPoints[j]);
                            }
                            nodePoints = node.tpoints;
                            if (nodePoints) {
                                if (enableReducedPatternSet) {
                                    if (!lo.redPatSet) {
                                        lo.redPatSet = {};
                                    }
                                    lo.redPatSet[pattern] = recreatePattern(pattern, nodePoints);
                                }
                                for (k = 0, nodePointsLength = nodePoints.length; k < nodePointsLength; k += 1) {
                                    points[i + k] = m(points[i + k], nodePoints[k]);
                                }
                            }
                        } else {
                            break;
                        }
                    }
                }
                for (i = 1; i < wordLength - 1; i += 1) {
                    if (i > lo.leftmin && i < (wordLength - lo.rightmin) && points[i] % 2) {
                        result.push(originalCharacters[i]);
                    } else {
                        result[result.length - 1] += originalCharacters[i];
                    }
                }
                r = result.join(hyphen);
                /**
                 * end of BSD licenced code from hypher.js
                 */
            }
            r = onAfterWordHyphenation(r, lang);
            if (enableCache) { //put the word in the cache
                lo.cache[origWord] = r;
            }
            return r;
        },

        /**
         * @name Hyphenator-hyphenateURL
         * @description
         * Puts {@link Hyphenator-urlhyphen} after each no-alphanumeric char that my be in a URL.
         * @param {string} url to hyphenate
         * @returns string the hyphenated URL
         * @public
         */
        hyphenateURL = function (url) {
            return url.replace(/([:\/\.\?#&_,;!@]+)/gi, '$&' + urlhyphen);
        },

        /**
         * @name Hyphenator-removeHyphenationFromElement
         * @description
         * Removes all hyphens from the element. If there are other elements, the function is
         * called recursively.
         * Removing hyphens is usefull if you like to copy text. Some browsers are buggy when the copy hyphenated texts.
         * @param {Object} el The element where to remove hyphenation.
         * @public
         */
        removeHyphenationFromElement = function (el) {
            var h, i = 0, n;
            switch (hyphen) {
            case '|':
                h = '\\|';
                break;
            case '+':
                h = '\\+';
                break;
            case '*':
                h = '\\*';
                break;
            default:
                h = hyphen;
            }
            n = el.childNodes[i];
            while (!!n) {
                if (n.nodeType === 3) {
                    n.data = n.data.replace(new RegExp(h, 'g'), '');
                    n.data = n.data.replace(new RegExp(zeroWidthSpace, 'g'), '');
                } else if (n.nodeType === 1) {
                    removeHyphenationFromElement(n);
                }
                i += 1;
                n = el.childNodes[i];
            }
        },

        /**
         * @name Hyphenator-oncopyHandler
         * @description
         * The function called by registerOnCopy
         * @private
         */
        oncopyHandler,

        /**
         * @name Hyphenator-removeOnCopy
         * @description
         * Method to remove copy event handler from the given element
         * @param object a html object from witch we remove the event
         * @private
         */
        removeOnCopy = function (el) {
            var body = el.ownerDocument.getElementsByTagName('body')[0];
            if (!body) {
                return;
            }
            el = el || body;
            if (window.removeEventListener) {
                el.removeEventListener("copy", oncopyHandler, true);
            } else {
                el.detachEvent("oncopy", oncopyHandler);
            }
        },

        /**
         * @name Hyphenator-registerOnCopy
         * @description
         * Huge work-around for browser-inconsistency when it comes to
         * copying of hyphenated text.
         * The idea behind this code has been provided by http://github.com/aristus/sweet-justice
         * sweet-justice is under BSD-License
         * @param object an HTML element where the copy event will be registered to
         * @private
         */
        registerOnCopy = function (el) {
            var body = el.ownerDocument.getElementsByTagName('body')[0],
                shadow,
                selection,
                range,
                rangeShadow,
                restore;
            oncopyHandler = function (e) {
                e = e || window.event;
                var target = e.target || e.srcElement,
                    currDoc = target.ownerDocument,
                    body = currDoc.getElementsByTagName('body')[0],
                    targetWindow = currDoc.defaultView || currDoc.parentWindow;
                if (target.tagName && dontHyphenate[target.tagName.toLowerCase()]) {
                    //Safari needs this
                    return;
                }
                //create a hidden shadow element
                shadow = currDoc.createElement('div');
                //Moving the element out of the screen doesn't work for IE9 (https://connect.microsoft.com/IE/feedback/details/663981/)
                //shadow.style.overflow = 'hidden';
                //shadow.style.position = 'absolute';
                //shadow.style.top = '-5000px';
                //shadow.style.height = '1px';
                //doing this instead:
                shadow.style.color = window.getComputedStyle ? targetWindow.getComputedStyle(body, null).backgroundColor : '#FFFFFF';
                shadow.style.fontSize = '0px';
                body.appendChild(shadow);
                if (!!window.getSelection) {
                    //FF3, Webkit, IE9
                    e.stopPropagation();
                    selection = targetWindow.getSelection();
                    range = selection.getRangeAt(0);
                    shadow.appendChild(range.cloneContents());
                    removeHyphenationFromElement(shadow);
                    selection.selectAllChildren(shadow);
                    restore = function () {
                        shadow.parentNode.removeChild(shadow);
                        selection.removeAllRanges(); //IE9 needs that
                        selection.addRange(range);
                    };
                } else {
                    // IE<9
                    e.cancelBubble = true;
                    selection = targetWindow.document.selection;
                    range = selection.createRange();
                    shadow.innerHTML = range.htmlText;
                    removeHyphenationFromElement(shadow);
                    rangeShadow = body.createTextRange();
                    rangeShadow.moveToElementText(shadow);
                    rangeShadow.select();
                    restore = function () {
                        shadow.parentNode.removeChild(shadow);
                        if (range.text !== "") {
                            range.select();
                        }
                    };
                }
                window.setTimeout(restore, 0);
            };
            if (!body) {
                return;
            }
            el = el || body;
            if (window.addEventListener) {
                el.addEventListener("copy", oncopyHandler, true);
            } else {
                el.attachEvent("oncopy", oncopyHandler);
            }
        },

        /**
         * @name Hyphenator-checkIfAllDone
         * @description
         * Checks if all Elements are hyphenated, unhides them and fires onHyphenationDone()
         * @private
         */
        checkIfAllDone = function () {
            var allDone = true, i;
            elements.each(function (ellist) {
                var i, l = ellist.length;
                for (i = 0; i < l; i += 1) {
                    allDone = allDone && ellist[i].hyphenated;
                }
            });
            if (allDone) {
                if (intermediateState === 'hidden' && unhide === 'progressive') {
                    elements.each(function (ellist) {
                        var i, l = ellist.length, el;
                        for (i = 0; i < l; i += 1) {
                            el = ellist[i].element;
                            el.className = el.className.replace(unhideClassRegExp, '');
                            if (el.className === '') {
                                el.removeAttribute('class');
                            }
                        }
                    });
                }
                for (i = 0; i < CSSEditors.length; i += 1) {
                    CSSEditors[i].clearChanges();
                }
                state = 3;
                onHyphenationDone();
            }
        },


        /**
         * @name Hyphenator-hyphenateElement
         * @description
         * Takes the content of the given element and - if there's text - replaces the words
         * by hyphenated words. If there's another element, the function is called recursively.
         * When all words are hyphenated, the visibility of the element is set to 'visible'.
         * @param {Object} el The element to hyphenate
         * @private
         */
        hyphenateElement = function (lang, elo) {
            var el = elo.element,
                hyphenate,
                n,
                i,
                r,
                controlOrphans = function (part) {
                    var h, r;
                    switch (hyphen) {
                    case '|':
                        h = '\\|';
                        break;
                    case '+':
                        h = '\\+';
                        break;
                    case '*':
                        h = '\\*';
                        break;
                    default:
                        h = hyphen;
                    }
                    if (orphanControl >= 2) {
                        //remove hyphen points from last word
                        r = part.split(' ');
                        r[1] = r[1].replace(new RegExp(h, 'g'), '');
                        r[1] = r[1].replace(new RegExp(zeroWidthSpace, 'g'), '');
                        r = r.join(' ');
                    }
                    if (orphanControl === 3) {
                        //replace spaces by non breaking spaces
                        r = r.replace(/[ ]+/g, String.fromCharCode(160));
                    }
                    return r;
                };
            if (Hyphenator.languages.hasOwnProperty(lang)) {
                hyphenate = function (word) {
                    if (!Hyphenator.doHyphenation) {
                        r = word;
                    } else if (urlOrMailRE.test(word)) {
                        r = hyphenateURL(word);
                    } else {
                        r = hyphenateWord(lang, word);
                    }
                    return r;
                };
                if (safeCopy && (el.tagName.toLowerCase() !== 'body')) {
                    registerOnCopy(el);
                }
                i = 0;
                n = el.childNodes[i];
                while (!!n) {
                    if (n.nodeType === 3 && n.data.length >= min) { //type 3 = #text -> hyphenate!
                        n.data = n.data.replace(Hyphenator.languages[lang].genRegExp, hyphenate);
                        if (orphanControl !== 1) {
                            n.data = n.data.replace(/[\S]+ [\S]+$/, controlOrphans);
                        }
                    }
                    i += 1;
                    n = el.childNodes[i];
                }
            }
            if (intermediateState === 'hidden' && unhide === 'wait') {
                el.className = el.className.replace(hideClassRegExp, '');
                if (el.className === '') {
                    el.removeAttribute('class');
                }
            }
            if (intermediateState === 'hidden' && unhide === 'progressive') {
                el.className = el.className.replace(hideClassRegExp, ' ' + unhideClass);
            }
            elo.hyphenated = true;
            elements.hyCount += 1;
            if (elements.count <= elements.hyCount) {
                checkIfAllDone();
            }
        },


        /**
         * @name Hyphenator-hyphenateLanguageElements
         * @description
         * Calls hyphenateElement() for all elements of the specified language.
         * If the language is '*' then all elements are hyphenated.
         * This is done with a setTimout
         * to prevent a "long running Script"-alert when hyphenating large pages.
         * Therefore a tricky bind()-function was necessary.
         * @private
         */
        hyphenateLanguageElements = function (lang) {
            function bind(fun, arg1, arg2) {
                return function () {
                    return fun(arg1, arg2);
                };
            }
            var i, l;
            if (lang === '*') {
                elements.each(function (lang, ellist) {
                    var i, l = ellist.length;
                    for (i = 0; i < l; i += 1) {
                        window.setTimeout(bind(hyphenateElement, lang, ellist[i]), 0);
                    }
                });
            } else {
                if (elements.list.hasOwnProperty(lang)) {
                    l = elements.list[lang].length;
                    for (i = 0; i < l; i += 1) {
                        window.setTimeout(bind(hyphenateElement, lang, elements.list[lang][i]), 0);
                    }
                }
            }
        },

        /**
         * @name Hyphenator-removeHyphenationFromDocument
         * @description
         * Does what it says ;-)
         * @private
         */
        removeHyphenationFromDocument = function () {
            elements.each(function (ellist) {
                var i, l = ellist.length;
                for (i = 0; i < l; i += 1) {
                    removeHyphenationFromElement(ellist[i].element);
                    if (safeCopy) {
                        removeOnCopy(ellist[i].element);
                    }
                    ellist[i].hyphenated = false;
                }
            });
            state = 4;
        },

        /**
         * @name Hyphenator-createStorage
         * @description
         * inits the private var storage depending of the setting in storageType
         * and the supported features of the system.
         * @private
         */
        createStorage = function () {
            var s;
            try {
                if (storageType !== 'none' &&
                        window.localStorage !== undefined &&
                        window.sessionStorage !== undefined &&
                        window.JSON.stringify !== undefined &&
                        window.JSON.parse !== undefined) {
                    switch (storageType) {
                    case 'session':
                        s = window.sessionStorage;
                        break;
                    case 'local':
                        s = window.localStorage;
                        break;
                    default:
                        s = undefined;
                        break;
                    }
                }
            } catch (f) {
                //FF throws an error if DOM.storage.enabled is set to false
            }
            if (s) {
                storage = {
                    prefix: 'Hyphenator_' + Hyphenator.version + '_',
                    store: s,
                    test: function (name) {
                        var val = this.store.getItem(this.prefix + name);
                        return (!!val) ? true : false;
                    },
                    getItem: function (name) {
                        return this.store.getItem(this.prefix + name);
                    },
                    setItem: function (name, value) {
                        this.store.setItem(this.prefix + name, value);
                    }
                };
            } else {
                storage = undefined;
            }
        },

        /**
         * @name Hyphenator-storeConfiguration
         * @description
         * Stores the current config-options in DOM-Storage
         * @private
         */
        storeConfiguration = function () {
            if (!storage) {
                return;
            }
            var settings = {
                'STORED': true,
                'classname': hyphenateClass,
                'donthyphenateclassname': dontHyphenateClass,
                'minwordlength': min,
                'hyphenchar': hyphen,
                'urlhyphenchar': urlhyphen,
                'togglebox': toggleBox,
                'displaytogglebox': displayToggleBox,
                'remoteloading': enableRemoteLoading,
                'enablecache': enableCache,
                'onhyphenationdonecallback': onHyphenationDone,
                'onerrorhandler': onError,
                'intermediatestate': intermediateState,
                'selectorfunction': selectorFunction || mySelectorFunction,
                'safecopy': safeCopy,
                'doframes': doFrames,
                'storagetype': storageType,
                'orphancontrol': orphanControl,
                'dohyphenation': Hyphenator.doHyphenation,
                'persistentconfig': persistentConfig,
                'defaultlanguage': defaultLanguage,
                'useCSS3hyphenation': css3,
                'unhide': unhide,
                'onbeforewordhyphenation': onBeforeWordHyphenation,
                'onafterwordhyphenation': onAfterWordHyphenation
            };
            storage.setItem('config', window.JSON.stringify(settings));
        },

        /**
         * @name Hyphenator-restoreConfiguration
         * @description
         * Retrieves config-options from DOM-Storage and does configuration accordingly
         * @private
         */
        restoreConfiguration = function () {
            var settings;
            if (storage.test('config')) {
                settings = window.JSON.parse(storage.getItem('config'));
                Hyphenator.config(settings);
            }
        };

    return {

        /**
         * @name Hyphenator.version
         * @memberOf Hyphenator
         * @description
         * String containing the actual version of Hyphenator.js
         * [major release].[minor releas].[bugfix release]
         * major release: new API, new Features, big changes
         * minor release: new languages, improvements
         * @public
         */
        version: '4.2.0',

        /**
         * @name Hyphenator.doHyphenation
         * @description
         * If doHyphenation is set to false (defaults to true), hyphenateDocument() isn't called.
         * All other actions are performed.
         */
        doHyphenation: true,

        /**
         * @name Hyphenator.languages
         * @memberOf Hyphenator
         * @description
         * Objects that holds key-value pairs, where key is the language and the value is the
         * language-object loaded from (and set by) the pattern file.
         * The language object holds the following members:
         * <table>
         * <tr><th>key</th><th>desc></th></tr>
         * <tr><td>leftmin</td><td>The minimum of chars to remain on the old line</td></tr>
         * <tr><td>rightmin</td><td>The minimum of chars to go on the new line</td></tr>
         * <tr><td>shortestPattern</td><td>The shortes pattern (numbers don't count!)</td></tr>
         * <tr><td>longestPattern</td><td>The longest pattern (numbers don't count!)</td></tr>
         * <tr><td>specialChars</td><td>Non-ASCII chars in the alphabet.</td></tr>
         * <tr><td>patterns</td><td>the patterns</td></tr>
         * </table>
         * And optionally (or after prepareLanguagesObj() has been called):
         * <table>
         * <tr><td>exceptions</td><td>Excpetions for the secified language</td></tr>
         * </table>
         * @public
         */
        languages: {},


        /**
         * @name Hyphenator.config
             * @description
         * Config function that takes an object as an argument. The object contains key-value-pairs
         * containig Hyphenator-settings. This is a shortcut for calling Hyphenator.set...-Methods.
         * @param {Object} obj <table>
         * <tr><th>key</th><th>values</th><th>default</th></tr>
         * <tr><td>classname</td><td>string</td><td>'hyphenate'</td></tr>
         * <tr><td>donthyphenateclassname</td><td>string</td><td>''</td></tr>
         * <tr><td>minwordlength</td><td>integer</td><td>6</td></tr>
         * <tr><td>hyphenchar</td><td>string</td><td>'&amp;shy;'</td></tr>
         * <tr><td>urlhyphenchar</td><td>string</td><td>'zero with space'</td></tr>
         * <tr><td>togglebox</td><td>function</td><td>see code</td></tr>
         * <tr><td>displaytogglebox</td><td>boolean</td><td>false</td></tr>
         * <tr><td>remoteloading</td><td>boolean</td><td>true</td></tr>
         * <tr><td>enablecache</td><td>boolean</td><td>true</td></tr>
         * <tr><td>enablereducedpatternset</td><td>boolean</td><td>false</td></tr>
         * <tr><td>onhyphenationdonecallback</td><td>function</td><td>empty function</td></tr>
         * <tr><td>onerrorhandler</td><td>function</td><td>alert(onError)</td></tr>
         * <tr><td>intermediatestate</td><td>string</td><td>'hidden'</td></tr>
         * <tr><td>selectorfunction</td><td>function</td><td>[…]</td></tr>
         * <tr><td>safecopy</td><td>boolean</td><td>true</td></tr>
         * <tr><td>doframes</td><td>boolean</td><td>false</td></tr>
         * <tr><td>storagetype</td><td>string</td><td>'none'</td></tr>
         * </table>
         * @public
         * @example &lt;script src = "Hyphenator.js" type = "text/javascript"&gt;&lt;/script&gt;
         * &lt;script type = "text/javascript"&gt;
         *     Hyphenator.config({'minwordlength':4,'hyphenchar':'|'});
         *     Hyphenator.run();
         * &lt;/script&gt;
         */
        config: function (obj) {
            var assert = function (name, type) {
                    var r, t;
                    t = typeof obj[name];
                    if (t === type) {
                        r = true;
                    } else {
                        onError(new Error('Config onError: ' + name + ' must be of type ' + type));
                        r = false;
                    }
                    return r;
                },
                key;

            if (obj.hasOwnProperty('storagetype')) {
                if (assert('storagetype', 'string')) {
                    storageType = obj.storagetype;
                }
                if (!storage) {
                    createStorage();
                }
            }
            if (!obj.hasOwnProperty('STORED') && storage && obj.hasOwnProperty('persistentconfig') && obj.persistentconfig === true) {
                restoreConfiguration();
            }

            for (key in obj) {
                if (obj.hasOwnProperty(key)) {
                    switch (key) {
                    case 'STORED':
                        break;
                    case 'classname':
                        if (assert('classname', 'string')) {
                            hyphenateClass = obj[key];
                        }
                        break;
                    case 'donthyphenateclassname':
                        if (assert('donthyphenateclassname', 'string')) {
                            dontHyphenateClass = obj[key];
                        }
                        break;
                    case 'minwordlength':
                        if (assert('minwordlength', 'number')) {
                            min = obj[key];
                        }
                        break;
                    case 'hyphenchar':
                        if (assert('hyphenchar', 'string')) {
                            if (obj.hyphenchar === '&shy;') {
                                obj.hyphenchar = String.fromCharCode(173);
                            }
                            hyphen = obj[key];
                        }
                        break;
                    case 'urlhyphenchar':
                        if (obj.hasOwnProperty('urlhyphenchar')) {
                            if (assert('urlhyphenchar', 'string')) {
                                urlhyphen = obj[key];
                            }
                        }
                        break;
                    case 'togglebox':
                        if (assert('togglebox', 'function')) {
                            toggleBox = obj[key];
                        }
                        break;
                    case 'displaytogglebox':
                        if (assert('displaytogglebox', 'boolean')) {
                            displayToggleBox = obj[key];
                        }
                        break;
                    case 'remoteloading':
                        if (assert('remoteloading', 'boolean')) {
                            enableRemoteLoading = obj[key];
                        }
                        break;
                    case 'enablecache':
                        if (assert('enablecache', 'boolean')) {
                            enableCache = obj[key];
                        }
                        break;
                    case 'enablereducedpatternset':
                        if (assert('enablereducedpatternset', 'boolean')) {
                            enableReducedPatternSet = obj[key];
                        }
                        break;
                    case 'onhyphenationdonecallback':
                        if (assert('onhyphenationdonecallback', 'function')) {
                            onHyphenationDone = obj[key];
                        }
                        break;
                    case 'onerrorhandler':
                        if (assert('onerrorhandler', 'function')) {
                            onError = obj[key];
                        }
                        break;
                    case 'intermediatestate':
                        if (assert('intermediatestate', 'string')) {
                            intermediateState = obj[key];
                        }
                        break;
                    case 'selectorfunction':
                        if (assert('selectorfunction', 'function')) {
                            selectorFunction = obj[key];
                        }
                        break;
                    case 'safecopy':
                        if (assert('safecopy', 'boolean')) {
                            safeCopy = obj[key];
                        }
                        break;
                    case 'doframes':
                        if (assert('doframes', 'boolean')) {
                            doFrames = obj[key];
                        }
                        break;
                    case 'storagetype':
                        if (assert('storagetype', 'string')) {
                            storageType = obj[key];
                        }
                        break;
                    case 'orphancontrol':
                        if (assert('orphancontrol', 'number')) {
                            orphanControl = obj[key];
                        }
                        break;
                    case 'dohyphenation':
                        if (assert('dohyphenation', 'boolean')) {
                            Hyphenator.doHyphenation = obj[key];
                        }
                        break;
                    case 'persistentconfig':
                        if (assert('persistentconfig', 'boolean')) {
                            persistentConfig = obj[key];
                        }
                        break;
                    case 'defaultlanguage':
                        if (assert('defaultlanguage', 'string')) {
                            defaultLanguage = obj[key];
                        }
                        break;
                    case 'useCSS3hyphenation':
                        if (assert('useCSS3hyphenation', 'boolean')) {
                            css3 = obj[key];
                        }
                        break;
                    case 'unhide':
                        if (assert('unhide', 'string')) {
                            unhide = obj[key];
                        }
                        break;
                    case 'onbeforewordhyphenation':
                        if (assert('onbeforewordhyphenation', 'function')) {
                            onBeforeWordHyphenation = obj[key];
                        }
                        break;
                    case 'onafterwordhyphenation':
                        if (assert('onafterwordhyphenation', 'function')) {
                            onAfterWordHyphenation = obj[key];
                        }
                        break;
                    default:
                        onError(new Error('Hyphenator.config: property ' + key + ' not known.'));
                    }
                }
            }
            if (storage && persistentConfig) {
                storeConfiguration();
            }
        },

        /**
         * @name Hyphenator.run
             * @description
         * Bootstrap function that starts all hyphenation processes when called.
         * @public
         * @example &lt;script src = "Hyphenator.js" type = "text/javascript"&gt;&lt;/script&gt;
         * &lt;script type = "text/javascript"&gt;
         *   Hyphenator.run();
         * &lt;/script&gt;
         */
        run: function () {
            var process = function () {
                try {
                    if (contextWindow.document.getElementsByTagName('frameset').length > 0) {
                        return; //we are in a frameset
                    }
                    autoSetMainLanguage(undefined);
                    gatherDocumentInfos();
                    prepare(hyphenateLanguageElements);
                    if (displayToggleBox) {
                        toggleBox();
                    }
                } catch (e) {
                    onError(e);
                }
            }, i, haveAccess, fl = window.frames.length;

            if (!storage) {
                createStorage();
            }
            if (!documentLoaded && !isBookmarklet) {
                runOnContentLoaded(window, process);
            }
            if (isBookmarklet || documentLoaded) {
                if (doFrames && fl > 0) {
                    for (i = 0; i < fl; i += 1) {
                        haveAccess = undefined;
                        //try catch isn't enough for webkit
                        try {
                            //opera throws only on document.toString-access
                            haveAccess = window.frames[i].document.toString();
                        } catch (e) {
                            haveAccess = undefined;
                        }
                        if (!!haveAccess) {
                            contextWindow = window.frames[i];
                            process();
                        }
                    }
                }
                contextWindow = window;
                process();
            }
        },

        /**
         * @name Hyphenator.addExceptions
             * @description
         * Adds the exceptions from the string to the appropriate language in the 
         * {@link Hyphenator-languages}-object
         * @param {string} lang The language
         * @param {string} words A comma separated string of hyphenated words WITH spaces.
         * @public
         * @example &lt;script src = "Hyphenator.js" type = "text/javascript"&gt;&lt;/script&gt;
         * &lt;script type = "text/javascript"&gt;
         *   Hyphenator.addExceptions('de','ziem-lich, Wach-stube');
         *   Hyphenator.run();
         * &lt;/script&gt;
         */
        addExceptions: function (lang, words) {
            if (lang === '') {
                lang = 'global';
            }
            if (exceptions.hasOwnProperty(lang)) {
                exceptions[lang] += ", " + words;
            } else {
                exceptions[lang] = words;
            }
        },

        /**
         * @name Hyphenator.hyphenate
             * @public
         * @description
         * Hyphenates the target. The language patterns must be loaded.
         * If the target is a string, the hyphenated string is returned,
         * if it's an object, the values are hyphenated directly.
         * @param {string|Object} target the target to be hyphenated
         * @param {string} lang the language of the target
         * @returns string
         * @example &lt;script src = "Hyphenator.js" type = "text/javascript"&gt;&lt;/script&gt;
         * &lt;script src = "patterns/en.js" type = "text/javascript"&gt;&lt;/script&gt;
         * &lt;script type = "text/javascript"&gt;
         * var t = Hyphenator.hyphenate('Hyphenation', 'en'); //Hy|phen|ation
         * &lt;/script&gt;
         */
        hyphenate: function (target, lang) {
            var hyphenate, n, i;
            if (Hyphenator.languages.hasOwnProperty(lang)) {
                if (!Hyphenator.languages[lang].prepared) {
                    prepareLanguagesObj(lang);
                }
                hyphenate = function (word) {
                    var r;
                    if (urlOrMailRE.test(word)) {
                        r = hyphenateURL(word);
                    } else {
                        r = hyphenateWord(lang, word);
                    }
                    return r;
                };
                if (typeof target === 'object' && !(typeof target === 'string' || target.constructor === String)) {
                    i = 0;
                    n = target.childNodes[i];
                    while (!!n) {
                        if (n.nodeType === 3 && n.data.length >= min) { //type 3 = #text -> hyphenate!
                            n.data = n.data.replace(Hyphenator.languages[lang].genRegExp, hyphenate);
                        } else if (n.nodeType === 1) {
                            if (n.lang !== '') {
                                Hyphenator.hyphenate(n, n.lang);
                            } else {
                                Hyphenator.hyphenate(n, lang);
                            }
                        }
                        i += 1;
                        n = target.childNodes[i];
                    }
                } else if (typeof target === 'string' || target.constructor === String) {
                    return target.replace(Hyphenator.languages[lang].genRegExp, hyphenate);
                }
            } else {
                onError(new Error('Language "' + lang + '" is not loaded.'));
            }
        },

        /**
         * @name Hyphenator.getRedPatternSet
             * @description
         * Returns {@link Hyphenator-isBookmarklet}.
         * @param {string} lang the language patterns are stored for
         * @returns object {'patk': pat}
         * @public
         */
        getRedPatternSet: function (lang) {
            return Hyphenator.languages[lang].redPatSet;
        },

        /**
         * @name Hyphenator.isBookmarklet
             * @description
         * Returns {@link Hyphenator-isBookmarklet}.
         * @returns boolean
         * @public
         */
        isBookmarklet: function () {
            return isBookmarklet;
        },

        getConfigFromURI: function () {
            /*jslint evil: true*/
            var loc = null, re = {}, jsArray = contextWindow.document.getElementsByTagName('script'), i, j, l, s, gp, option;
            for (i = 0, l = jsArray.length; i < l; i += 1) {
                if (!!jsArray[i].getAttribute('src')) {
                    loc = jsArray[i].getAttribute('src');
                }
                if (loc && (loc.indexOf('Hyphenator.js?') !== -1)) {
                    s = loc.indexOf('Hyphenator.js?');
                    gp = loc.substring(s + 14).split('&');
                    for (j = 0; j < gp.length; j += 1) {
                        option = gp[j].split('=');
                        if (option[0] !== 'bm') {
                            if (option[1] === 'true') {
                                option[1] = true;
                            } else if (option[1] === 'false') {
                                option[1] = false;
                            } else if (isFinite(option[1])) {
                                option[1] = parseInt(option[1], 10);
                            }
                            if (option[0] === 'onhyphenationdonecallback') {
                                option[1] = new Function('', option[1]);
                            }
                            re[option[0]] = option[1];
                        }
                    }
                    break;
                }
            }
            return re;
        },

        /**
         * @name Hyphenator.toggleHyphenation
             * @description
         * Checks the current state of the ToggleBox and removes or does hyphenation.
         * @public
         */
        toggleHyphenation: function () {
            if (Hyphenator.doHyphenation) {
                if (!!css3hyphenateClassHandle) {
                    css3hyphenateClassHandle.setRule('.' + css3hyphenateClass, css3_h9n.property + ': none;');
                }
                removeHyphenationFromDocument();
                Hyphenator.doHyphenation = false;
                storeConfiguration();
                toggleBox();
            } else {
                if (!!css3hyphenateClassHandle) {
                    css3hyphenateClassHandle.setRule('.' + css3hyphenateClass, css3_h9n.property + ': auto;');
                }
                hyphenateLanguageElements('*');
                Hyphenator.doHyphenation = true;
                storeConfiguration();
                toggleBox();
            }
        }
    };
}(window));
//Export properties/methods (for google closure compiler)
/* to be moved to external file
Hyphenator['languages'] = Hyphenator.languages;
Hyphenator['config'] = Hyphenator.config;
Hyphenator['run'] = Hyphenator.run;
Hyphenator['addExceptions'] = Hyphenator.addExceptions;
Hyphenator['hyphenate'] = Hyphenator.hyphenate;
Hyphenator['getRedPatternSet'] = Hyphenator.getRedPatternSet;
Hyphenator['isBookmarklet'] = Hyphenator.isBookmarklet;
Hyphenator['getConfigFromURI'] = Hyphenator.getConfigFromURI;
Hyphenator['toggleHyphenation'] = Hyphenator.toggleHyphenation;
window['Hyphenator'] = Hyphenator;
*/
if (Hyphenator.isBookmarklet()) {
    Hyphenator.config({displaytogglebox: true, intermediatestate: 'visible', doframes: true, useCSS3hyphenation: true});
    Hyphenator.config(Hyphenator.getConfigFromURI());
    Hyphenator.run();
}