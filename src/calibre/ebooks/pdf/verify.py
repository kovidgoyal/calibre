from __future__ import with_statement
# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Verify PDF files.
'''

import os

from pyPdf import PdfFileReader

def is_valid_pdf(pdf_path):
    '''
    Returns True if the pdf file is valid.
    '''

    try:
        with open(os.path.abspath(pdf_path), 'rb') as pdf_file:
            pdf = PdfFileReader(pdf_file)
    except:
        return False
    return True

def is_valid_pdfs(pdf_paths):
    '''
    Returns a list of invalid pdf files.
    '''

    invalid = []
    for pdf_path in pdf_paths:
        if not is_valid_pdf(pdf_path):
            invalid.append(pdf_path)
    return invalid

def is_encrypted(pdf_path):
    with open(os.path.abspath(pdf_path), 'rb') as pdf_file:
        pdf = PdfFileReader(pdf_file)
        if pdf.isEncrypted:
            return True
    return False
