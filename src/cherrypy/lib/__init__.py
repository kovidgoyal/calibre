"""CherryPy Library"""

import sys as _sys


def modules(modulePath):
    """Load a module and retrieve a reference to that module."""
    try:
        mod = _sys.modules[modulePath]
        if mod is None:
            raise KeyError()
    except KeyError:
        # The last [''] is important.
        mod = __import__(modulePath, globals(), locals(), [''])
    return mod

def attributes(full_attribute_name):
    """Load a module and retrieve an attribute of that module."""
    
    # Parse out the path, module, and attribute
    last_dot = full_attribute_name.rfind(u".")
    attr_name = full_attribute_name[last_dot + 1:]
    mod_path = full_attribute_name[:last_dot]
    
    mod = modules(mod_path)
    # Let an AttributeError propagate outward.
    try:
        attr = getattr(mod, attr_name)
    except AttributeError:
        raise AttributeError("'%s' object has no attribute '%s'"
                             % (mod_path, attr_name))
    
    # Return a reference to the attribute.
    return attr


# public domain "unrepr" implementation, found on the web and then improved.

class _Builder:
    
    def build(self, o):
        m = getattr(self, 'build_' + o.__class__.__name__, None)
        if m is None:
            raise TypeError("unrepr does not recognize %s" %
                            repr(o.__class__.__name__))
        return m(o)
    
    def build_Subscript(self, o):
        expr, flags, subs = o.getChildren()
        expr = self.build(expr)
        subs = self.build(subs)
        return expr[subs]
    
    def build_CallFunc(self, o):
        children = map(self.build, o.getChildren())
        callee = children.pop(0)
        kwargs = children.pop() or {}
        starargs = children.pop() or ()
        args = tuple(children) + tuple(starargs)
        return callee(*args, **kwargs)
    
    def build_List(self, o):
        return map(self.build, o.getChildren())
    
    def build_Const(self, o):
        return o.value
    
    def build_Dict(self, o):
        d = {}
        i = iter(map(self.build, o.getChildren()))
        for el in i:
            d[el] = i.next()
        return d
    
    def build_Tuple(self, o):
        return tuple(self.build_List(o))
    
    def build_Name(self, o):
        if o.name == 'None':
            return None
        if o.name == 'True':
            return True
        if o.name == 'False':
            return False
        
        # See if the Name is a package or module. If it is, import it.
        try:
            return modules(o.name)
        except ImportError:
            pass
        
        # See if the Name is in __builtin__.
        try:
            import __builtin__
            return getattr(__builtin__, o.name)
        except AttributeError:
            pass
        
        raise TypeError("unrepr could not resolve the name %s" % repr(o.name))
    
    def build_Add(self, o):
        left, right = map(self.build, o.getChildren())
        return left + right
    
    def build_Getattr(self, o):
        parent = self.build(o.expr)
        return getattr(parent, o.attrname)
    
    def build_NoneType(self, o):
        return None
    
    def build_UnarySub(self, o):
        return -self.build(o.getChildren()[0])
    
    def build_UnaryAdd(self, o):
        return self.build(o.getChildren()[0])


def unrepr(s):
    """Return a Python object compiled from a string."""
    if not s:
        return s
    
    try:
        import compiler
    except ImportError:
        # Fallback to eval when compiler package is not available,
        # e.g. IronPython 1.0.
        return eval(s)
    
    p = compiler.parse("__tempvalue__ = " + s)
    obj = p.getChildren()[1].getChildren()[0].getChildren()[1]
    
    return _Builder().build(obj)

