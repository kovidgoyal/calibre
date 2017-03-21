#!/usr/bin/env python2


__copyright__ = '2015, mushony'

'''
Creates adjustments languages between Latin languages (ltr text) and Semitic languages (rtl text).
'''

from calibre.constants import get_windows_user_locale_name


class html_text():
    def __init__(self, text, tag="p"):
        self.tag = tag
        self.text = text

    def convert(self):
        '''Layout of text to Semitic languages display'''
        from calibre.constants import get_windows_user_locale_name

        lang = get_windows_user_locale_name()
        if lang!="he_IL":
            return self.text

        text = '<'+self.tag+'style="text-align: right" dir="rtl"> '+self.text+ ' </'+self.tag+'>'
        return text

    def convert2(self):
        '''Layout of text to Semitic languages display'''

        lang = get_windows_user_locale_name()
        if lang!="he_IL":
            self.text
        text = self.text.split(r"\n")


        for i in range(1,len(text),1):
            text[i-1],text[i]=text[i],text[i-1]
        self.text = "\n".join(text)

        text = self.convert()

        return text
