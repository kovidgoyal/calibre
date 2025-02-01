#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Greg Riker'
__docformat__ = 'restructuredtext en'

import re

from calibre import prints
from calibre.utils.logging import default_log as log


class NumberToText:  # {{{
    '''
    Converts numbers to text
    4.56    => four point fifty-six
    456     => four hundred fifty-six
    4:56    => four fifty-six
    '''
    ORDINALS = ['zeroth','first','second','third','fourth','fifth','sixth','seventh','eighth','ninth']
    lessThanTwenty = ['<zero>','one','two','three','four','five','six','seven','eight','nine',
                        'ten','eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen',
                        'eighteen','nineteen']
    tens = ['<zero>','<tens>','twenty','thirty','forty','fifty','sixty','seventy','eighty','ninety']
    hundreds = ['<zero>','one','two','three','four','five','six','seven','eight','nine']

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

        tensComponentString = ''
        hundredsComponent = intToTranslate - (intToTranslate % 100)
        tensComponent = intToTranslate % 100

        # Build the hundreds component
        if hundredsComponent:
            hundredsComponentString = f'{self.hundreds[hundredsComponent//100]} hundred'
        else:
            hundredsComponentString = ''

        # Build the tens component
        if tensComponent < 20:
            tensComponentString = self.lessThanTwenty[tensComponent]
        else:
            tensPart = ''
            onesPart = ''

            # Get the tens part
            tensPart = self.tens[tensComponent // 10]
            onesPart = self.lessThanTwenty[tensComponent % 10]

            if intToTranslate % 10:
                tensComponentString = f'{tensPart}-{onesPart}'
            else:
                tensComponentString = f'{tensPart}'

        # Concatenate the results
        result = ''
        if hundredsComponent and not tensComponent:
            result = hundredsComponentString
        elif not hundredsComponent and tensComponent:
            result = tensComponentString
        elif hundredsComponent and tensComponent:
            result = hundredsComponentString + ' ' + tensComponentString
        else:
            prints(f' NumberToText.stringFromInt(): empty result translating {intToTranslate}')
        return result

    def numberTranslate(self):
        hundredsNumber = 0
        thousandsNumber = 0
        hundredsString = ''
        thousandsString = ''
        resultString = ''
        self.suffix = ''

        if self.verbose:
            self.log(f'numberTranslate(): {self.number}')

        # Special case ordinals
        if re.search(r'[st|nd|rd|th]',self.number):
            self.number = self.number.replace(',', '')
            ordinal_suffix = re.search(r'[\D]', self.number)
            ordinal_number = re.sub(r'\D','',self.number.replace(',', ''))
            if self.verbose:
                self.log(f'Ordinal: {ordinal_number}')
            self.number_as_float = ordinal_number
            self.suffix = self.number[ordinal_suffix.start():]
            if int(ordinal_number) > 9:
                # Some typos (e.g., 'twentyth'), acceptable
                self.text = f'{NumberToText(ordinal_number).text}'
            else:
                self.text = f'{self.ORDINALS[int(ordinal_number)]}'

        # Test for time
        elif ':' in self.number:
            if self.verbose:
                self.log(f'Time: {self.number}')
            self.number_as_float = self.number.replace(':', '.')
            time_strings = self.number.split(':')
            hours = NumberToText(time_strings[0]).text
            minutes = NumberToText(time_strings[1]).text
            self.text = f'{hours.capitalize()}-{minutes}'

        # Test for %
        elif '%' in self.number:
            if self.verbose:
                self.log(f'Percent: {self.number}')
            self.number_as_float = self.number.split('%')[0]
            self.text = NumberToText(self.number.replace('%',' percent')).text

        # Test for decimal
        elif '.' in self.number:
            if self.verbose:
                self.log(f'Decimal: {self.number}')
            self.number_as_float = self.number
            decimal_strings = self.number.split('.')
            left = NumberToText(decimal_strings[0]).text
            right = NumberToText(decimal_strings[1]).text
            self.text = f'{left.capitalize()} point {right}'

        # Test for hyphenated
        elif '-' in self.number:
            if self.verbose:
                self.log(f'Hyphenated: {self.number}')
            self.number_as_float = self.number.split('-')[0]
            strings = self.number.split('-')
            if re.search(r'[0-9]+', strings[0]):
                left = NumberToText(strings[0]).text
                right = strings[1]
            else:
                left = strings[0]
                right = NumberToText(strings[1]).text
            self.text = f'{left}-{right}'

        # Test for only commas and numbers
        elif ',' in self.number and not re.search(r'[^0-9,]',self.number):
            if self.verbose:
                self.log(f'Comma(s): {self.number}')
            self.number_as_float = self.number.replace(',', '')
            self.text = NumberToText(self.number_as_float).text

        # Test for hybrid e.g., 'K2, 2nd, 10@10'
        elif re.search(r'[\D]+', self.number):
            if self.verbose:
                self.log(f'Hybrid: {self.number}')
            # Split the token into number/text
            number_position = re.search(r'\d',self.number).start()
            text_position = re.search(r'\D',self.number).start()
            if number_position < text_position:
                number = self.number[:text_position]
                text = self.number[text_position:]
                self.text = f'{NumberToText(number).text}{text}'
            else:
                text = self.number[:number_position]
                number = self.number[number_position:]
                self.text = f'{text}{NumberToText(number).text}'

        else:
            if self.verbose:
                self.log(f'Clean: {self.number}')
            try:
                self.float_as_number = float(self.number)
                number = int(self.number)
            except:
                return

            if number > 10**9:
                self.text = f'{number} out of range'
                return

            if number == 10**9:
                self.text = 'one billion'
            else:
                # Isolate the three-digit number groups
                millionsNumber  = number//10**6
                thousandsNumber = (number - (millionsNumber * 10**6))//10**3
                hundredsNumber  = number - (millionsNumber * 10**6) - (thousandsNumber * 10**3)
                if self.verbose:
                    print(f'Converting {millionsNumber} {thousandsNumber} {hundredsNumber}')

                # Convert hundredsNumber
                if hundredsNumber:
                    hundredsString = self.stringFromInt(hundredsNumber)

                # Convert thousandsNumber
                if thousandsNumber:
                    if number > 1099 and number < 2000:
                        resultString = f'{self.lessThanTwenty[number//100]} {self.stringFromInt(number % 100)}'
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
                    resultString += f'{millionsString} million '

                if thousandsNumber:
                    resultString += f'{thousandsString} thousand '

                if hundredsNumber:
                    resultString += f'{hundredsString}'

                if not millionsNumber and not thousandsNumber and not hundredsNumber:
                    resultString = 'zero'

                if self.verbose:
                    self.log(f'resultString: {resultString}')
                self.text = resultString.strip().capitalize()
# }}}
