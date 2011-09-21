#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from future_builtins import map

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre import as_unicode

class Control(object):

    def __init__(self, qwe):
        self.qwe = qwe
        self.name = unicode(qwe.attribute('name'))
        self.type = unicode(qwe.attribute('type'))

    def __repr__(self):
        return unicode(self.qwe.toOuterXml())

    @dynamic_property
    def value(self):
        def fget(self):
            if self.type in ('checkbox', 'radio'):
                return unicode(self.qwe.attribute('checked')) == 'checked'
            if self.type in ('text', 'password'):
                return unicode(self.qwe.attribute('value'))

        def fset(self, val):
            if self.type in ('checkbox', 'radio'):
                if val:
                    self.qwe.setAttribute('checked', 'checked')
                else:
                    self.qwe.removeAttribute('checked')
            elif self.type in ('text', 'password'):
                self.qwe.setAttribute('value', as_unicode(val))

        return property(fget=fget, fset=fset)

class RadioControl(object):

    ATTR = 'checked'

    def __init__(self, name, controls):
        self.name = name
        self.type = 'radio'
        self.values = {unicode(c.attribute('value')):c for c in controls}

    def __repr__(self):
        return '%s(%s)'%(self.__class__.__name__, ', '.join(self.values))

    @dynamic_property
    def value(self):
        def fget(self):
            for val, x in self.values.iteritems():
                if unicode(x.attribute(self.ATTR)) == self.ATTR:
                    return val

        def fset(self, val):
            control = None
            for value, x in self.values.iteritems():
                if val == value:
                    control = x
                    break
            if control is not None:
                for x in self.values.itervalues():
                    x.removeAttribute(self.ATTR)
                control.setAttribute(self.ATTR, self.ATTR)

        return property(fget=fget, fset=fset)

class SelectControl(RadioControl):

    ATTR = 'selected'

    def __init__(self, qwe):
        self.qwe = qwe
        self.name = unicode(qwe.attribute('name'))
        self.type = 'select'
        self.values = {unicode(c.attribute('value')):c for c in
                qwe.findAll('option')}


class Form(object):

    def __init__(self, qwe):
        self.qwe = qwe
        self.attributes = {unicode(x):unicode(qwe.attribute(x)) for x in
                qwe.attributeNames()}
        self.input_controls = list(map(Control, qwe.findAll('input')))
        rc = [x for x in self.input_controls if x.type == 'radio']
        self.input_controls = [x for x in self.input_controls if x.type != 'radio']
        rc_names = {x.name for x in rc}
        self.radio_controls = {name:RadioControl(name, [x.qwe for x in rc if x.name == name]) for name in rc_names}
        selects = list(map(SelectControl, qwe.findAll('select')))
        self.select_controls = {x.name:x for x in selects}

    def __getitem__(self, key):
        for x in self.input_controls:
            if key == x.name:
                return x
        for x in (self.radio_controls, self.select_controls):
            try:
                return x[key]
            except KeyError:
                continue
        raise KeyError('No control with the name %s in this form'%key)

    def __repr__(self):
        attrs = ['%s=%s'%(k, v) for k, v in self.attributes.iteritems()]
        return '<form %s>'%(' '.join(attrs))

    def submit_control(self, submit_control_selector=None):
        if submit_control_selector is not None:
            sc = self.qwe.findFirst(submit_control_selector)
            if not sc.isNull():
                return sc
        for c in self.input_controls:
            if c.type == 'submit':
                return c
        for c in self.input_controls:
            if c.type == 'image':
                return c



class FormsMixin(object):

    def __init__(self):
        self.current_form = None

    def find_form(self, css2_selector=None, nr=None):
        mf = self.page.mainFrame()
        if css2_selector is not None:
            candidate = mf.findFirstElement(css2_selector)
            if not candidate.isNull():
                return Form(candidate)
        if nr is not None and int(nr) > -1:
            nr = int(nr)
            forms = mf.findAllElements('form')
            if nr < forms.count():
                return Form(forms.at(nr))

    def all_forms(self):
        '''
        Return all forms present in the current page.
        '''
        mf = self.page.mainFrame()
        return list(map(Form, mf.findAllElements('form').toList()))

    def select_form(self, css2_selector=None, nr=None):
        '''
        Select a form for further processing. Specify the form either with
        css2_selector or nr. Raises ValueError if no matching form is found.

        :param css2_selector: A CSS2 selector, for example:
                    'form[action="/accounts/login"]' or 'form[id="loginForm"]'

        :param nr: An integer >= 0. Selects the nr'th form in the current page.

        '''
        self.current_form = self.find_form(css2_selector=css2_selector, nr=nr)
        if self.current_form is None:
            raise ValueError('No such form found')
        return self.current_form

    def submit(self, submit_control_selector=None, ajax_replies=0, timeout=30.0):
        if self.current_form is None:
            raise ValueError('No form selected, use select_form() first')
        sc = self.current_form.submit_control(submit_control_selector)
        if sc is None:
            raise ValueError('No submit control found in the current form')
        self.current_form = None
        self.click(sc.qwe, ajax_replies=ajax_replies, timeout=timeout)

