# This file was created automatically by SWIG.
# Don't modify this file, modify the SWIG interface instead.
# This file is compatible with both classic and new-style classes.

from calibre.constants import plugins

_chmlib, chmlib_err = plugins['chmlib']

if chmlib_err:
    raise RuntimeError('Failed to load chmlib: '+chmlib_err)


def _swig_setattr(self,class_type,name,value):
    if (name == "this"):
        if isinstance(value, class_type):
            self.__dict__[name] = value.this
            if hasattr(value,"thisown"):
                self.__dict__["thisown"] = value.thisown
            del value.thisown
            return
    method = class_type.__swig_setmethods__.get(name,None)
    if method:
        return method(self,value)
    self.__dict__[name] = value


def _swig_getattr(self,class_type,name):
    method = class_type.__swig_getmethods__.get(name,None)
    if method:
        return method(self)
    raise AttributeError(name)

import types
try:
    _object = types.ObjectType
    _newclass = 1
except AttributeError:
    class _object :
        pass
    _newclass = 0


CHM_UNCOMPRESSED = _chmlib.CHM_UNCOMPRESSED
CHM_COMPRESSED = _chmlib.CHM_COMPRESSED
CHM_MAX_PATHLEN = _chmlib.CHM_MAX_PATHLEN


class chmUnitInfo(_object):
    __swig_setmethods__ = {}
    __setattr__ = lambda self, name, value: _swig_setattr(self, chmUnitInfo, name, value)
    __swig_getmethods__ = {}
    __getattr__ = lambda self, name: _swig_getattr(self, chmUnitInfo, name)
    __swig_setmethods__["start"] = _chmlib.chmUnitInfo_start_set
    __swig_getmethods__["start"] = _chmlib.chmUnitInfo_start_get
    if _newclass:
        start = property(_chmlib.chmUnitInfo_start_get,_chmlib.chmUnitInfo_start_set)
    __swig_setmethods__["length"] = _chmlib.chmUnitInfo_length_set
    __swig_getmethods__["length"] = _chmlib.chmUnitInfo_length_get
    if _newclass:
        length = property(_chmlib.chmUnitInfo_length_get,_chmlib.chmUnitInfo_length_set)
    __swig_setmethods__["space"] = _chmlib.chmUnitInfo_space_set
    __swig_getmethods__["space"] = _chmlib.chmUnitInfo_space_get
    if _newclass:
        space = property(_chmlib.chmUnitInfo_space_get,_chmlib.chmUnitInfo_space_set)
    __swig_setmethods__["path"] = _chmlib.chmUnitInfo_path_set
    __swig_getmethods__["path"] = _chmlib.chmUnitInfo_path_get
    if _newclass:
        path = property(_chmlib.chmUnitInfo_path_get,_chmlib.chmUnitInfo_path_set)

    def __init__(self,*args):
        _swig_setattr(self, chmUnitInfo, 'this', apply(_chmlib.new_chmUnitInfo,args))
        _swig_setattr(self, chmUnitInfo, 'thisown', 1)

    def __del__(self, destroy=_chmlib.delete_chmUnitInfo):
        try:
            if self.thisown:
                destroy(self)
        except:
            pass

    def __repr__(self):
        return "<C chmUnitInfo instance at %s>" % (self.this,)


class chmUnitInfoPtr(chmUnitInfo):

    def __init__(self,this):
        _swig_setattr(self, chmUnitInfo, 'this', this)
        if not hasattr(self,"thisown"):
            _swig_setattr(self, chmUnitInfo, 'thisown', 0)
        _swig_setattr(self, chmUnitInfo,self.__class__,chmUnitInfo)
_chmlib.chmUnitInfo_swigregister(chmUnitInfoPtr)

chm_open = _chmlib.chm_open

chm_close = _chmlib.chm_close

CHM_PARAM_MAX_BLOCKS_CACHED = _chmlib.CHM_PARAM_MAX_BLOCKS_CACHED
chm_set_param = _chmlib.chm_set_param

CHM_RESOLVE_SUCCESS = _chmlib.CHM_RESOLVE_SUCCESS
CHM_RESOLVE_FAILURE = _chmlib.CHM_RESOLVE_FAILURE
chm_resolve_object = _chmlib.chm_resolve_object

chm_retrieve_object = _chmlib.chm_retrieve_object

CHM_ENUMERATE_NORMAL = _chmlib.CHM_ENUMERATE_NORMAL
CHM_ENUMERATE_META = _chmlib.CHM_ENUMERATE_META
CHM_ENUMERATE_SPECIAL = _chmlib.CHM_ENUMERATE_SPECIAL
CHM_ENUMERATE_FILES = _chmlib.CHM_ENUMERATE_FILES
CHM_ENUMERATE_DIRS = _chmlib.CHM_ENUMERATE_DIRS
CHM_ENUMERATE_ALL = _chmlib.CHM_ENUMERATE_ALL
CHM_ENUMERATOR_FAILURE = _chmlib.CHM_ENUMERATOR_FAILURE
CHM_ENUMERATOR_CONTINUE = _chmlib.CHM_ENUMERATOR_CONTINUE
CHM_ENUMERATOR_SUCCESS = _chmlib.CHM_ENUMERATOR_SUCCESS
chm_enumerate = _chmlib.chm_enumerate

chm_enumerate_dir = _chmlib.chm_enumerate_dir


