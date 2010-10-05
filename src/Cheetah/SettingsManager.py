import sys
import os.path
import copy as copyModule
from ConfigParser import ConfigParser 
import re
from tokenize import Intnumber, Floatnumber, Number
import types
import time
from StringIO import StringIO # not cStringIO because of unicode support
import imp                 # used by SettingsManager.updateSettingsFromPySrcFile()


numberRE = re.compile(Number)
complexNumberRE = re.compile('[\(]*' +Number + r'[ \t]*\+[ \t]*' + Number + '[\)]*')

##################################################
## FUNCTIONS ##

def mergeNestedDictionaries(dict1, dict2, copy=False, deepcopy=False):
    """Recursively merge the values of dict2 into dict1.

    This little function is very handy for selectively overriding settings in a
    settings dictionary that has a nested structure.
    """

    if copy:
        dict1 = copyModule.copy(dict1)
    elif deepcopy:
        dict1 = copyModule.deepcopy(dict1)
        
    for key, val in dict2.iteritems():
        if key in dict1 and isinstance(val, dict) and isinstance(dict1[key], dict):
            dict1[key] = mergeNestedDictionaries(dict1[key], val)
        else:
            dict1[key] = val
    return dict1
    
def stringIsNumber(S):
    """Return True if theString represents a Python number, False otherwise.
    This also works for complex numbers and numbers with +/- in front."""

    S = S.strip()
    
    if S[0] in '-+' and len(S) > 1:
        S = S[1:].strip()
    
    match = complexNumberRE.match(S)
    if not match:
        match = numberRE.match(S)
    if not match or (match.end() != len(S)):
        return False
    else:
        return True
        
def convStringToNum(theString):
    """Convert a string representation of a Python number to the Python version"""
    
    if not stringIsNumber(theString):
        raise Error(theString + ' cannot be converted to a Python number')
    return eval(theString, {}, {})


class Error(Exception):
    pass

class NoDefault(object):
    pass

class ConfigParserCaseSensitive(ConfigParser):
    """A case sensitive version of the standard Python ConfigParser."""
    
    def optionxform(self, optionstr):
        """Don't change the case as is done in the default implemenation."""
        return optionstr

class _SettingsCollector(object):
    """An abstract base class that provides the methods SettingsManager uses to
    collect settings from config files and strings.

    This class only collects settings it doesn't modify the _settings dictionary
    of SettingsManager instances in any way.
    """

    _ConfigParserClass = ConfigParserCaseSensitive 

    def readSettingsFromModule(self, mod, ignoreUnderscored=True):
        """Returns all settings from a Python module.
        """
        S = {}
        attrs = vars(mod)
        for k, v in attrs.iteritems():
            if (ignoreUnderscored and k.startswith('_')):
                continue
            else:
                S[k] = v
        return S
        
    def readSettingsFromPySrcStr(self, theString):
        """Return a dictionary of the settings in a Python src string."""

        globalsDict = {'True': (1==1),
                       'False': (0==1),
                       }
        newSettings = {'self':self}
        exec((theString+os.linesep), globalsDict, newSettings)        
        del newSettings['self']
        module = types.ModuleType('temp_settings_module')
        module.__dict__.update(newSettings)
        return self.readSettingsFromModule(module)

    def readSettingsFromConfigFileObj(self, inFile, convert=True):
        """Return the settings from a config file that uses the syntax accepted by
        Python's standard ConfigParser module (like Windows .ini files).

        NOTE:
        this method maintains case unlike the ConfigParser module, unless this
        class was initialized with the 'caseSensitive' keyword set to False.

        All setting values are initially parsed as strings. However, If the
        'convert' arg is True this method will do the following value
        conversions:
        
        * all Python numeric literals will be coverted from string to number
        
        * The string 'None' will be converted to the Python value None
        
        * The string 'True' will be converted to a Python truth value
        
        * The string 'False' will be converted to a Python false value
        
        * Any string starting with 'python:' will be treated as a Python literal
          or expression that needs to be eval'd. This approach is useful for
          declaring lists and dictionaries.

        If a config section titled 'Globals' is present the options defined
        under it will be treated as top-level settings.        
        """
        
        p = self._ConfigParserClass()
        p.readfp(inFile)
        sects = p.sections()
        newSettings = {}

        sects = p.sections()
        newSettings = {}
        
        for s in sects:
            newSettings[s] = {}
            for o in p.options(s):
                if o != '__name__':
                    newSettings[s][o] = p.get(s, o)

        ## loop through new settings -> deal with global settings, numbers,
        ## booleans and None ++ also deal with 'importSettings' commands

        for sect, subDict in newSettings.items():
            for key, val in subDict.items():
                if convert:
                    if val.lower().startswith('python:'):
                        subDict[key] = eval(val[7:], {}, {})
                    if val.lower() == 'none':
                        subDict[key] = None
                    if val.lower() == 'true':
                        subDict[key] = True
                    if val.lower() == 'false':
                        subDict[key] = False
                    if stringIsNumber(val):
                        subDict[key] = convStringToNum(val)
                        
                ## now deal with any 'importSettings' commands
                if key.lower() == 'importsettings':
                    if val.find(';') < 0:
                        importedSettings = self.readSettingsFromPySrcFile(val)
                    else:
                        path = val.split(';')[0]
                        rest = ''.join(val.split(';')[1:]).strip()
                        parentDict = self.readSettingsFromPySrcFile(path)
                        importedSettings = eval('parentDict["' + rest + '"]')
                        
                    subDict.update(mergeNestedDictionaries(subDict,
                                                           importedSettings))
                        
            if sect.lower() == 'globals':
                newSettings.update(newSettings[sect])
                del newSettings[sect]
                
        return newSettings


class SettingsManager(_SettingsCollector):
    """A mixin class that provides facilities for managing application settings.
    
    SettingsManager is designed to work well with nested settings dictionaries
    of any depth.
    """

    def __init__(self):
        super(SettingsManager, self).__init__()
        self._settings = {}
        self._initializeSettings()

    def _defaultSettings(self):
        return {}
    
    def _initializeSettings(self):
        """A hook that allows for complex setting initialization sequences that
        involve references to 'self' or other settings.  For example:
              self._settings['myCalcVal'] = self._settings['someVal'] * 15        
        This method should be called by the class' __init__() method when needed.       
        The dummy implementation should be reimplemented by subclasses.
        """
        
        pass 

    ## core post startup methods

    def setting(self, name, default=NoDefault):
        """Get a setting from self._settings, with or without a default value."""
        
        if default is NoDefault:
            return self._settings[name]
        else:
            return self._settings.get(name, default)


    def hasSetting(self, key):
        """True/False"""
        return key in self._settings

    def setSetting(self, name, value):
        """Set a setting in self._settings."""
        self._settings[name] = value

    def settings(self):
        """Return a reference to the settings dictionary"""
        return self._settings
        
    def copySettings(self):
        """Returns a shallow copy of the settings dictionary"""
        return copyModule.copy(self._settings)

    def deepcopySettings(self):
        """Returns a deep copy of the settings dictionary"""
        return copyModule.deepcopy(self._settings)
    
    def updateSettings(self, newSettings, merge=True):
        """Update the settings with a selective merge or a complete overwrite."""
        
        if merge:
            mergeNestedDictionaries(self._settings, newSettings)
        else:
            self._settings.update(newSettings)


    ## source specific update methods

    def updateSettingsFromPySrcStr(self, theString, merge=True):
        """Update the settings from a code in a Python src string."""
        
        newSettings = self.readSettingsFromPySrcStr(theString)
        self.updateSettings(newSettings,
                            merge=newSettings.get('mergeSettings', merge) )
        
    
    def updateSettingsFromConfigFileObj(self, inFile, convert=True, merge=True):
        """See the docstring for .updateSettingsFromConfigFile()

        The caller of this method is responsible for closing the inFile file
        object."""

        newSettings = self.readSettingsFromConfigFileObj(inFile, convert=convert)
        self.updateSettings(newSettings,
                            merge=newSettings.get('mergeSettings', merge))

    def updateSettingsFromConfigStr(self, configStr, convert=True, merge=True):
        """See the docstring for .updateSettingsFromConfigFile()
        """

        configStr = '[globals]\n' + configStr
        inFile = StringIO(configStr)
        newSettings = self.readSettingsFromConfigFileObj(inFile, convert=convert)
        self.updateSettings(newSettings,
                            merge=newSettings.get('mergeSettings', merge))

