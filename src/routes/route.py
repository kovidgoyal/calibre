import re
import sys
import urllib

if sys.version < '2.4':
    from sets import ImmutableSet as frozenset

from routes.util import _url_quote as url_quote, _str_encode


class Route(object):
    """The Route object holds a route recognition and generation
    routine.
    
    See Route.__init__ docs for usage.
    
    """
    # reserved keys that don't count
    reserved_keys = ['requirements']
    
    # special chars to indicate a natural split in the URL
    done_chars = ('/', ',', ';', '.', '#')
    
    def __init__(self, name, routepath, **kargs):
        """Initialize a route, with a given routepath for
        matching/generation
        
        The set of keyword args will be used as defaults.
        
        Usage::
        
            >>> from routes.base import Route
            >>> newroute = Route(None, ':controller/:action/:id')
            >>> sorted(newroute.defaults.items())
            [('action', 'index'), ('id', None)]
            >>> newroute = Route(None, 'date/:year/:month/:day',  
            ...     controller="blog", action="view")
            >>> newroute = Route(None, 'archives/:page', controller="blog", 
            ...     action="by_page", requirements = { 'page':'\d{1,2}' })
            >>> newroute.reqs
            {'page': '\\\d{1,2}'}
        
        .. Note:: 
            Route is generally not called directly, a Mapper instance
            connect method should be used to add routes.
        
        """
        self.routepath = routepath
        self.sub_domains = False
        self.prior = None
        self.redirect = False
        self.name = name
        self._kargs = kargs
        self.minimization = kargs.pop('_minimize', False)
        self.encoding = kargs.pop('_encoding', 'utf-8')
        self.reqs = kargs.get('requirements', {})
        self.decode_errors = 'replace'
        
        # Don't bother forming stuff we don't need if its a static route
        self.static = kargs.pop('_static', False)
        self.filter = kargs.pop('_filter', None)
        self.absolute = kargs.pop('_absolute', False)
        
        # Pull out the member/collection name if present, this applies only to
        # map.resource
        self.member_name = kargs.pop('_member_name', None)
        self.collection_name = kargs.pop('_collection_name', None)
        self.parent_resource = kargs.pop('_parent_resource', None)
        
        # Pull out route conditions
        self.conditions = kargs.pop('conditions', None)
        
        # Determine if explicit behavior should be used
        self.explicit = kargs.pop('_explicit', False)
                
        # Since static need to be generated exactly, treat them as
        # non-minimized
        if self.static:
            self.external = '://' in self.routepath
            self.minimization = False
        
        # Strip preceding '/' if present, and not minimizing
        if routepath.startswith('/') and self.minimization:
            self.routepath = routepath[1:]
        self._setup_route()
        
    def _setup_route(self):
        # Build our routelist, and the keys used in the route
        self.routelist = routelist = self._pathkeys(self.routepath)
        routekeys = frozenset([key['name'] for key in routelist
                               if isinstance(key, dict)])
        self.dotkeys = frozenset([key['name'] for key in routelist
                                  if isinstance(key, dict) and 
                                     key['type'] == '.'])

        if not self.minimization:
            self.make_full_route()
        
        # Build a req list with all the regexp requirements for our args
        self.req_regs = {}
        for key, val in self.reqs.iteritems():
            self.req_regs[key] = re.compile('^' + val + '$')
        # Update our defaults and set new default keys if needed. defaults
        # needs to be saved
        (self.defaults, defaultkeys) = self._defaults(routekeys, 
                                                      self.reserved_keys, 
                                                      self._kargs.copy())
        # Save the maximum keys we could utilize
        self.maxkeys = defaultkeys | routekeys
        
        # Populate our minimum keys, and save a copy of our backward keys for
        # quicker generation later
        (self.minkeys, self.routebackwards) = self._minkeys(routelist[:])
        
        # Populate our hardcoded keys, these are ones that are set and don't 
        # exist in the route
        self.hardcoded = frozenset([key for key in self.maxkeys \
            if key not in routekeys and self.defaults[key] is not None])
        
        # Cache our default keys
        self._default_keys = frozenset(self.defaults.keys())
    
    def make_full_route(self):
        """Make a full routelist string for use with non-minimized
        generation"""
        regpath = ''
        for part in self.routelist:
            if isinstance(part, dict):
                regpath += '%(' + part['name'] + ')s'
            else:
                regpath += part
        self.regpath = regpath
    
    def make_unicode(self, s):
        """Transform the given argument into a unicode string."""
        if isinstance(s, unicode):
            return s
        elif isinstance(s, str):
            return s.decode(self.encoding)
        elif callable(s):
            return s
        else:
            return unicode(s)
    
    def _pathkeys(self, routepath):
        """Utility function to walk the route, and pull out the valid
        dynamic/wildcard keys."""
        collecting = False
        current = ''
        done_on = ''
        var_type = ''
        just_started = False
        routelist = []
        for char in routepath:
            if char in [':', '*', '{'] and not collecting and not self.static \
               or char in ['{'] and not collecting:
                just_started = True
                collecting = True
                var_type = char
                if char == '{':
                    done_on = '}'
                    just_started = False
                if len(current) > 0:
                    routelist.append(current)
                    current = ''
            elif collecting and just_started:
                just_started = False
                if char == '(':
                    done_on = ')'
                else:
                    current = char
                    done_on = self.done_chars + ('-',)
            elif collecting and char not in done_on:
                current += char
            elif collecting:
                collecting = False
                if var_type == '{':
                    if current[0] == '.':
                        var_type = '.'
                        current = current[1:]
                    else:
                        var_type = ':'
                    opts = current.split(':')
                    if len(opts) > 1:
                        current = opts[0]
                        self.reqs[current] = opts[1]
                routelist.append(dict(type=var_type, name=current))
                if char in self.done_chars:
                    routelist.append(char)
                done_on = var_type = current = ''
            else:
                current += char
        if collecting:
            routelist.append(dict(type=var_type, name=current))
        elif current:
            routelist.append(current)
        return routelist

    def _minkeys(self, routelist):
        """Utility function to walk the route backwards
        
        Will also determine the minimum keys we can handle to generate
        a working route.
        
        routelist is a list of the '/' split route path
        defaults is a dict of all the defaults provided for the route
        
        """
        minkeys = []
        backcheck = routelist[:]
        
        # If we don't honor minimization, we need all the keys in the
        # route path
        if not self.minimization:
            for part in backcheck:
                if isinstance(part, dict):
                    minkeys.append(part['name'])
            return (frozenset(minkeys), backcheck)
        
        gaps = False
        backcheck.reverse()
        for part in backcheck:
            if not isinstance(part, dict) and part not in self.done_chars:
                gaps = True
                continue
            elif not isinstance(part, dict):
                continue
            key = part['name']
            if self.defaults.has_key(key) and not gaps:
                continue
            minkeys.append(key)
            gaps = True
        return  (frozenset(minkeys), backcheck)
    
    def _defaults(self, routekeys, reserved_keys, kargs):
        """Creates default set with values stringified
        
        Put together our list of defaults, stringify non-None values
        and add in our action/id default if they use it and didn't
        specify it.
        
        defaultkeys is a list of the currently assumed default keys
        routekeys is a list of the keys found in the route path
        reserved_keys is a list of keys that are not
        
        """
        defaults = {}
        # Add in a controller/action default if they don't exist
        if 'controller' not in routekeys and 'controller' not in kargs \
           and not self.explicit:
            kargs['controller'] = 'content'
        if 'action' not in routekeys and 'action' not in kargs \
           and not self.explicit:
            kargs['action'] = 'index'
        defaultkeys = frozenset([key for key in kargs.keys() \
                                 if key not in reserved_keys])
        for key in defaultkeys:
            if kargs[key] is not None:
                defaults[key] = self.make_unicode(kargs[key])
            else:
                defaults[key] = None
        if 'action' in routekeys and not defaults.has_key('action') \
           and not self.explicit:
            defaults['action'] = 'index'
        if 'id' in routekeys and not defaults.has_key('id') \
           and not self.explicit:
            defaults['id'] = None
        newdefaultkeys = frozenset([key for key in defaults.keys() \
                                    if key not in reserved_keys])
        
        return (defaults, newdefaultkeys)
        
    def makeregexp(self, clist, include_names=True):
        """Create a regular expression for matching purposes
        
        Note: This MUST be called before match can function properly.
        
        clist should be a list of valid controller strings that can be 
        matched, for this reason makeregexp should be called by the web
        framework after it knows all available controllers that can be
        utilized.
        
        include_names indicates whether this should be a match regexp
        assigned to itself using regexp grouping names, or if names
        should be excluded for use in a single larger regexp to
        determine if any routes match
        
        """
        if self.minimization:
            reg = self.buildnextreg(self.routelist, clist, include_names)[0]
            if not reg:
                reg = '/'
            reg = reg + '/?' + '$'
        
            if not reg.startswith('/'):
                reg = '/' + reg
        else:
            reg = self.buildfullreg(clist, include_names)
        
        reg = '^' + reg
        
        if not include_names:
            return reg
        
        self.regexp = reg
        self.regmatch = re.compile(reg)
    
    def buildfullreg(self, clist, include_names=True):
        """Build the regexp by iterating through the routelist and
        replacing dicts with the appropriate regexp match"""
        regparts = []
        for part in self.routelist:
            if isinstance(part, dict):
                var = part['name']
                if var == 'controller':
                    partmatch = '|'.join(map(re.escape, clist))
                elif part['type'] == ':':
                    partmatch = self.reqs.get(var) or '[^/]+?'
                elif part['type'] == '.':
                    partmatch = self.reqs.get(var) or '[^/.]+?'
                else:
                    partmatch = self.reqs.get(var) or '.+?'
                if include_names:
                    regpart = '(?P<%s>%s)' % (var, partmatch)
                else:
                    regpart = '(?:%s)' % partmatch
                if part['type'] == '.':
                    regparts.append('(?:\.%s)??' % regpart)
                else:
                    regparts.append(regpart)
            else:
                regparts.append(re.escape(part))
        regexp = ''.join(regparts) + '$'
        return regexp
    
    def buildnextreg(self, path, clist, include_names=True):
        """Recursively build our regexp given a path, and a controller
        list.
        
        Returns the regular expression string, and two booleans that
        can be ignored as they're only used internally by buildnextreg.
        
        """
        if path:
            part = path[0]
        else:
            part = ''
        reg = ''
        
        # noreqs will remember whether the remainder has either a string 
        # match, or a non-defaulted regexp match on a key, allblank remembers
        # if the rest could possible be completely empty
        (rest, noreqs, allblank) = ('', True, True)
        if len(path[1:]) > 0:
            self.prior = part
            (rest, noreqs, allblank) = self.buildnextreg(path[1:], clist, include_names)
        
        if isinstance(part, dict) and part['type'] in (':', '.'):
            var = part['name']
            typ = part['type']
            partreg = ''
            
            # First we plug in the proper part matcher
            if self.reqs.has_key(var):
                if include_names:
                    partreg = '(?P<%s>%s)' % (var, self.reqs[var])
                else:
                    partreg = '(?:%s)' % self.reqs[var]
                if typ == '.':
                    partreg = '(?:\.%s)??' % partreg
            elif var == 'controller':
                if include_names:
                    partreg = '(?P<%s>%s)' % (var, '|'.join(map(re.escape, clist)))
                else:
                    partreg = '(?:%s)' % '|'.join(map(re.escape, clist))
            elif self.prior in ['/', '#']:
                if include_names:
                    partreg = '(?P<' + var + '>[^' + self.prior + ']+?)'
                else:
                    partreg = '(?:[^' + self.prior + ']+?)'
            else:
                if not rest:
                    if typ == '.':
                        exclude_chars = '/.'
                    else:
                        exclude_chars = '/'
                    if include_names:
                        partreg = '(?P<%s>[^%s]+?)' % (var, exclude_chars)
                    else:
                        partreg = '(?:[^%s]+?)' % exclude_chars
                    if typ == '.':
                        partreg = '(?:\.%s)??' % partreg
                else:
                    end = ''.join(self.done_chars)
                    rem = rest
                    if rem[0] == '\\' and len(rem) > 1:
                        rem = rem[1]
                    elif rem.startswith('(\\') and len(rem) > 2:
                        rem = rem[2]
                    else:
                        rem = end
                    rem = frozenset(rem) | frozenset(['/'])
                    if include_names:
                        partreg = '(?P<%s>[^%s]+?)' % (var, ''.join(rem))
                    else:
                        partreg = '(?:[^%s]+?)' % ''.join(rem)
            
            if self.reqs.has_key(var):
                noreqs = False
            if not self.defaults.has_key(var): 
                allblank = False
                noreqs = False
            
            # Now we determine if its optional, or required. This changes 
            # depending on what is in the rest of the match. If noreqs is 
            # true, then its possible the entire thing is optional as there's
            # no reqs or string matches.
            if noreqs:
                # The rest is optional, but now we have an optional with a 
                # regexp. Wrap to ensure that if we match anything, we match
                # our regexp first. It's still possible we could be completely
                # blank as we have a default
                if self.reqs.has_key(var) and self.defaults.has_key(var):
                    reg = '(' + partreg + rest + ')?'
                
                # Or we have a regexp match with no default, so now being 
                # completely blank form here on out isn't possible
                elif self.reqs.has_key(var):
                    allblank = False
                    reg = partreg + rest
                
                # If the character before this is a special char, it has to be
                # followed by this
                elif self.defaults.has_key(var) and \
                     self.prior in (',', ';', '.'):
                    reg = partreg + rest
                
                # Or we have a default with no regexp, don't touch the allblank
                elif self.defaults.has_key(var):
                    reg = partreg + '?' + rest
                
                # Or we have a key with no default, and no reqs. Not possible
                # to be all blank from here
                else:
                    allblank = False
                    reg = partreg + rest
            # In this case, we have something dangling that might need to be
            # matched
            else:
                # If they can all be blank, and we have a default here, we know
                # its safe to make everything from here optional. Since 
                # something else in the chain does have req's though, we have
                # to make the partreg here required to continue matching
                if allblank and self.defaults.has_key(var):
                    reg = '(' + partreg + rest + ')?'
                    
                # Same as before, but they can't all be blank, so we have to 
                # require it all to ensure our matches line up right
                else:
                    reg = partreg + rest
        elif isinstance(part, dict) and part['type'] == '*':
            var = part['name']
            if noreqs:
                if include_names:
                    reg = '(?P<%s>.*)' % var + rest
                else:
                    reg = '(?:.*)' + rest
                if not self.defaults.has_key(var):
                    allblank = False
                    noreqs = False
            else:
                if allblank and self.defaults.has_key(var):
                    if include_names:
                        reg = '(?P<%s>.*)' % var + rest
                    else:
                        reg = '(?:.*)' + rest
                elif self.defaults.has_key(var):
                    if include_names:
                        reg = '(?P<%s>.*)' % var + rest
                    else:
                        reg = '(?:.*)' + rest
                else:
                    if include_names:
                        reg = '(?P<%s>.*)' % var + rest
                    else:
                        reg = '(?:.*)' + rest
                    allblank = False
                    noreqs = False
        elif part and part[-1] in self.done_chars:
            if allblank:
                reg = re.escape(part[:-1]) + '(' + re.escape(part[-1]) + rest
                reg += ')?'
            else:
                allblank = False
                reg = re.escape(part) + rest
        
        # We have a normal string here, this is a req, and it prevents us from 
        # being all blank
        else:
            noreqs = False
            allblank = False
            reg = re.escape(part) + rest
        
        return (reg, noreqs, allblank)
    
    def match(self, url, environ=None, sub_domains=False, 
              sub_domains_ignore=None, domain_match=''):
        """Match a url to our regexp. 
        
        While the regexp might match, this operation isn't
        guaranteed as there's other factors that can cause a match to
        fail even though the regexp succeeds (Default that was relied
        on wasn't given, requirement regexp doesn't pass, etc.).
        
        Therefore the calling function shouldn't assume this will
        return a valid dict, the other possible return is False if a
        match doesn't work out.
        
        """
        # Static routes don't match, they generate only
        if self.static:
            return False
        
        match = self.regmatch.match(url)
        
        if not match:
            return False
            
        sub_domain = None
        
        if sub_domains and environ and 'HTTP_HOST' in environ:
            host = environ['HTTP_HOST'].split(':')[0]
            sub_match = re.compile('^(.+?)\.%s$' % domain_match)
            subdomain = re.sub(sub_match, r'\1', host)
            if subdomain not in sub_domains_ignore and host != subdomain:
                sub_domain = subdomain
        
        if self.conditions:
            if 'method' in self.conditions and environ and \
                environ['REQUEST_METHOD'] not in self.conditions['method']:
                return False
            
            # Check sub-domains?
            use_sd = self.conditions.get('sub_domain')
            if use_sd and not sub_domain:
                return False
            elif not use_sd and 'sub_domain' in self.conditions and sub_domain:
                return False
            if isinstance(use_sd, list) and sub_domain not in use_sd:
                return False
        
        matchdict = match.groupdict()
        result = {}
        extras = self._default_keys - frozenset(matchdict.keys())
        for key, val in matchdict.iteritems():
            if key != 'path_info' and self.encoding:
                # change back into python unicode objects from the URL 
                # representation
                try:
                    val = val and val.decode(self.encoding, self.decode_errors)
                except UnicodeDecodeError:
                    return False
            
            if not val and key in self.defaults and self.defaults[key]:
                result[key] = self.defaults[key]
            else:
                result[key] = val
        for key in extras:
            result[key] = self.defaults[key]
        
        # Add the sub-domain if there is one
        if sub_domains:
            result['sub_domain'] = sub_domain
        
        # If there's a function, call it with environ and expire if it
        # returns False
        if self.conditions and 'function' in self.conditions and \
            not self.conditions['function'](environ, result):
            return False
        
        return result
    
    def generate_non_minimized(self, kargs):
        """Generate a non-minimal version of the URL"""
        # Iterate through the keys that are defaults, and NOT in the route
        # path. If its not in kargs, or doesn't match, or is None, this
        # route won't work
        for k in self.maxkeys - self.minkeys:
            if k not in kargs:
                return False
            elif self.make_unicode(kargs[k]) != \
                self.make_unicode(self.defaults[k]):
                return False
                
        # Ensure that all the args in the route path are present and not None
        for arg in self.minkeys:
            if arg not in kargs or kargs[arg] is None:
                if arg in self.dotkeys:
                    kargs[arg] = ''
                else:
                    return False

        # Encode all the argument that the regpath can use
        for k in kargs:
            if k in self.maxkeys:
                if k in self.dotkeys:
                    if kargs[k]:
                        kargs[k] = url_quote('.' + kargs[k], self.encoding)
                else:
                    kargs[k] = url_quote(kargs[k], self.encoding)

        return self.regpath % kargs
    
    def generate_minimized(self, kargs):
        """Generate a minimized version of the URL"""
        routelist = self.routebackwards
        urllist = []
        gaps = False
        for part in routelist:
            if isinstance(part, dict) and part['type'] in (':', '.'):
                arg = part['name']
                
                # For efficiency, check these just once
                has_arg = kargs.has_key(arg)
                has_default = self.defaults.has_key(arg)
                
                # Determine if we can leave this part off
                # First check if the default exists and wasn't provided in the 
                # call (also no gaps)
                if has_default and not has_arg and not gaps:
                    continue
                    
                # Now check to see if there's a default and it matches the 
                # incoming call arg
                if (has_default and has_arg) and self.make_unicode(kargs[arg]) == \
                    self.make_unicode(self.defaults[arg]) and not gaps: 
                    continue
                
                # We need to pull the value to append, if the arg is None and 
                # we have a default, use that
                if has_arg and kargs[arg] is None and has_default and not gaps:
                    continue
                
                # Otherwise if we do have an arg, use that
                elif has_arg:
                    val = kargs[arg]
                
                elif has_default and self.defaults[arg] is not None:
                    val = self.defaults[arg]
                # Optional format parameter?
                elif part['type'] == '.':
                    continue
                # No arg at all? This won't work
                else:
                    return False
                    
                urllist.append(url_quote(val, self.encoding))
                if part['type'] == '.':
                    urllist.append('.')

                if has_arg:
                    del kargs[arg]
                gaps = True
            elif isinstance(part, dict) and part['type'] == '*':
                arg = part['name']
                kar = kargs.get(arg)
                if kar is not None:
                    urllist.append(url_quote(kar, self.encoding))
                    gaps = True
            elif part and part[-1] in self.done_chars:
                if not gaps and part in self.done_chars:
                    continue
                elif not gaps:
                    urllist.append(part[:-1])
                    gaps = True
                else:
                    gaps = True
                    urllist.append(part)
            else:
                gaps = True
                urllist.append(part)
        urllist.reverse()
        url = ''.join(urllist)
        return url
    
    def generate(self, _ignore_req_list=False, _append_slash=False, **kargs):
        """Generate a URL from ourself given a set of keyword arguments
        
        Toss an exception if this
        set of keywords would cause a gap in the url.
        
        """
        # Verify that our args pass any regexp requirements
        if not _ignore_req_list:
            for key in self.reqs.keys():
                val = kargs.get(key)
                if val and not self.req_regs[key].match(self.make_unicode(val)):
                    return False
        
        # Verify that if we have a method arg, its in the method accept list. 
        # Also, method will be changed to _method for route generation
        meth = kargs.get('method')
        if meth:
            if self.conditions and 'method' in self.conditions \
                and meth.upper() not in self.conditions['method']:
                return False
            kargs.pop('method')
        
        if self.minimization:
            url = self.generate_minimized(kargs)
        else:
            url = self.generate_non_minimized(kargs)
        
        if url is False:
            return url
        
        if not url.startswith('/') and not self.static:
            url = '/' + url
        extras = frozenset(kargs.keys()) - self.maxkeys
        if extras:
            if _append_slash and not url.endswith('/'):
                url += '/'
            fragments = []
            # don't assume the 'extras' set preserves order: iterate
            # through the ordered kargs instead
            for key in kargs:
                if key not in extras:
                    continue
                if key == 'action' or key == 'controller':
                    continue
                val = kargs[key]
                if isinstance(val, (tuple, list)):
                    for value in val:
                        fragments.append((key, _str_encode(value, self.encoding)))
                else:
                    fragments.append((key, _str_encode(val, self.encoding)))
            if fragments:
                url += '?'
                url += urllib.urlencode(fragments)
        elif _append_slash and not url.endswith('/'):
            url += '/'
        return url
