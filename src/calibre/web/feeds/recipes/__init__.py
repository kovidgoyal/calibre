#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Builtin recipes.
'''
recipe_modules = ['recipe_' + r for r in (
           'newsweek', 'atlantic', 'economist', 'portfolio', 'the_register',
           'usatoday', 'outlook_india', 'bbc', 'greader', 'wsj',
           'wired', 'globe_and_mail', 'smh', 'espn', 'business_week', 'miami_herald',
           'ars_technica', 'upi', 'new_yorker', 'irish_times', 'lanacion',
           'discover_magazine', 'scientific_american', 'new_york_review_of_books',
           'daily_telegraph', 'guardian', 'el_pais', 'new_scientist', 'b92',
           'politika', 'moscow_times', 'latimes', 'japan_times', 'san_fran_chronicle',
           'demorgen_be', 'de_standaard', 'ap', 'barrons', 'chr_mon', 'cnn', 'faznet',
           'jpost', 'jutarnji', 'nasa', 'reuters', 'spiegelde', 'wash_post', 'zeitde',
           'blic', 'novosti', 'danas', 'vreme', 'times_online', 'the_scotsman',
           'nytimes_sub', 'nytimes', 'security_watch', 'cyberpresse', 'st_petersburg_times',
           'clarin', 'financial_times', 'heise', 'le_monde', 'harpers', 'science_aas',
           'science_news', 'the_nation', 'lrb', 'harpers_full', 'liberation',
           'linux_magazine', 'telegraph_uk', 'utne', 'sciencedaily', 'forbes',
           'time_magazine', 'endgadget', 'fudzilla', 'nspm_int', 'nspm', 'pescanik',
           'spiegel_int', 'themarketticker', 'tomshardware', 'xkcd', 'ftd', 'zdnet',
           'joelonsoftware', 'telepolis', 'common_dreams', 'nin', 'tomshardware_de',
           'pagina12', 'infobae', 'ambito', 'elargentino', 'sueddeutsche', 'the_age',
           'laprensa', 'amspec', 'freakonomics', 'criticadigital', 'elcronista',
           'shacknews', 'teleread', 'granma', 'juventudrebelde', 'juventudrebelde_english',
           'la_tercera', 'el_mercurio_chile', 'la_cuarta', 'lanacion_chile', 'la_segunda',
           'jb_online', 'estadao', 'o_globo', 'vijesti', 'elmundo', 'the_oz',
           'honoluluadvertiser', 'starbulletin', 'exiled', 'indy_star', 'dna',
           'pobjeda', 'chicago_breaking_news', 'glasgow_herald', 'linuxdevices',
           'hindu', 'cincinnati_enquirer', 'physics_world', 'pressonline',
           'la_republica', 'physics_today', 'chicago_tribune', 'e_novine',
           'al_jazeera', 'winsupersite', 'borba', 'courrierinternational',
           'lamujerdemivida', 'soldiers', 'theonion', 'news_times',
           'el_universal', 'mediapart', 'wikinews_en', 'ecogeek', 'daily_mail',
           'new_york_review_of_books_no_sub', 'politico', 'adventuregamers',
           'mondedurable', 'instapaper', 'dnevnik_cro', 'vecernji_list',
           'nacional_cro', '24sata', 'dnevni_avaz', 'glas_srpske', '24sata_rs',
           'krstarica', 'krstarica_en', 'tanjug', 'laprensa_ni', 'azstarnet',
           'corriere_della_sera_it', 'corriere_della_sera_en', 'msdnmag_en',
           'moneynews', 'der_standard', 'diepresse', 'nzz_ger', 'hna',
           'seattle_times', 'scott_hanselman', 'coding_horror', 'twitchfilms',
           'stackoverflow', 'telepolis_artikel', 'zaobao', 'usnews',
           'straitstimes', 'index_hu', 'pcworld_hu', 'hrt', 'rts', 'axxon_news',
           'h1', 'h2', 'h3', 'phd_comics', 'woz_die', 'elektrolese',
           'climate_progress', 'carta', 'slashdot', 'publico',
           'the_budget_fashionista', 'elperiodico_catalan',
           'elperiodico_spanish', 'expansion_spanish', 'lavanguardia',
           'marca', 'kellog_faculty', 'kellog_insight', 'noaa',
           '7dias', 'buenosaireseconomico', 'huntechnet', 'cubadebate',
           'diagonales', 'miradasalsur', 'newsweek_argentina', 'veintitres',
           'gva_be', 'hln', 'tijd', 'degentenaar', 'inquirer_net', 'uncrate',
           'fastcompany', 'accountancyage', 'laprensa_hn', 'latribuna',
           'eltiempo_hn', 'slate', 'tnxm', 'bbcvietnamese', 'vnexpress',
           'volksrant', 'theeconomictimes_india', 'ourdailybread',
           'monitor', 'republika', 'beta', 'beta_en', 'glasjavnosti',
           'esquire', 'livemint', 'thedgesingapore', 'darknet', 'rga',
           'intelligencer', 'theoldfoodie', 'hln_be', 'honvedelem',
           'the_new_republic', 'philly',
          )]


import re, imp, inspect, time, os
from calibre.web.feeds.news import BasicNewsRecipe, CustomIndexRecipe, AutomaticNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre import __appname__, english_sort

basic_recipes = (BasicNewsRecipe, AutomaticNewsRecipe, CustomIndexRecipe)
basic_recipe_names = (i.__name__ for i in basic_recipes)


#: Compile builtin recipe/profile classes
def load_recipe(module, package='calibre.web.feeds.recipes'):
    module = __import__(package+'.'+module, fromlist=[''])
    for attr in dir(module):
        obj = getattr(module, attr)
        if type(obj) is not type:
            continue
        recipe = False
        for b in obj.__bases__:
            if b in basic_recipes:
                recipe = True
                break
        if not recipe:
            continue
        if obj not in basic_recipes:
            return obj


recipes = [load_recipe(i) for i in recipe_modules]

_tdir = None
_crep = 0
def compile_recipe(src):
    '''
    Compile the code in src and return the first object that is a recipe or profile.
    @param src: Python source code
    @type src: string
    @return: Recipe class or None, if no such class was found in C{src}
    '''
    global _tdir, _crep
    if _tdir is None or not os.path.exists(_tdir):
        _tdir = PersistentTemporaryDirectory('_recipes')
    temp = os.path.join(_tdir, 'recipe%d.py'%_crep)
    _crep += 1
    if not isinstance(src, unicode):
        match = re.search(r'coding[:=]\s*([-\w.]+)', src[:200])
        enc = match.group(1) if match else 'utf-8'
        src = src.decode(enc)
    src = re.sub(r'from __future__.*', '', src)
    f = open(temp, 'wb')
    src = 'from %s.web.feeds.news import BasicNewsRecipe, AutomaticNewsRecipe\n'%__appname__ + src
    src = '# coding: utf-8\n' + src
    src = 'from __future__ import with_statement\n' + src

    src = src.replace('from libprs500', 'from calibre').encode('utf-8')
    f.write(src)
    f.close()
    module = imp.find_module(os.path.splitext(os.path.basename(temp))[0],
        [os.path.dirname(temp)])
    module = imp.load_module(os.path.splitext(os.path.basename(temp))[0], *module)
    classes = inspect.getmembers(module,
            lambda x : inspect.isclass(x) and \
                issubclass(x, (BasicNewsRecipe,)) and \
                x not in basic_recipes)
    if not classes:
        return None

    return classes[0][1]


def get_builtin_recipe(title):
    '''
    Return a builtin recipe/profile class whose title == C{title} or None if no such
    recipe exists.

    @type title: string
    @rtype: class or None
    '''
    for r in recipes:
        if r.title == title:
            return r
    return None

_titles = [r.title for r in recipes]
_titles.sort(cmp=english_sort)
titles = _titles

def migrate_automatic_profile_to_automatic_recipe(profile):
    BeautifulSoup
    oprofile = profile
    profile = compile_recipe(profile)
    if 'BasicUserProfile' not in profile.__name__:
        return oprofile
    return '''\
class BasicUserRecipe%d(AutomaticNewsRecipe):

    title = %s
    oldest_article = %d
    max_articles_per_feed = %d
    summary_length = %d

    feeds = %s

'''%(int(time.time()), repr(profile.title), profile.oldest_article,
    profile.max_articles_per_feed, profile.summary_length, repr(profile.feeds))


