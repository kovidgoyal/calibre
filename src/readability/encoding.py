import re
import chardet

def get_encoding(page):
    text = re.sub('</?[^>]*>\s*', ' ', page)
    enc = 'utf-8'
    if not text.strip() or len(text) < 10:
        return enc # can't guess
    try:
        diff = text.decode(enc, 'ignore').encode(enc)
        sizes = len(diff), len(text)
        if abs(len(text) - len(diff)) < max(sizes) * 0.01: # 99% of utf-8
            return enc
    except UnicodeDecodeError:
        pass
    res = chardet.detect(text)
    enc = res['encoding']
    #print '->', enc, "%.2f" % res['confidence']
    if enc == 'MacCyrillic':
        enc = 'cp1251'
    return enc
