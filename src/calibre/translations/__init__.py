__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Manage translation of user visible strings.
'''
import shutil, tarfile, re, os, subprocess, urllib2

language_codes = {
    'aa':'Afar','ab':'Abkhazian','af':'Afrikaans','am':'Amharic','ar':'Arabic','as':'Assamese','ay':'Aymara','az':'Azerbaijani',
    'ba':'Bashkir','be':'Byelorussian','bg':'Bulgarian','bh':'Bihari','bi':'Bislama','bn':'Bengali','bo':'Tibetan','br':'Breton',
    'ca':'Catalan','co':'Corsican','cs':'Czech','cy':'Welsh',
    'da':'Danish','de':'German','dz':'Bhutani',
    'el':'Greek','en':'English','eo':'Esperanto','es':'Spanish','et':'Estonian','eu':'Basque',
    'fa':'Persian','fi':'Finnish','fj':'Fiji','fo':'Faroese','fr':'French','fy':'Frisian',
    'ga':'Irish','gd':'Scots Gaelic','gl':'Galician','gn':'Guarani','gu':'Gujarati',
    'ha':'Hausa','he':'Hebrew','hi':'Hindi','hr':'Croatian','hu':'Hungarian','hy':'Armenian',
    'ia':'Interlingua','id':'Indonesian','ie':'Interlingue','ik':'Inupiak','is':'Icelandic','it':'Italian','iu':'Inuktitut',
    'ja':'Japanese','jw':'Javanese',
    'ka':'Georgian','kk':'Kazakh','kl':'Greenlandic','km':'Cambodian','kn':'Kannada','ko':'Korean','ks':'Kashmiri','ku':'Kurdish','ky':'Kirghiz',
    'la':'Latin','ln':'Lingala','lo':'Laothian','lt':'Lithuanian','lv':'Latvian, Lettish',
    'mg':'Malagasy','mi':'Maori','mk':'Macedonian','ml':'Malayalam','mn':'Mongolian','mo':'Moldavian','mr':'Marathi','ms':'Malay','mt':'Maltese','my':'Burmese',
    'na':'Nauru','nb':'Norwegian Bokmal','nds':'German,Low','ne':'Nepali','nl':'Dutch','no':'Norwegian',
    'oc':'Occitan','om':'(Afan) Oromo','or':'Oriya',
    'pa':'Punjabi','pl':'Polish','ps':'Pashto, Pushto','pt':'Portuguese',
    'qu':'Quechua',
    'rm':'Rhaeto-Romance','rn':'Kirundi','ro':'Romanian','ru':'Russian','rw':'Kinyarwanda',
    'sa':'Sanskrit','sd':'Sindhi','sg':'Sangho','sh':'Serbo-Croatian','si':'Sinhalese','sk':'Slovak','sl':'Slovenian','sm':'Samoan','sn':'Shona','so':'Somali','sq':'Albanian','sr':'Serbian','ss':'Siswati','st':'Sesotho','su':'Sundanese','sv':'Swedish','sw':'Swahili',  # noqa
    'ta':'Tamil','te':'Telugu','tg':'Tajik','th':'Thai','ti':'Tigrinya','tk':'Turkmen','tl':'Tagalog','tn':'Setswana','to':'Tonga','tr':'Turkish','ts':'Tsonga','tt':'Tatar','tw':'Twi',  # noqa
    'ug':'Uighur','uk':'Ukrainian','ur':'Urdu','uz':'Uzbek',
    'vi':'Vietnamese','vo':'Volapuk',
    'wo':'Wolof',
    'xh':'Xhosa',
    'yi':'Yiddish','yo':'Yoruba',
    'za':'Zhuang','zh':'Chinese','zu':'Zulu'
}


def import_from_launchpad(url):
    f = open('/tmp/launchpad_export.tar.gz', 'wb')
    shutil.copyfileobj(urllib2.urlopen(url), f)
    f.close()
    tf = tarfile.open('/tmp/launchpad_export.tar.gz', 'r:gz')
    next = tf.next()
    while next is not None:
        if next.isfile() and next.name.endswith('.po'):
            try:
                po = re.search(r'-([a-z]{2,3}\.po)', next.name).group(1)
            except:
                next = tf.next()
                continue
            out = os.path.abspath(os.path.join('.', os.path.basename(po)))
            print 'Updating', '%6s'%po, '-->', out
            open(out, 'wb').write(tf.extractfile(next).read())
        next = tf.next()
    check_for_critical_bugs()
    path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    print path
    subprocess.check_call('python setup.py translations'.split(), cwd=path)
    return 0


def check_for_critical_bugs():
    if os.path.exists('.errors'):
        shutil.rmtree('.errors')
    pofilter = ('pofilter', '-i', '.', '-o', '.errors',
                '-t', 'accelerators', '-t', 'escapes', '-t', 'variables',
                # '-t', 'xmltags',
                '-t', 'printf')
    subprocess.check_call(pofilter)
    errs = os.listdir('.errors')
    if errs:
        print 'WARNING: Translation errors detected'
        print 'See the .errors directory and http://translate.sourceforge.net/wiki/toolkit/using_pofilter'

if __name__ == '__main__':
    import sys
    import_from_launchpad(sys.argv[1])

