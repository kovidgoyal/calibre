"""Experimental settings for special stuff."""

def set(key, value):
    """Call to enable special settings:
    
    ('DXImageTransform.Microsoft', True)
        enable support for parsing special MS only filter values
    
    """
    if key == 'DXImageTransform.Microsoft' and value == True:
        import cssproductions
        cssproductions.PRODUCTIONS.insert(1, cssproductions._DXImageTransform)
    