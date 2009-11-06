"""CSS profiles.

Profiles is based on code by Kevin D. Smith, orginally used as cssvalues,
thanks!
"""
__all__ = ['Profiles']
__docformat__ = 'restructuredtext'
__version__ = '$Id: cssproperties.py 1116 2008-03-05 13:52:23Z cthedot $'

import re

class NoSuchProfileException(Exception):
    """Raised if no profile with given name is found"""
    pass


class Profiles(object):
    """
    All profiles used for validation. ``cssutils.profile`` is a
    preset object of this class and used by all properties for validation.

    Predefined profiles are (use
    :meth:`~cssutils.profiles.Profiles.propertiesByProfile` to
    get a list of defined properties):

    :attr:`~cssutils.profiles.Profiles.CSS_LEVEL_2`
        Properties defined by CSS2.1
    :attr:`~cssutils.profiles.Profiles.CSS3_COLOR`
        CSS 3 color properties
    :attr:`~cssutils.profiles.Profiles.CSS3_BOX`
        Currently overflow related properties only
    :attr:`~cssutils.profiles.Profiles.CSS3_PAGED_MEDIA`
        As defined at http://www.w3.org/TR/css3-page/ (at 090307)

    Predefined macros are:

    :attr:`~cssutils.profiles.Profiles._TOKEN_MACROS`
        Macros containing the token values as defined to CSS2
    :attr:`~cssutils.profiles.Profiles._MACROS`
        Additional general macros.

    If you want to redefine any of these macros do this in your custom
    macros.
    """
    CSS_LEVEL_2 = 'CSS Level 2.1'
    CSS3_BOX = CSS_BOX_LEVEL_3 = 'CSS Box Module Level 3'
    CSS3_COLOR = CSS_COLOR_LEVEL_3 = 'CSS Color Module Level 3'
    CSS3_FONTS = 'CSS Fonts Module Level 3'
    CSS3_FONT_FACE = 'CSS Fonts Module Level 3 @font-face properties'
    CSS3_PAGED_MEDIA = 'CSS3 Paged Media Module'

    _TOKEN_MACROS = {
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
        'positivenum': r'\d+|\d*\.\d+',
        'number': r'{num}',
        'string': r'{string1}|{string2}',
        'string1': r'"(\\\"|[^\"])*"',
        'uri': r'url\({w}({string}|(\\\)|[^\)])+){w}\)',
        'string2': r"'(\\\'|[^\'])*'",
        'nl': r'\n|\r\n|\r|\f',
        'w': r'\s*',
        }
    _MACROS = {
        'hexcolor': r'#[0-9a-f]{3}|#[0-9a-f]{6}',
        'rgbcolor': r'rgb\({w}{int}{w},{w}{int}{w},{w}{int}{w}\)|rgb\({w}{num}%{w},{w}{num}%{w},{w}{num}%{w}\)',
        'namedcolor': r'(transparent|orange|maroon|red|orange|yellow|olive|purple|fuchsia|white|lime|green|navy|blue|aqua|teal|black|silver|gray)',
        'uicolor': r'(ActiveBorder|ActiveCaption|AppWorkspace|Background|ButtonFace|ButtonHighlight|ButtonShadow|ButtonText|CaptionText|GrayText|Highlight|HighlightText|InactiveBorder|InactiveCaption|InactiveCaptionText|InfoBackground|InfoText|Menu|MenuText|Scrollbar|ThreeDDarkShadow|ThreeDFace|ThreeDHighlight|ThreeDLightShadow|ThreeDShadow|Window|WindowFrame|WindowText)',
        'color': r'{namedcolor}|{hexcolor}|{rgbcolor}|{uicolor}',
        #'color': r'(maroon|red|orange|yellow|olive|purple|fuchsia|white|lime|green|navy|blue|aqua|teal|black|silver|gray|ActiveBorder|ActiveCaption|AppWorkspace|Background|ButtonFace|ButtonHighlight|ButtonShadow|ButtonText|CaptionText|GrayText|Highlight|HighlightText|InactiveBorder|InactiveCaption|InactiveCaptionText|InfoBackground|InfoText|Menu|MenuText|Scrollbar|ThreeDDarkShadow|ThreeDFace|ThreeDHighlight|ThreeDLightShadow|ThreeDShadow|Window|WindowFrame|WindowText)|#[0-9a-f]{3}|#[0-9a-f]{6}|rgb\({w}{int}{w},{w}{int}{w},{w}{int}{w}\)|rgb\({w}{num}%{w},{w}{num}%{w},{w}{num}%{w}\)',
        'integer': r'{int}',
        'length': r'0|{num}(em|ex|px|in|cm|mm|pt|pc)',
        'positivelength': r'0|{positivenum}(em|ex|px|in|cm|mm|pt|pc)',
        'angle': r'0|{num}(deg|grad|rad)',
        'time': r'0|{num}m?s',
        'frequency': r'0|{num}k?Hz',
        'percentage': r'{num}%',
        }

    def __init__(self, log=None):
        """A few known profiles are predefined."""
        self._log = log
        self._profileNames = [] # to keep order, REFACTOR!
        self._profiles = {}
        self._defaultProfiles = None

        self.addProfile(self.CSS_LEVEL_2,
                        properties[self.CSS_LEVEL_2],
                        macros[self.CSS_LEVEL_2])
        self.addProfile(self.CSS3_BOX,
                        properties[self.CSS3_BOX],
                        macros[self.CSS3_BOX])
        self.addProfile(self.CSS3_COLOR,
                        properties[self.CSS3_COLOR],
                        macros[self.CSS3_COLOR])
        
        self.addProfile(self.CSS3_FONTS,
                        properties[self.CSS3_FONTS],
                        macros[self.CSS3_FONTS])
        
        # new object for font-face only?
        self.addProfile(self.CSS3_FONT_FACE,
                        properties[self.CSS3_FONT_FACE],
                        macros[self.CSS3_FONTS]) # same
        
        self.addProfile(self.CSS3_PAGED_MEDIA,
                        properties[self.CSS3_PAGED_MEDIA],
                        macros[self.CSS3_PAGED_MEDIA])

        self.__update_knownNames()

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

    def __update_knownNames(self):
        self._knownNames = []
        for properties in self._profiles.values():
            self._knownNames.extend(properties.keys())

    def _getDefaultProfiles(self):
        "If not explicitly set same as Profiles.profiles but in reverse order."
        if not self._defaultProfiles:
            return self.profiles
        else:
            return self._defaultProfiles

    def _setDefaultProfiles(self, profiles):
        "profiles may be a single or a list of profile names"
        if isinstance(profiles, basestring):
            self._defaultProfiles = (profiles,)
        else:
            self._defaultProfiles = profiles

    defaultProfiles = property(_getDefaultProfiles,
                               _setDefaultProfiles,
                               doc=u"Names of profiles to use for validation."
                                   u"To use e.g. the CSS2 profile set "
                                   u"``cssutils.profile.defaultProfiles = "
                                   u"cssutils.profile.CSS_LEVEL_2``")

    profiles = property(lambda self: self._profileNames,
                        doc=u'Names of all profiles in order as defined.')

    knownNames = property(lambda self: self._knownNames,
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
            :attr:`Profiles._TOKEN_MACROS` and :attr:`Profiles._MACROS`.
        """
        if not macros:
            macros = {}
        m = Profiles._TOKEN_MACROS.copy()
        m.update(Profiles._MACROS)
        m.update(macros)
        properties = self._expand_macros(properties, m)
        self._profileNames.append(profile)
        self._profiles[profile] = self._compile_regexes(properties)

        self.__update_knownNames()

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
            del self._profileNames[:]
        else:
            try:
                del self._profiles[profile]
                del self._profileNames[self._profileNames.index(profile)]
            except KeyError:
                raise NoSuchProfileException(u'No profile %r.' % profile)

        self.__update_knownNames()

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
        :param profiles:
            internal parameter used by Property.validate only
        :returns:
            ``valid, matching, profiles`` where ``valid`` is if the `value`
            is valid for the given property `name` in any profile,
            ``matching==True`` if it is valid in the given `profiles`
            and ``profiles`` the profile names for which the value is valid
            (or ``[]`` if not valid at all)

        Example::

            >>> cssutils.profile.defaultProfiles = cssutils.profile.CSS_LEVEL_2
            >>> print cssutils.profile.validateWithProfile('color', 'rgba(1,1,1,1)')
            (True, False, Profiles.CSS3_COLOR)
        """
        if name not in self.knownNames:
            return False, False, []
        else:
            if not profiles:
                profiles = self.defaultProfiles
            elif isinstance(profiles, basestring):
                profiles = (profiles, )

            for profilename in profiles:
                # check given profiles
                if name in self._profiles[profilename]:
                    validate = self._profiles[profilename][name]
                    try:
                        if validate(value):
                            return True, True, [profilename]
                    except Exception, e:
                        self._log.error(e, error=Exception)

            for profilename in (p for p in self._profileNames
                                if p not in profiles):
                # check remaining profiles as well
                if name in self._profiles[profilename]:
                    validate = self._profiles[profilename][name]
                    try:
                        if validate(value):
                            return True, False, [profilename]
                    except Exception, e:
                        self._log.error(e, error=Exception)

            names = []
            for profilename, properties in self._profiles.items():
                # return profile to which name belongs
                if name in properties.keys():
                    names.append(profilename)
            names.sort()
            return False, False, names


properties = {}
macros = {}
"""
Define some regular expression fragments that will be used as
macros within the CSS property value regular expressions.
"""
macros[Profiles.CSS_LEVEL_2] = {
    'border-style': 'none|hidden|dotted|dashed|solid|double|groove|ridge|inset|outset',
    'border-color': '{color}',
    'border-width': '{length}|thin|medium|thick',

    'background-color': r'{color}|transparent|inherit',
    'background-image': r'{uri}|none|inherit',
    #'background-position': r'({percentage}|{length})(\s*({percentage}|{length}))?|((top|center|bottom)\s*(left|center|right)?)|((left|center|right)\s*(top|center|bottom)?)|inherit',
    'background-position': r'({percentage}|{length}|left|center|right)(\s*({percentage}|{length}|top|center|bottom))?|((top|center|bottom)\s*(left|center|right)?)|((left|center|right)\s*(top|center|bottom)?)|inherit',
    'background-repeat': r'repeat|repeat-x|repeat-y|no-repeat|inherit',
    'background-attachment': r'scroll|fixed|inherit',

    'shape': r'rect\(({w}({length}|auto}){w},){3}{w}({length}|auto){w}\)',
    'counter': r'counter\({w}{identifier}{w}(?:,{w}{list-style-type}{w})?\)',
    'identifier': r'{ident}',
    'family-name': r'{string}|{identifier}({w}{identifier})*',
    'generic-family': r'serif|sans-serif|cursive|fantasy|monospace',
    'absolute-size': r'(x?x-)?(small|large)|medium',
    'relative-size': r'smaller|larger',
    'font-family': r'(({family-name}|{generic-family}){w},{w})*({family-name}|{generic-family})|inherit',
    'font-size': r'{absolute-size}|{relative-size}|{positivelength}|{percentage}|inherit',
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
properties[Profiles.CSS_LEVEL_2] = {
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
    'content': r'none|normal|{content}(\s+{content})*|inherit',
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

# CSS Box Module Level 3
macros[Profiles.CSS3_BOX] = {
    'overflow': macros[Profiles.CSS_LEVEL_2]['overflow']
    }
properties[Profiles.CSS3_BOX] = {
    'overflow': '{overflow}{w}{overflow}?|inherit',
    'overflow-x': '{overflow}|inherit',
    'overflow-y': '{overflow}|inherit'
    }

# CSS Color Module Level 3
macros[Profiles.CSS3_COLOR] = {
    # orange and transparent in CSS 2.1
    'namedcolor': r'(currentcolor|transparent|aqua|black|blue|fuchsia|gray|green|lime|maroon|navy|olive|orange|purple|red|silver|teal|white|yellow)',
                    # orange?
    'rgbacolor': r'rgba\({w}{int}{w},{w}{int}{w},{w}{int}{w},{w}{int}{w}\)|rgba\({w}{num}%{w},{w}{num}%{w},{w}{num}%{w},{w}{num}{w}\)',
    'hslcolor': r'hsl\({w}{int}{w},{w}{num}%{w},{w}{num}%{w}\)|hsla\({w}{int}{w},{w}{num}%{w},{w}{num}%{w},{w}{num}{w}\)',
    'x11color': r'aliceblue|antiquewhite|aqua|aquamarine|azure|beige|bisque|black|blanchedalmond|blue|blueviolet|brown|burlywood|cadetblue|chartreuse|chocolate|coral|cornflowerblue|cornsilk|crimson|cyan|darkblue|darkcyan|darkgoldenrod|darkgray|darkgreen|darkgrey|darkkhaki|darkmagenta|darkolivegreen|darkorange|darkorchid|darkred|darksalmon|darkseagreen|darkslateblue|darkslategray|darkslategrey|darkturquoise|darkviolet|deeppink|deepskyblue|dimgray|dimgrey|dodgerblue|firebrick|floralwhite|forestgreen|fuchsia|gainsboro|ghostwhite|gold|goldenrod|gray|green|greenyellow|grey|honeydew|hotpink|indianred|indigo|ivory|khaki|lavender|lavenderblush|lawngreen|lemonchiffon|lightblue|lightcoral|lightcyan|lightgoldenrodyellow|lightgray|lightgreen|lightgrey|lightpink|lightsalmon|lightseagreen|lightskyblue|lightslategray|lightslategrey|lightsteelblue|lightyellow|lime|limegreen|linen|magenta|maroon|mediumaquamarine|mediumblue|mediumorchid|mediumpurple|mediumseagreen|mediumslateblue|mediumspringgreen|mediumturquoise|mediumvioletred|midnightblue|mintcream|mistyrose|moccasin|navajowhite|navy|oldlace|olive|olivedrab|orange|orangered|orchid|palegoldenrod|palegreen|paleturquoise|palevioletred|papayawhip|peachpuff|peru|pink|plum|powderblue|purple|red|rosybrown|royalblue|saddlebrown|salmon|sandybrown|seagreen|seashell|sienna|silver|skyblue|slateblue|slategray|slategrey|snow|springgreen|steelblue|tan|teal|thistle|tomato|turquoise|violet|wheat|white|whitesmoke|yellow|yellowgreen',
    'uicolor': r'(ActiveBorder|ActiveCaption|AppWorkspace|Background|ButtonFace|ButtonHighlight|ButtonShadow|ButtonText|CaptionText|GrayText|Highlight|HighlightText|InactiveBorder|InactiveCaption|InactiveCaptionText|InfoBackground|InfoText|Menu|MenuText|Scrollbar|ThreeDDarkShadow|ThreeDFace|ThreeDHighlight|ThreeDLightShadow|ThreeDShadow|Window|WindowFrame|WindowText)',
    }
properties[Profiles.CSS3_COLOR] = {
    'color': r'{namedcolor}|{hexcolor}|{rgbcolor}|{rgbacolor}|{hslcolor}|inherit',
    'opacity': r'{num}|inherit'
    }

# CSS Fonts Module Level 3 http://www.w3.org/TR/css3-fonts/
macros[Profiles.CSS3_FONTS] = {
    'family-name': r'{string}|{ident}', # but STRING is effectively an IDENT??? 
    'font-face-name': 'local\({w}{ident}{w}\)',
    'font-stretch-names': r'(ultra-condensed|extra-condensed|condensed|semi-condensed|semi-expanded|expanded|extra-expanded|ultra-expanded)',
    'unicode-range': r'[uU]\+[0-9A-Fa-f?]{1,6}(\-[0-9A-Fa-f]{1,6})?'
    }
properties[Profiles.CSS3_FONTS] = {
    'font-size-adjust': r'{number}|none|inherit',
    'font-stretch': r'normal|wider|narrower|{font-stretch-names}|inherit'
    }
properties[Profiles.CSS3_FONT_FACE] = {
    'font-family': '{family-name}',
    'font-stretch': r'{font-stretch-names}',                                       
    'font-style': r'normal|italic|oblique',
    'font-weight': r'normal|bold|[1-9]00',
    'src': r'({uri}{w}(format\({w}{string}{w}(\,{w}{string}{w})*\))?|{font-face-name})({w},{w}({uri}{w}(format\({w}{string}{w}(\,{w}{string}{w})*\))?|{font-face-name}))*',
    'unicode-range': '{unicode-range}({w},{w}{unicode-range})*'
    }



# CSS3 Paged Media
macros[Profiles.CSS3_PAGED_MEDIA] = {
    'pagesize': 'a5|a4|a3|b5|b4|letter|legal|ledger',
    'pagebreak': 'auto|always|avoid|left|right'
    }
properties[Profiles.CSS3_PAGED_MEDIA] = {
    'fit': 'fill|hidden|meet|slice',
    'fit-position': r'auto|(({percentage}|{length})(\s*({percentage}|{length}))?|((top|center|bottom)\s*(left|center|right)?)|((left|center|right)\s*(top|center|bottom)?))',
    'image-orientation': 'auto|{angle}',
    'orphans': r'{integer}|inherit',
    'page': 'auto|{ident}',
    'page-break-before': '{pagebreak}|inherit',
    'page-break-after': '{pagebreak}|inherit',
    'page-break-inside': 'auto|avoid|inherit',
    'size': '({length}{w}){1,2}|auto|{pagesize}{w}(?:portrait|landscape)',
    'widows': r'{integer}|inherit'
    }


