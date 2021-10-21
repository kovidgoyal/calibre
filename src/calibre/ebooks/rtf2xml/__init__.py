def open_for_read(path):
    return open(path, encoding='utf-8', errors='replace')


def open_for_write(path, append=False):
    mode = 'a' if append else 'w'
    return open(path, mode, encoding='utf-8', errors='replace', newline='')
