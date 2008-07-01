# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2008 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

"""Template loading and caching."""

import os
try:
    import threading
except ImportError:
    import dummy_threading as threading

from calibre.utils.genshi.template.base import TemplateError
from calibre.utils.genshi.util import LRUCache

__all__ = ['TemplateLoader', 'TemplateNotFound']
__docformat__ = 'restructuredtext en'


class TemplateNotFound(TemplateError):
    """Exception raised when a specific template file could not be found."""

    def __init__(self, name, search_path):
        """Create the exception.
        
        :param name: the filename of the template
        :param search_path: the search path used to lookup the template
        """
        TemplateError.__init__(self, 'Template "%s" not found' % name)
        self.search_path = search_path


class TemplateLoader(object):
    """Responsible for loading templates from files on the specified search
    path.
    
    >>> import tempfile
    >>> fd, path = tempfile.mkstemp(suffix='.html', prefix='template')
    >>> os.write(fd, '<p>$var</p>')
    11
    >>> os.close(fd)
    
    The template loader accepts a list of directory paths that are then used
    when searching for template files, in the given order:
    
    >>> loader = TemplateLoader([os.path.dirname(path)])
    
    The `load()` method first checks the template cache whether the requested
    template has already been loaded. If not, it attempts to locate the
    template file, and returns the corresponding `Template` object:
    
    >>> from genshi.template import MarkupTemplate
    >>> template = loader.load(os.path.basename(path))
    >>> isinstance(template, MarkupTemplate)
    True
    
    Template instances are cached: requesting a template with the same name
    results in the same instance being returned:
    
    >>> loader.load(os.path.basename(path)) is template
    True
    
    The `auto_reload` option can be used to control whether a template should
    be automatically reloaded when the file it was loaded from has been
    changed. Disable this automatic reloading to improve performance.
    
    >>> os.remove(path)
    """
    def __init__(self, search_path=None, auto_reload=False,
                 default_encoding=None, max_cache_size=25, default_class=None,
                 variable_lookup='strict', allow_exec=True, callback=None):
        """Create the template laoder.
        
        :param search_path: a list of absolute path names that should be
                            searched for template files, or a string containing
                            a single absolute path; alternatively, any item on
                            the list may be a ''load function'' that is passed
                            a filename and returns a file-like object and some
                            metadata
        :param auto_reload: whether to check the last modification time of
                            template files, and reload them if they have changed
        :param default_encoding: the default encoding to assume when loading
                                 templates; defaults to UTF-8
        :param max_cache_size: the maximum number of templates to keep in the
                               cache
        :param default_class: the default `Template` subclass to use when
                              instantiating templates
        :param variable_lookup: the variable lookup mechanism; either "strict"
                                (the default), "lenient", or a custom lookup
                                class
        :param allow_exec: whether to allow Python code blocks in templates
        :param callback: (optional) a callback function that is invoked after a
                         template was initialized by this loader; the function
                         is passed the template object as only argument. This
                         callback can be used for example to add any desired
                         filters to the template
        :see: `LenientLookup`, `StrictLookup`
        
        :note: Changed in 0.5: Added the `allow_exec` argument
        """
        from calibre.utils.genshi.template.markup import MarkupTemplate

        self.search_path = search_path
        if self.search_path is None:
            self.search_path = []
        elif not isinstance(self.search_path, (list, tuple)):
            self.search_path = [self.search_path]

        self.auto_reload = auto_reload
        """Whether templates should be reloaded when the underlying file is
        changed"""

        self.default_encoding = default_encoding
        self.default_class = default_class or MarkupTemplate
        self.variable_lookup = variable_lookup
        self.allow_exec = allow_exec
        if callback is not None and not callable(callback):
            raise TypeError('The "callback" parameter needs to be callable')
        self.callback = callback
        self._cache = LRUCache(max_cache_size)
        self._uptodate = {}
        self._lock = threading.RLock()

    def load(self, filename, relative_to=None, cls=None, encoding=None):
        """Load the template with the given name.
        
        If the `filename` parameter is relative, this method searches the
        search path trying to locate a template matching the given name. If the
        file name is an absolute path, the search path is ignored.
        
        If the requested template is not found, a `TemplateNotFound` exception
        is raised. Otherwise, a `Template` object is returned that represents
        the parsed template.
        
        Template instances are cached to avoid having to parse the same
        template file more than once. Thus, subsequent calls of this method
        with the same template file name will return the same `Template`
        object (unless the ``auto_reload`` option is enabled and the file was
        changed since the last parse.)
        
        If the `relative_to` parameter is provided, the `filename` is
        interpreted as being relative to that path.
        
        :param filename: the relative path of the template file to load
        :param relative_to: the filename of the template from which the new
                            template is being loaded, or ``None`` if the
                            template is being loaded directly
        :param cls: the class of the template object to instantiate
        :param encoding: the encoding of the template to load; defaults to the
                         ``default_encoding`` of the loader instance
        :return: the loaded `Template` instance
        :raises TemplateNotFound: if a template with the given name could not
                                  be found
        """
        if cls is None:
            cls = self.default_class
        if relative_to and not os.path.isabs(relative_to):
            filename = os.path.join(os.path.dirname(relative_to), filename)
        filename = os.path.normpath(filename)
        cachekey = filename

        self._lock.acquire()
        try:
            # First check the cache to avoid reparsing the same file
            try:
                tmpl = self._cache[cachekey]
                if not self.auto_reload:
                    return tmpl
                uptodate = self._uptodate[cachekey]
                if uptodate is not None and uptodate():
                    return tmpl
            except (KeyError, OSError):
                pass

            search_path = self.search_path
            isabs = False

            if os.path.isabs(filename):
                # Bypass the search path if the requested filename is absolute
                search_path = [os.path.dirname(filename)]
                isabs = True

            elif relative_to and os.path.isabs(relative_to):
                # Make sure that the directory containing the including
                # template is on the search path
                dirname = os.path.dirname(relative_to)
                if dirname not in search_path:
                    search_path = list(search_path) + [dirname]
                isabs = True

            elif not search_path:
                # Uh oh, don't know where to look for the template
                raise TemplateError('Search path for templates not configured')

            for loadfunc in search_path:
                if isinstance(loadfunc, basestring):
                    loadfunc = directory(loadfunc)
                try:
                    filepath, filename, fileobj, uptodate = loadfunc(filename)
                except IOError:
                    continue
                else:
                    try:
                        if isabs:
                            # If the filename of either the included or the 
                            # including template is absolute, make sure the
                            # included template gets an absolute path, too,
                            # so that nested includes work properly without a
                            # search path
                            filename = filepath
                        tmpl = self._instantiate(cls, fileobj, filepath,
                                                 filename, encoding=encoding)
                        if self.callback:
                            self.callback(tmpl)
                        self._cache[cachekey] = tmpl
                        self._uptodate[cachekey] = uptodate
                    finally:
                        if hasattr(fileobj, 'close'):
                            fileobj.close()
                    return tmpl

            raise TemplateNotFound(filename, search_path)

        finally:
            self._lock.release()

    def _instantiate(self, cls, fileobj, filepath, filename, encoding=None):
        """Instantiate and return the `Template` object based on the given
        class and parameters.
        
        This function is intended for subclasses to override if they need to
        implement special template instantiation logic. Code that just uses
        the `TemplateLoader` should use the `load` method instead.
        
        :param cls: the class of the template object to instantiate
        :param fileobj: a readable file-like object containing the template
                        source
        :param filepath: the absolute path to the template file
        :param filename: the path to the template file relative to the search
                         path
        :param encoding: the encoding of the template to load; defaults to the
                         ``default_encoding`` of the loader instance
        :return: the loaded `Template` instance
        :rtype: `Template`
        """
        if encoding is None:
            encoding = self.default_encoding
        return cls(fileobj, filepath=filepath, filename=filename, loader=self,
                   encoding=encoding, lookup=self.variable_lookup,
                   allow_exec=self.allow_exec)

    def directory(path):
        """Loader factory for loading templates from a local directory.
        
        :param path: the path to the local directory containing the templates
        :return: the loader function to load templates from the given directory
        :rtype: ``function``
        """
        def _load_from_directory(filename):
            filepath = os.path.join(path, filename)
            fileobj = open(filepath, 'U')
            mtime = os.path.getmtime(filepath)
            def _uptodate():
                return mtime == os.path.getmtime(filepath)
            return filepath, filename, fileobj, _uptodate
        return _load_from_directory
    directory = staticmethod(directory)

    def package(name, path):
        """Loader factory for loading templates from egg package data.
        
        :param name: the name of the package containing the resources
        :param path: the path inside the package data
        :return: the loader function to load templates from the given package
        :rtype: ``function``
        """
        from pkg_resources import resource_stream
        def _load_from_package(filename):
            filepath = os.path.join(path, filename)
            return filepath, filename, resource_stream(name, filepath), None
        return _load_from_package
    package = staticmethod(package)

    def prefixed(**delegates):
        """Factory for a load function that delegates to other loaders
        depending on the prefix of the requested template path.
        
        The prefix is stripped from the filename when passing on the load
        request to the delegate.
        
        >>> load = prefixed(
        ...     app1 = lambda filename: ('app1', filename, None, None),
        ...     app2 = lambda filename: ('app2', filename, None, None)
        ... )
        >>> print load('app1/foo.html')
        ('app1', 'app1/foo.html', None, None)
        >>> print load('app2/bar.html')
        ('app2', 'app2/bar.html', None, None)
        
        :param delegates: mapping of path prefixes to loader functions
        :return: the loader function
        :rtype: ``function``
        """
        def _dispatch_by_prefix(filename):
            for prefix, delegate in delegates.items():
                if filename.startswith(prefix):
                    if isinstance(delegate, basestring):
                        delegate = directory(delegate)
                    filepath, _, fileobj, uptodate = delegate(
                        filename[len(prefix):].lstrip('/\\')
                    )
                    return filepath, filename, fileobj, uptodate
            raise TemplateNotFound(filename, delegates.keys())
        return _dispatch_by_prefix
    prefixed = staticmethod(prefixed)

directory = TemplateLoader.directory
package = TemplateLoader.package
prefixed = TemplateLoader.prefixed
