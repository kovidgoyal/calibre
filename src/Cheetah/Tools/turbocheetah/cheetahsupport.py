"Template support for Cheetah"

import sys, os, imp

from Cheetah import Compiler
import pkg_resources

def _recompile_template(package, basename, tfile, classname):
    tmpl = pkg_resources.resource_string(package, "%s.tmpl" % basename)
    c = Compiler.Compiler(source=tmpl, mainClassName='GenTemplate')
    code = str(c)
    mod = imp.new_module(classname)
    ns = dict()
    exec(code, ns)
    tempclass = ns.get("GenTemplate",
                       ns.get('DynamicallyCompiledCheetahTemplate'))
    assert tempclass
    tempclass.__name__ = basename
    setattr(mod, basename, tempclass)
    sys.modules[classname] = mod
    return mod

class TurboCheetah:
    extension = "tmpl"
    
    def __init__(self, extra_vars_func=None, options=None):
        if options is None:
            options = dict()
        self.get_extra_vars = extra_vars_func
        self.options = options
        self.compiledTemplates = {}
        self.search_path = []
    
    def load_template(self, template=None,
                      template_string=None, template_file=None,
                      loadingSite=False):
        """Searches for a template along the Python path.

        Template files must end in ".tmpl" and be in legitimate packages.
        """
        given = len([_f for _f in (template, template_string, template_file) if _f])
        if given > 1:
            raise TypeError(
                "You may give only one of template, template_string, and "
                "template_file")
        if not given:
            raise TypeError(
                "You must give one of template, template_string, or "
                "template_file")
        if template:
            return self.load_template_module(template)
        elif template_string:
            return self.load_template_string(template_string)
        elif template_file:
            return self.load_template_file(template_file)

    def load_template_module(self, classname):

        ct = self.compiledTemplates

        divider = classname.rfind(".")
        if divider > -1:
            package = classname[0:divider]
            basename = classname[divider+1:]
        else:
            raise ValueError("All templates must be in a package")

        if not self.options.get("cheetah.precompiled", False):
            tfile = pkg_resources.resource_filename(package, 
                                                    "%s.%s" % 
                                                    (basename,
                                                    self.extension))
            if classname in ct:
                mtime = os.stat(tfile).st_mtime
                if ct[classname] != mtime:
                    ct[classname] = mtime
                    del sys.modules[classname]
                    mod = _recompile_template(package, basename, 
                                              tfile, classname)
                else:
                    mod = __import__(classname, dict(), dict(), [basename])
            else:
                ct[classname] = os.stat(tfile).st_mtime
                mod = _recompile_template(package, basename, 
                                          tfile, classname)
        else:
            mod = __import__(classname, dict(), dict(), [basename])
        tempclass = getattr(mod, basename)
        return tempclass

    def load_template_string(self, content):
        raise NotImplementedError

    def load_template_file(self, filename):
        raise NotImplementedError

    def render(self, info, format="html", fragment=False, template=None,
               template_string=None, template_file=None):
        tclass = self.load_template(
            template=template, template_string=template_string,
            template_file=template_file)
        if self.get_extra_vars:
            extra = self.get_extra_vars()
        else:
            extra = {}
        tempobj = tclass(searchList=[info, extra])
        if fragment:
            return tempobj.fragment()
        else:
            return tempobj.respond()
