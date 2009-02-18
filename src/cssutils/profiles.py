"""CSS profiles. 

css2 is based on cssvalues
    contributed by Kevin D. Smith, thanks!

    "cssvalues" is used as a property validator.
    it is an importable object that contains a dictionary of compiled regular
    expressions.  The keys of this dictionary are all of the valid CSS property
    names.  The values are compiled regular expressions that can be used to
    validate the values for that property. (Actually, the values are references
    to the 'match' method of a compiled regular expression, so that they are
    simply called like functions.)

"""
__all__ = ['profiles']
__docformat__ = 'restructuredtext'
__version__ = '$Id: cssproperties.py 1116 2008-03-05 13:52:23Z cthedot $'

import cssutils
import re

properties = {}
"""
Define some regular expression fragments that will be used as
macros within the CSS property value regular expressions.
"""
css2macros = {
    'border-style': 'none|hidden|dotted|dashed|solid|double|groove|ridge|inset|outset',
    'border-color': '{color}',
    'border-width': '{length}|thin|medium|thick',

    'background-color': r'{color}|transparent|inherit',
    'background-image': r'{uri}|none|inherit',
    'background-position': r'({percentage}|{length})(\s*({percentage}|{length}))?|((top|center|bottom)\s*(left|center|right))|((left|center|right)\s*(top|center|bottom))|inherit',
    'background-repeat': r'repeat|repeat-x|repeat-y|no-repeat|inherit',
    'background-attachment': r'scroll|fixed|inherit',


    'shape': r'rect\(({w}({length}|auto}){w},){3}{w}({length}|auto){w}\)',
    'counter': r'counter\({w}{identifier}{w}(?:,{w}{list-style-type}{w})?\)',
    'identifier': r'{ident}',
    'family-name': r'{string}|{identifier}',
    'generic-family': r'serif|sans-serif|cursive|fantasy|monospace',
    'absolute-size': r'(x?x-)?(small|large)|medium',
    'relative-size': r'smaller|larger',
    'font-family': r'(({family-name}|{generic-family}){w},{w})*({family-name}|{generic-family})|inherit',
    'font-size': r'{absolute-size}|{relative-size}|{length}|{percentage}|inherit',
    'font-style': r'normal|italic|oblique|inherit',
    'font-variant': r'normal|small-caps|inherit',
    'font-weight': r'normal|bold|bolder|lighter|[1-9]00|inherit',
    'line-height': r'normal|{number}|{length}|{percentage}|inherit',
    'list-style-image': r'{uri}|none|inherit',
    'list-style-position': r'inside|outside|inherit',
    'list-style-type': r'disc|circle|square|decimal|decimal-leading-zero|lower-roman|upper-roman|lower-greek|lower-(latin|alpha)|upper-(latin|alpha)|armenian|georgian|none|inherit',
    'margin-width': r'{length}|{percentage}|auto',
    'outline-color': r'{color}|invert|inherit',
    'outline-style': r'{border-style}|inherit',
    'outline-width': r'{border-width}|inherit',
    'padding-width': r'{length}|{percentage}',
    'specific-voice': r'{identifier}',
    'generic-voice': r'male|female|child',
    'content': r'{string}|{uri}|{counter}|attr\({w}{identifier}{w}\)|open-quote|close-quote|no-open-quote|no-close-quote',
    'border-attrs': r'{border-width}|{border-style}|{border-color}',
    'background-attrs': r'{background-color}|{background-image}|{background-repeat}|{background-attachment}|{background-position}',
    'list-attrs': r'{list-style-type}|{list-style-position}|{list-style-image}',
    'font-attrs': r'{font-style}|{font-variant}|{font-weight}',
    'outline-attrs': r'{outline-color}|{outline-style}|{outline-width}',
    'text-attrs': r'underline|overline|line-through|blink',
    'overflow': r'visible|hidden|scroll|auto|inherit',
}

"""
Define the regular expressions for validation all CSS values
"""
properties['css2'] = {
    'azimuth': r'{angle}|(behind\s+)?(left-side|far-left|left|center-left|center|center-right|right|far-right|right-side)(\s+behind)?|behind|leftwards|rightwards|inherit',
    'background-attachment': r'{background-attachment}',
    'background-color': r'{background-color}',
    'background-image': r'{background-image}',
    'background-position': r'{background-position}',
    'background-repeat': r'{background-repeat}',
    # Each piece should only be allowed one time
    'background': r'{background-attrs}(\s+{background-attrs})*|inherit',
    'border-collapse': r'collapse|separate|inherit',
    'border-color': r'({border-color}|transparent)(\s+({border-color}|transparent)){0,3}|inherit',
    'border-spacing': r'{length}(\s+{length})?|inherit',
    'border-style': r'{border-style}(\s+{border-style}){0,3}|inherit',
    'border-top': r'{border-attrs}(\s+{border-attrs})*|inherit',
    'border-right': r'{border-attrs}(\s+{border-attrs})*|inherit',
    'border-bottom': r'{border-attrs}(\s+{border-attrs})*|inherit',
    'border-left': r'{border-attrs}(\s+{border-attrs})*|inherit',
    'border-top-color': r'{border-color}|transparent|inherit',
    'border-right-color': r'{border-color}|transparent|inherit',
    'border-bottom-color': r'{border-color}|transparent|inherit',
    'border-left-color': r'{border-color}|transparent|inherit',
    'border-top-style': r'{border-style}|inherit',
    'border-right-style': r'{border-style}|inherit',
    'border-bottom-style': r'{border-style}|inherit',
    'border-left-style': r'{border-style}|inherit',
    'border-top-width': r'{border-width}|inherit',
    'border-right-width': r'{border-width}|inherit',
    'border-bottom-width': r'{border-width}|inherit',
    'border-left-width': r'{border-width}|inherit',
    'border-width': r'{border-width}(\s+{border-width}){0,3}|inherit',
    'border': r'{border-attrs}(\s+{border-attrs})*|inherit',
    'bottom': r'{length}|{percentage}|auto|inherit',
    'caption-side': r'top|bottom|inherit',
    'clear': r'none|left|right|both|inherit',
    'clip': r'{shape}|auto|inherit',
    'color': r'{color}|inherit',
    'content': r'normal|{content}(\s+{content})*|inherit',
    'counter-increment': r'({identifier}(\s+{integer})?)(\s+({identifier}(\s+{integer})))*|none|inherit',
    'counter-reset': r'({identifier}(\s+{integer})?)(\s+({identifier}(\s+{integer})))*|none|inherit',
    'cue-after': r'{uri}|none|inherit',
    'cue-before': r'{uri}|none|inherit',
    'cue': r'({uri}|none|inherit){1,2}|inherit',
    'cursor': r'((({uri}{w},{w})*)?(auto|crosshair|default|pointer|move|(e|ne|nw|n|se|sw|s|w)-resize|text|wait|help|progress))|inherit',
    'direction': r'ltr|rtl|inherit',
    'display': r'inline|block|list-item|run-in|inline-block|table|inline-table|table-row-group|table-header-group|table-footer-group|table-row|table-column-group|table-column|table-cell|table-caption|none|inherit',
    'elevation': r'{angle}|below|level|above|higher|lower|inherit',
    'empty-cells': r'show|hide|inherit',
    'float': r'left|right|none|inherit',
    'font-family': r'{font-family}',
    'font-size': r'{font-size}',
    'font-style': r'{font-style}',
    'font-variant': r'{font-variant}',
    'font-weight': r'{font-weight}',
    'font': r'({font-attrs}\s+)*{font-size}({w}/{w}{line-height})?\s+{font-family}|caption|icon|menu|message-box|small-caption|status-bar|inherit',
    'height': r'{length}|{percentage}|auto|inherit',
    'left': r'{length}|{percentage}|auto|inherit',
    'letter-spacing': r'normal|{length}|inherit',
    'line-height': r'{line-height}',
    'list-style-image': r'{list-style-image}',
    'list-style-position': r'{list-style-position}',
    'list-style-type': r'{list-style-type}',
    'list-style': r'{list-attrs}(\s+{list-attrs})*|inherit',
    'margin-right': r'{margin-width}|inherit',
    'margin-left': r'{margin-width}|inherit',
    'margin-top': r'{margin-width}|inherit',
    'margin-bottom': r'{margin-width}|inherit',
    'margin': r'{margin-width}(\s+{margin-width}){0,3}|inherit',
    'max-height': r'{length}|{percentage}|none|inherit',
    'max-width': r'{length}|{percentage}|none|inherit',
    'min-height': r'{length}|{percentage}|none|inherit',
    'min-width': r'{length}|{percentage}|none|inherit',
    'orphans': r'{integer}|inherit',
    'outline-color': r'{outline-color}',
    'outline-style': r'{outline-style}',
    'outline-width': r'{outline-width}',
    'outline': r'{outline-attrs}(\s+{outline-attrs})*|inherit',
    'overflow': r'{overflow}',
    'padding-top': r'{padding-width}|inherit',
    'padding-right': r'{padding-width}|inherit',
    'padding-bottom': r'{padding-width}|inherit',
    'padding-left': r'{padding-width}|inherit',
    'padding': r'{padding-width}(\s+{padding-width}){0,3}|inherit',
    'page-break-after': r'auto|always|avoid|left|right|inherit',
    'page-break-before': r'auto|always|avoid|left|right|inherit',
    'page-break-inside': r'avoid|auto|inherit',
    'pause-after': r'{time}|{percentage}|inherit',
    'pause-before': r'{time}|{percentage}|inherit',
    'pause': r'({time}|{percentage}){1,2}|inherit',
    'pitch-range': r'{number}|inherit',
    'pitch': r'{frequency}|x-low|low|medium|high|x-high|inherit',
    'play-during': r'{uri}(\s+(mix|repeat))*|auto|none|inherit',
    'position': r'static|relative|absolute|fixed|inherit',
    'quotes': r'({string}\s+{string})(\s+{string}\s+{string})*|none|inherit',
    'richness': r'{number}|inherit',
    'right': r'{length}|{percentage}|auto|inherit',
    'speak-header': r'once|always|inherit',
    'speak-numeral': r'digits|continuous|inherit',
    'speak-punctuation': r'code|none|inherit',
    'speak': r'normal|none|spell-out|inherit',
    'speech-rate': r'{number}|x-slow|slow|medium|fast|x-fast|faster|slower|inherit',
    'stress': r'{number}|inherit',
    'table-layout': r'auto|fixed|inherit',
    'text-align': r'left|right|center|justify|inherit',
    'text-decoration': r'none|{text-attrs}(\s+{text-attrs})*|inherit',
    'text-indent': r'{length}|{percentage}|inherit',
    'text-transform': r'capitalize|uppercase|lowercase|none|inherit',
    'top': r'{length}|{percentage}|auto|inherit',
    'unicode-bidi': r'normal|embed|bidi-override|inherit',
    'vertical-align': r'baseline|sub|super|top|text-top|middle|bottom|text-bottom|{percentage}|{length}|inherit',
    'visibility': r'visible|hidden|collapse|inherit',
    'voice-family': r'({specific-voice}|{generic-voice}{w},{w})*({specific-voice}|{generic-voice})|inherit',
    'volume': r'{number}|{percentage}|silent|x-soft|soft|medium|loud|x-loud|inherit',
    'white-space': r'normal|pre|nowrap|pre-wrap|pre-line|inherit',
    'widows': r'{integer}|inherit',
    'width': r'{length}|{percentage}|auto|inherit',
    'word-spacing': r'normal|{length}|inherit',
    'z-index': r'auto|{integer}|inherit',
}

# CSS Color Module Level 3
css3colormacros = {
    # orange and transparent in CSS 2.1
    'namedcolor': r'(currentcolor|transparent|orange|black|green|silver|lime|gray|olive|white|yellow|maroon|navy|red|blue|purple|teal|fuchsia|aqua)',
                    # orange?
    'rgbacolor': r'rgba\({w}{int}{w},{w}{int}{w},{w}{int}{w},{w}{int}{w}\)|rgba\({w}{num}%{w},{w}{num}%{w},{w}{num}%{w},{w}{num}{w}\)',
    'hslcolor': r'hsl\({w}{int}{w},{w}{num}%{w},{w}{num}%{w}\)|hsla\({w}{int}{w},{w}{num}%{w},{w}{num}%{w},{w}{num}{w}\)',
    'x11color': r'aliceblue|antiquewhite|aqua|aquamarine|azure|beige|bisque|black|blanchedalmond|blue|blueviolet|brown|burlywood|cadetblue|chartreuse|chocolate|coral|cornflowerblue|cornsilk|crimson|cyan|darkblue|darkcyan|darkgoldenrod|darkgray|darkgreen|darkgrey|darkkhaki|darkmagenta|darkolivegreen|darkorange|darkorchid|darkred|darksalmon|darkseagreen|darkslateblue|darkslategray|darkslategrey|darkturquoise|darkviolet|deeppink|deepskyblue|dimgray|dimgrey|dodgerblue|firebrick|floralwhite|forestgreen|fuchsia|gainsboro|ghostwhite|gold|goldenrod|gray|green|greenyellow|grey|honeydew|hotpink|indianred|indigo|ivory|khaki|lavender|lavenderblush|lawngreen|lemonchiffon|lightblue|lightcoral|lightcyan|lightgoldenrodyellow|lightgray|lightgreen|lightgrey|lightpink|lightsalmon|lightseagreen|lightskyblue|lightslategray|lightslategrey|lightsteelblue|lightyellow|lime|limegreen|linen|magenta|maroon|mediumaquamarine|mediumblue|mediumorchid|mediumpurple|mediumseagreen|mediumslateblue|mediumspringgreen|mediumturquoise|mediumvioletred|midnightblue|mintcream|mistyrose|moccasin|navajowhite|navy|oldlace|olive|olivedrab|orange|orangered|orchid|palegoldenrod|palegreen|paleturquoise|palevioletred|papayawhip|peachpuff|peru|pink|plum|powderblue|purple|red|rosybrown|royalblue|saddlebrown|salmon|sandybrown|seagreen|seashell|sienna|silver|skyblue|slateblue|slategray|slategrey|snow|springgreen|steelblue|tan|teal|thistle|tomato|turquoise|violet|wheat|white|whitesmoke|yellow|yellowgreen',
    'uicolor': r'(ActiveBorder|ActiveCaption|AppWorkspace|Background|ButtonFace|ButtonHighlight|ButtonShadow|ButtonText|CaptionText|GrayText|Highlight|HighlightText|InactiveBorder|InactiveCaption|InactiveCaptionText|InfoBackground|InfoText|Menu|MenuText|Scrollbar|ThreeDDarkShadow|ThreeDFace|ThreeDHighlight|ThreeDLightShadow|ThreeDShadow|Window|WindowFrame|WindowText)',

    }
properties['css3color'] = {
    'color': r'{namedcolor}|{hexcolor}|{rgbcolor}|{rgbacolor}|{hslcolor}|inherit',
    'opacity': r'{num}|inherit'
    }

# CSS Box Module Level 3
properties['css3box'] = {
    'overflow': '{overflow}\s?{overflow}?',
    'overflow-x': '{overflow}',
    'overflow-y': '{overflow}'
    }

class NoSuchProfileException(Exception):
    """Raised if no profile with given name is found"""
    pass


class Profiles(object):
    """
    All profiles used for validation. ``cssutils.profiles.profiles`` is a
    preset object of this class and used by all properties for validation.

    Predefined profiles are (use 
    :meth:`~cssutils.profiles.Profiles.propertiesByProfile` to
    get a list of defined properties):

    :attr:`~cssutils.profiles.Profiles.Profiles.CSS_LEVEL_2`
        Properties defined by CSS2.1
    :attr:`~cssutils.profiles.Profiles.Profiles.CSS_COLOR_LEVEL_3`
        CSS 3 color properties
    :attr:`~cssutils.profiles.Profiles.Profiles.CSS_BOX_LEVEL_3`
        Currently overflow related properties only

    """
    CSS_LEVEL_2 = 'CSS Level 2.1'
    CSS_COLOR_LEVEL_3 = 'CSS Color Module Level 3'
    CSS_BOX_LEVEL_3 = 'CSS Box Module Level 3'
    
    basicmacros = {
        'ident': r'[-]?{nmstart}{nmchar}*',
        'name': r'{nmchar}+',
        'nmstart': r'[_a-z]|{nonascii}|{escape}',
        'nonascii': r'[^\0-\177]',
        'unicode': r'\\[0-9a-f]{1,6}(\r\n|[ \n\r\t\f])?',
        'escape': r'{unicode}|\\[ -~\200-\777]',
    #   'escape': r'{unicode}|\\[ -~\200-\4177777]',
        'int': r'[-]?\d+',
        'nmchar': r'[\w-]|{nonascii}|{escape}',
        'num': r'[-]?\d+|[-]?\d*\.\d+',
        'number': r'{num}',
        'string': r'{string1}|{string2}',
        'string1': r'"(\\\"|[^\"])*"',
        'uri': r'url\({w}({string}|(\\\)|[^\)])+){w}\)',
        'string2': r"'(\\\'|[^\'])*'",
        'nl': r'\n|\r\n|\r|\f',
        'w': r'\s*',
        }
    generalmacros = {
        'hexcolor': r'#[0-9a-f]{3}|#[0-9a-f]{6}',
        'rgbcolor': r'rgb\({w}{int}{w},{w}{int}{w},{w}{int}{w}\)|rgb\({w}{num}%{w},{w}{num}%{w},{w}{num}%{w}\)',
        'namedcolor': r'(transparent|orange|maroon|red|orange|yellow|olive|purple|fuchsia|white|lime|green|navy|blue|aqua|teal|black|silver|gray)',
        'uicolor': r'(ActiveBorder|ActiveCaption|AppWorkspace|Background|ButtonFace|ButtonHighlight|ButtonShadow|ButtonText|CaptionText|GrayText|Highlight|HighlightText|InactiveBorder|InactiveCaption|InactiveCaptionText|InfoBackground|InfoText|Menu|MenuText|Scrollbar|ThreeDDarkShadow|ThreeDFace|ThreeDHighlight|ThreeDLightShadow|ThreeDShadow|Window|WindowFrame|WindowText)',
        'color': r'{namedcolor}|{hexcolor}|{rgbcolor}|{uicolor}',
        #'color': r'(maroon|red|orange|yellow|olive|purple|fuchsia|white|lime|green|navy|blue|aqua|teal|black|silver|gray|ActiveBorder|ActiveCaption|AppWorkspace|Background|ButtonFace|ButtonHighlight|ButtonShadow|ButtonText|CaptionText|GrayText|Highlight|HighlightText|InactiveBorder|InactiveCaption|InactiveCaptionText|InfoBackground|InfoText|Menu|MenuText|Scrollbar|ThreeDDarkShadow|ThreeDFace|ThreeDHighlight|ThreeDLightShadow|ThreeDShadow|Window|WindowFrame|WindowText)|#[0-9a-f]{3}|#[0-9a-f]{6}|rgb\({w}{int}{w},{w}{int}{w},{w}{int}{w}\)|rgb\({w}{num}%{w},{w}{num}%{w},{w}{num}%{w}\)',
        'integer': r'{int}',
        'length': r'0|{num}(em|ex|px|in|cm|mm|pt|pc)',
        'angle': r'0|{num}(deg|grad|rad)',
        'time': r'0|{num}m?s',
        'frequency': r'0|{num}k?Hz',
        'percentage': r'{num}%',
        }

    def __init__(self):
        """A few known profiles are predefined."""
        self._log = cssutils.log
        self._profilenames = [] # to keep order, REFACTOR!
        self._profiles = {}
        
        self.addProfile(self.CSS_LEVEL_2, properties['css2'], css2macros)
        self.addProfile(self.CSS_COLOR_LEVEL_3, properties['css3color'], css3colormacros)
        self.addProfile(self.CSS_BOX_LEVEL_3, properties['css3box'])
        
        self.__update_knownnames()

    def _expand_macros(self, dictionary, macros):
        """Expand macros in token dictionary"""
        def macro_value(m):
            return '(?:%s)' % macros[m.groupdict()['macro']]
        for key, value in dictionary.items():
            if not hasattr(value, '__call__'):
                while re.search(r'{[a-z][a-z0-9-]*}', value):
                    value = re.sub(r'{(?P<macro>[a-z][a-z0-9-]*)}',
                                   macro_value, value)
            dictionary[key] = value
        return dictionary

    def _compile_regexes(self, dictionary):
        """Compile all regular expressions into callable objects"""
        for key, value in dictionary.items():
            if not hasattr(value, '__call__'):
                value = re.compile('^(?:%s)$' % value, re.I).match
            dictionary[key] = value

        return dictionary

    def __update_knownnames(self):
        self._knownnames = []
        for properties in self._profiles.values():
            self._knownnames.extend(properties.keys())
        
    profiles = property(lambda self: sorted(self._profiles.keys()),
                                            doc=u'Names of all profiles.')

    knownnames = property(lambda self: self._knownnames,
                               doc="All known property names of all profiles.")

    def addProfile(self, profile, properties, macros=None):
        """Add a new profile with name `profile` (e.g. 'CSS level 2')
        and the given `properties`.

        :param profile:
            the new `profile`'s name
        :param properties:
            a dictionary of ``{ property-name: propery-value }`` items where
            property-value is a regex which may use macros defined in given
            ``macros`` or the standard macros Profiles.tokens and
            Profiles.generalvalues.

            ``propery-value`` may also be a function which takes a single
            argument which is the value to validate and which should return
            True or False.
            Any exceptions which may be raised during this custom validation
            are reported or raised as all other cssutils exceptions depending
            on cssutils.log.raiseExceptions which e.g during parsing normally
            is False so the exceptions would be logged only.
        :param macros:
            may be used in the given properties definitions. There are some
            predefined basic macros which may always be used in 
            :attr:`Profiles.basicmacros` and :attr:`Profiles.generalmacros`.
        """
        if not macros:
            macros = {}
        m = self.basicmacros
        m.update(self.generalmacros)
        m.update(macros)
        properties = self._expand_macros(properties, m)
        self._profilenames.append(profile)
        self._profiles[profile] = self._compile_regexes(properties)
        
        self.__update_knownnames()

    def removeProfile(self, profile=None, all=False):
        """Remove `profile` or remove `all` profiles.
        
        :param profile:
            profile name to remove
        :param all:
            if ``True`` removes all profiles to start with a clean state
        :exceptions:
            - :exc:`cssutils.profiles.NoSuchProfileException`:
              If given `profile` cannot be found.
        """
        if all:
            self._profiles.clear()
        else:
            try:
                del self._profiles[profile]
            except KeyError:
                raise NoSuchProfileException(u'No profile %r.' % profile)

        self.__update_knownnames()

    def propertiesByProfile(self, profiles=None):
        """Generator: Yield property names, if no `profiles` is given all
        profile's properties are used.
        
        :param profiles:
            a single profile name or a list of names.
        """
        if not profiles:
            profiles = self.profiles
        elif isinstance(profiles, basestring):
            profiles = (profiles, )
        try:
            for profile in sorted(profiles):
                for name in sorted(self._profiles[profile].keys()):
                    yield name
        except KeyError, e:
            raise NoSuchProfileException(e)

    def validate(self, name, value):
        """Check if `value` is valid for given property `name` using **any** 
        profile.
        
        :param name:
            a property name
        :param value:
            a CSS value (string)
        :returns: 
            if the `value` is valid for the given property `name` in any
            profile
        """
        for profile in self.profiles:
            if name in self._profiles[profile]:
                try:
                    # custom validation errors are caught
                    r = bool(self._profiles[profile][name](value))
                except Exception, e:
                    self._log.error(e, error=Exception)
                    return False
                if r:
                    return r
        return False

    def validateWithProfile(self, name, value, profiles=None):
        """Check if `value` is valid for given property `name` returning
        ``(valid, profile)``.

        :param name:
            a property name
        :param value:
            a CSS value (string)
        :returns: 
            ``valid, profiles`` where ``valid`` is if the `value` is valid for
            the given property `name` in any profile of given `profiles` 
            and ``profiles`` the profile names for which the value is valid
            (or ``[]`` if not valid at all)

        Example: You might expect a valid Profiles.CSS_LEVEL_2 value but
        e.g. ``validateWithProfile('color', 'rgba(1,1,1,1)')`` returns
        (True, Profiles.CSS_COLOR_LEVEL_3)
        """
        if name not in self.knownnames:
            return False, []
        else:
            if not profiles:
                profiles = self._profilenames
            elif isinstance(profiles, basestring):
                profiles = (profiles, )  
    
            for profilename in profiles:
                # check given profiles
                if name in self._profiles[profilename]:
                    validate = self._profiles[profilename][name]
                    try:
                        if validate(value):
                            return True, [profilename]
                    except Exception, e:
                        self._log.error(e, error=Exception)
    
            for profilename in (p for p in self._profilenames if p not in profiles):
                # check remaining profiles as well
                if name in self._profiles[profilename]:
                    validate = self._profiles[profilename][name]
                    try:
                        if validate(value):
                            return True, [profilename]
                    except Exception, e:
                        self._log.error(e, error=Exception)
            
            names = []
            for profilename, properties in self._profiles.items():
                # return profile to which name belongs
                if name in properties.keys():
                    names.append(profilename)
            names.sort()
            return False, names
                    
# used by 
profiles = Profiles()

# set for validation to e.g.``Profiles.CSS_LEVEL_2``
defaultprofile = None

