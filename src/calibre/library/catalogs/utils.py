#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Greg Riker'
__docformat__ = 'restructuredtext en'

import re

from calibre import prints
from calibre.utils.logging import default_log as log


class NumberToText(object):  # {{{
    '''
    Converts numbers to text
    4.56    => four point fifty-six
    456     => four hundred fifty-six
    4:56    => four fifty-six
    '''
    ORDINALS = ['zeroth','first','second','third','fourth','fifth','sixth','seventh','eighth','ninth']
    lessThanTwenty = ["<zero>","one","two","three","four","five","six","seven","eight","nine",
                        "ten","eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen",
                        "eighteen","nineteen"]
    tens = ["<zero>","<tens>","twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"]
    hundreds = ["<zero>","one","two","three","four","five","six","seven","eight","nine"]

    def __init__(self, number, verbose=False):
        self.number = number
        self.number_as_float = 0.0
        self.text = ''
        self.verbose = verbose
        self.log = log
        self.numberTranslate()

    def stringFromInt(self, intToTranslate):
        # Convert intToTranslate to string
        # intToTranslate is a three-digit number

        tensComponentString = ""
        hundredsComponent = intToTranslate - (intToTranslate % 100)
        tensComponent = intToTranslate % 100

        # Build the hundreds component
        if hundredsComponent:
            hundredsComponentString = "%s hundred" % self.hundreds[hundredsComponent//100]
        else:
            hundredsComponentString = ""

        # Build the tens component
        if tensComponent < 20:
            tensComponentString = self.lessThanTwenty[tensComponent]
        else:
            tensPart = ""
            onesPart = ""

            # Get the tens part
            tensPart = self.tens[tensComponent // 10]
            onesPart = self.lessThanTwenty[tensComponent % 10]

            if intToTranslate % 10:
                tensComponentString = "%s-%s" % (tensPart, onesPart)
            else:
                tensComponentString = "%s" % tensPart

        # Concatenate the results
        result = ''
        if hundredsComponent and not tensComponent:
            result = hundredsComponentString
        elif not hundredsComponent and tensComponent:
            result = tensComponentString
        elif hundredsComponent and tensComponent:
            result = hundredsComponentString + " " + tensComponentString
        else:
            prints(" NumberToText.stringFromInt(): empty result translating %d" % intToTranslate)
        return result

    def numberTranslate(self):
        hundredsNumber = 0
        thousandsNumber = 0
        hundredsString = ""
        thousandsString = ""
        resultString = ""
        self.suffix = ''

        if self.verbose:
            self.log("numberTranslate(): %s" % self.number)

        # Special case ordinals
        if re.search('[st|nd|rd|th]',self.number):
            self.number = re.sub(',','',self.number)
            ordinal_suffix = re.search(r'[\D]', self.number)
            ordinal_number = re.sub(r'\D','',re.sub(',','',self.number))
            if self.verbose:
                self.log("Ordinal: %s" % ordinal_number)
            self.number_as_float = ordinal_number
            self.suffix = self.number[ordinal_suffix.start():]
            if int(ordinal_number) > 9:
                # Some typos (e.g., 'twentyth'), acceptable
                self.text = '%s' % (NumberToText(ordinal_number).text)
            else:
                self.text = '%s' % (self.ORDINALS[int(ordinal_number)])

        # Test for time
        elif re.search(':',self.number):
            if self.verbose:
                self.log("Time: %s" % self.number)
            self.number_as_float = re.sub(':','.',self.number)
            time_strings = self.number.split(":")
            hours = NumberToText(time_strings[0]).text
            minutes = NumberToText(time_strings[1]).text
            self.text = '%s-%s' % (hours.capitalize(), minutes)

        # Test for %
        elif re.search('%', self.number):
            if self.verbose:
                self.log("Percent: %s" % self.number)
            self.number_as_float = self.number.split('%')[0]
            self.text = NumberToText(self.number.replace('%',' percent')).text

        # Test for decimal
        elif re.search('\\.',self.number):
            if self.verbose:
                self.log("Decimal: %s" % self.number)
            self.number_as_float = self.number
            decimal_strings = self.number.split(".")
            left = NumberToText(decimal_strings[0]).text
            right = NumberToText(decimal_strings[1]).text
            self.text = '%s point %s' % (left.capitalize(), right)

        # Test for hypenated
        elif re.search('-', self.number):
            if self.verbose:
                self.log("Hyphenated: %s" % self.number)
            self.number_as_float = self.number.split('-')[0]
            strings = self.number.split('-')
            if re.search('[0-9]+', strings[0]):
                left = NumberToText(strings[0]).text
                right = strings[1]
            else:
                left = strings[0]
                right = NumberToText(strings[1]).text
            self.text = '%s-%s' % (left, right)

        # Test for only commas and numbers
        elif re.search(',', self.number) and not re.search('[^0-9,]',self.number):
            if self.verbose:
                self.log("Comma(s): %s" % self.number)
            self.number_as_float = re.sub(',','',self.number)
            self.text = NumberToText(self.number_as_float).text

        # Test for hybrid e.g., 'K2, 2nd, 10@10'
        elif re.search('[\\D]+', self.number):
            if self.verbose:
                self.log("Hybrid: %s" % self.number)
            # Split the token into number/text
            number_position = re.search(r'\d',self.number).start()
            text_position = re.search(r'\D',self.number).start()
            if number_position < text_position:
                number = self.number[:text_position]
                text = self.number[text_position:]
                self.text = '%s%s' % (NumberToText(number).text,text)
            else:
                text = self.number[:number_position]
                number = self.number[number_position:]
                self.text = '%s%s' % (text, NumberToText(number).text)

        else:
            if self.verbose:
                self.log("Clean: %s" % self.number)
            try:
                self.float_as_number = float(self.number)
                number = int(self.number)
            except:
                return

            if number > 10**9:
                self.text = "%d out of range" % number
                return

            if number == 10**9:
                self.text = "one billion"
            else :
                # Isolate the three-digit number groups
                millionsNumber  = number//10**6
                thousandsNumber = (number - (millionsNumber * 10**6))//10**3
                hundredsNumber  = number - (millionsNumber * 10**6) - (thousandsNumber * 10**3)
                if self.verbose:
                    print("Converting %s %s %s" % (millionsNumber, thousandsNumber, hundredsNumber))

                # Convert hundredsNumber
                if hundredsNumber :
                    hundredsString = self.stringFromInt(hundredsNumber)

                # Convert thousandsNumber
                if thousandsNumber:
                    if number > 1099 and number < 2000:
                        resultString = '%s %s' % (self.lessThanTwenty[number//100],
                                                    self.stringFromInt(number % 100))
                        self.text = resultString.strip().capitalize()
                        return
                    else:
                        thousandsString = self.stringFromInt(thousandsNumber)

                # Convert millionsNumber
                if millionsNumber:
                    millionsString = self.stringFromInt(millionsNumber)

                # Concatenate the strings
                resultString = ''
                if millionsNumber:
                    resultString += "%s million " % millionsString

                if thousandsNumber:
                    resultString += "%s thousand " % thousandsString

                if hundredsNumber:
                    resultString += "%s" % hundredsString

                if not millionsNumber and not thousandsNumber and not hundredsNumber:
                    resultString = "zero"

                if self.verbose:
                    self.log('resultString: %s' % resultString)
                self.text = resultString.strip().capitalize()
# }}}
