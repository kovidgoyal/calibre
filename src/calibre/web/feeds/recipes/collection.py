#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, calendar
from threading import RLock
from datetime import timedelta

from lxml import etree
from lxml.builder import ElementMaker

from calibre import browser
from calibre.utils.date import parse_date, now as nowf, utcnow, tzlocal, \
        isoformat, fromordinal

NS = 'http://calibre-ebook.com/recipe_collection'
E = ElementMaker(namespace=NS, nsmap={None:NS})

def iterate_over_builtin_recipe_files():
    exclude = ['craigslist', 'iht', 'outlook_india', 'toronto_sun',
            'indian_express', 'india_today', 'livemint']
    d = os.path.dirname
    base = os.path.join(d(d(d(d(d(d(os.path.abspath(__file__))))))), 'resources', 'recipes')
    for x in os.walk(base):
        for f in x[-1]:
            fbase, ext = os.path.splitext(f)
            if ext != '.recipe' or fbase in exclude:
                continue
            f = os.path.join(x[0], f)
            rid = os.path.splitext(os.path.relpath(f, base).replace(os.sep,
                '/'))[0]
            yield rid, os.path.join(x[0], f)


def serialize_recipe(urn, recipe_class):

    def attr(n, d):
        ans = getattr(recipe_class, n, d)
        if isinstance(ans, str):
            ans = ans.decode('utf-8', 'replace')
        return ans

    default_author = _('You') if urn.startswith('custom:') else _('Unknown')
    ns = attr('needs_subscription', False)
    if not ns:
        ns = 'no'
    if ns is True:
        ns = 'yes'
    return E.recipe({
        'id'                 : str(urn),
        'title'              : attr('title', _('Unknown')),
        'author'             : attr('__author__', default_author),
        'language'           : attr('language', 'und'),
        'needs_subscription' : ns,
        'description'        : attr('description', '')
        })

def serialize_collection(mapping_of_recipe_classes):
    collection = E.recipe_collection()
    '''
    for urn in sorted(mapping_of_recipe_classes.keys(), key = lambda key: mapping_of_recipe_classes[key].title):
        recipe = serialize_recipe(urn, mapping_of_recipe_classes[urn])
        collection.append(recipe)
    '''
    for urn, recipe_class in mapping_of_recipe_classes.items():
        recipe = serialize_recipe(urn, recipe_class)
        collection.append(recipe)
    collection.set('count', str(len(collection)))
    return etree.tostring(collection, encoding='utf-8', xml_declaration=True,
            pretty_print=True)

def serialize_builtin_recipes():
    from calibre.web.feeds.recipes import compile_recipe
    recipe_mapping = {}
    for rid, f in iterate_over_builtin_recipe_files():
        recipe_class = compile_recipe(open(f, 'rb').read())
        if recipe_class is not None:
            recipe_mapping['builtin:'+rid] = recipe_class

    return serialize_collection(recipe_mapping)

def get_builtin_recipe_collection():
    return etree.parse(P('builtin_recipes.xml')).getroot()

def get_custom_recipe_collection(db):
    from calibre.web.feeds.recipes import compile_recipe
    rmap = {}
    for id, title, recipe in db.get_custom_recipes():
        try:
            recipe_class = compile_recipe(recipe)
            if recipe_class is not None:
                rmap['custom:%d'%id] = recipe_class
        except:
            continue

    return etree.fromstring(serialize_collection(rmap))

def get_builtin_recipe_titles():
    return [r.get('title') for r in get_builtin_recipe_collection()]

def download_builtin_recipe(urn):
    br = browser()
    return br.open_novisit('http://status.calibre-ebook.com/recipe/'+urn).read()


def get_builtin_recipe_by_title(title, log=None, download_recipe=False):
    for x in get_builtin_recipe_collection():
        if x.get('title') == title:
            urn = x.get('id')[8:]
            if download_recipe:
                try:
                    if log is not None:
                        log('Trying to get latest version of recipe:', urn)
                    return download_builtin_recipe(urn)
                except:
                    if log is None:
                        import traceback
                        traceback.print_exc()
                    else:
                        log.exception(
                        'Failed to download recipe, using builtin version')
            return P('recipes/%s.recipe'%urn, data=True)

class SchedulerConfig(object):

    def __init__(self):
        from calibre.utils.config import config_dir
        from calibre.utils.lock import ExclusiveFile
        self.conf_path = os.path.join(config_dir, 'scheduler.xml')
        old_conf_path  = os.path.join(config_dir, 'scheduler.pickle')
        self.root = E.recipe_collection()
        self.lock = RLock()
        if os.access(self.conf_path, os.R_OK):
            with ExclusiveFile(self.conf_path) as f:
                try:
                    self.root = etree.fromstring(f.read())
                except:
                    print 'Failed to read recipe scheduler config'
                    import traceback
                    traceback.print_exc()
        elif os.path.exists(old_conf_path):
            self.migrate_old_conf(old_conf_path)

    def iter_recipes(self):
        for x in self.root:
            if x.tag == '{%s}scheduled_recipe'%NS:
                yield x

    def iter_accounts(self):
        for x in self.root:
            if x.tag == '{%s}account_info'%NS:
                yield x

    def iter_customization(self):
        for x in self.root:
            if x.tag == '{%s}recipe_customization'%NS:
                yield x

    def schedule_recipe(self, recipe, schedule_type, schedule, last_downloaded=None):
        with self.lock:
            for x in list(self.iter_recipes()):
                if x.get('id', False) == recipe.get('id'):
                    ld = x.get('last_downloaded', None)
                    if ld and last_downloaded is None:
                        try:
                            last_downloaded = parse_date(ld)
                        except:
                            pass
                    self.root.remove(x)
                    break
            if last_downloaded is None:
                last_downloaded = fromordinal(1)
            sr = E.scheduled_recipe({
                'id' : recipe.get('id'),
                'title': recipe.get('title'),
                'last_downloaded':isoformat(last_downloaded),
                }, self.serialize_schedule(schedule_type, schedule))
            self.root.append(sr)
            self.write_scheduler_file()

    def customize_recipe(self, urn, add_title_tag, custom_tags):
        with self.lock:
            for x in list(self.iter_customization()):
                if x.get('id') == urn:
                    self.root.remove(x)
            cs = E.recipe_customization({
                'id' : urn,
                'add_title_tag' : 'yes' if add_title_tag else 'no',
                'custom_tags' : ','.join(custom_tags),
                })
            self.root.append(cs)
            self.write_scheduler_file()

    def un_schedule_recipe(self, recipe_id):
        with self.lock:
            for x in list(self.iter_recipes()):
                if x.get('id', False) == recipe_id:
                    self.root.remove(x)
                    break
            self.write_scheduler_file()

    def update_last_downloaded(self, recipe_id):
        with self.lock:
            now = utcnow()
            for x in self.iter_recipes():
                if x.get('id', False) == recipe_id:
                    typ, sch, last_downloaded = self.un_serialize_schedule(x)
                    if typ == 'interval':
                        actual_interval = now - last_downloaded
                        nominal_interval = timedelta(days=sch)
                        if abs(actual_interval - nominal_interval) < \
                                timedelta(hours=1):
                            now = last_downloaded + nominal_interval
                    x.set('last_downloaded', isoformat(now))
                    break
            self.write_scheduler_file()

    def get_to_be_downloaded_recipes(self):
        ans = []
        with self.lock:
            for recipe in self.iter_recipes():
                if self.recipe_needs_to_be_downloaded(recipe):
                    ans.append(recipe.get('id'))
        return ans

    def write_scheduler_file(self):
        from calibre.utils.lock import ExclusiveFile
        self.root.text = '\n\n\t'
        for x in self.root:
            x.tail = '\n\n\t'
        if len(self.root) > 0:
            self.root[-1].tail = '\n\n'
        with ExclusiveFile(self.conf_path) as f:
            f.seek(0)
            f.truncate()
            f.write(etree.tostring(self.root, encoding='utf-8',
                xml_declaration=True, pretty_print=False))

    def serialize_schedule(self, typ, schedule):
        s = E.schedule({'type':typ})
        if typ == 'interval':
            if schedule < 0.1:
                schedule = 1/24.
            text = '%f'%schedule
        elif typ == 'day/time':
            text = '%d:%d:%d'%schedule
        s.text = text
        return s

    def un_serialize_schedule(self, recipe):
        for x in recipe.iterdescendants():
            if 'schedule' in x.tag:
                sch, typ = x.text, x.get('type')
                if typ == 'interval':
                    sch = float(sch)
                elif typ == 'day/time':
                    sch = list(map(int, sch.split(':')))
                return typ, sch, parse_date(recipe.get('last_downloaded'))

    def recipe_needs_to_be_downloaded(self, recipe):
        try:
            typ, sch, ld = self.un_serialize_schedule(recipe)
        except:
            return False
        if typ == 'interval':
            return utcnow() - ld > timedelta(sch)
        elif typ == 'day/time':
            now = nowf()
            ld_local = ld.astimezone(tzlocal())
            day, hour, minute = sch

            is_today = day < 0 or day > 6 or \
                    day == calendar.weekday(now.year, now.month, now.day)
            is_time = now.hour > hour or \
                    (now.hour == hour and now.minute >= minute)
            was_downloaded_already_today = ld_local.date() == now.date()
            return is_today and not was_downloaded_already_today and is_time
        return False

    def set_account_info(self, urn, un, pw):
        with self.lock:
            for x in list(self.iter_accounts()):
                if x.get('id', False) == urn:
                    self.root.remove(x)
                    break
            ac = E.account_info({'id':urn, 'username':un, 'password':pw})
            self.root.append(ac)
            self.write_scheduler_file()

    def get_account_info(self, urn):
        with self.lock:
            for x in self.iter_accounts():
                if x.get('id', False) == urn:
                    return x.get('username', ''), x.get('password', '')

    def get_customize_info(self, urn):
        add_title_tag = True
        custom_tags = []
        with self.lock:
            for x in self.iter_customization():
                if x.get('id', False) == urn:
                    add_title_tag = x.get('add_title_tag', 'yes') == 'yes'
                    custom_tags = [i.strip() for i in x.get('custom_tags',
                        '').split(',')]
                    break
        return add_title_tag, custom_tags

    def get_schedule_info(self, urn):
        with self.lock:
            for x in self.iter_recipes():
                if x.get('id', False) == urn:
                    ans = list(self.un_serialize_schedule(x))
                    return ans

    def migrate_old_conf(self, old_conf_path):
        from calibre.utils.config import DynamicConfig
        c = DynamicConfig('scheduler')
        for r in c.get('scheduled_recipes', []):
            try:
                self.add_old_recipe(r)
            except:
                continue
        for k in c.keys():
            if k.startswith('recipe_account_info'):
                try:
                    urn = k.replace('recipe_account_info_', '')
                    if urn.startswith('recipe_'):
                        urn = 'builtin:'+urn[7:]
                    else:
                        urn = 'custom:%d'%int(urn)
                    try:
                        username, password = c[k]
                    except:
                        username = password = ''
                    self.set_account_info(urn, unicode(username),
                            unicode(password))
                except:
                    continue
        del c
        self.write_scheduler_file()
        try:
            os.remove(old_conf_path)
        except:
            pass

    def add_old_recipe(self, r):
        urn = None
        if r['builtin'] and r['id'].startswith('recipe_'):
            urn = 'builtin:'+r['id'][7:]
        elif not r['builtin']:
            try:
                urn = 'custom:%d'%int(r['id'])
            except:
                return
        schedule = r['schedule']
        typ = 'interval'
        if schedule > 1e5:
            typ = 'day/time'
            raw = '%d'%int(schedule)
            day = int(raw[0]) - 1
            hour = int(raw[2:4]) - 1
            minute = int(raw[-2:]) - 1
            if day >= 7:
                day = -1
            schedule = [day, hour, minute]
        recipe = {'id':urn, 'title':r['title']}
        self.schedule_recipe(recipe, typ, schedule,
        last_downloaded=r['last_downloaded'])




