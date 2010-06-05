"""LRU caching class and decorator"""
import threading

_marker = object()

class LRUCache(object):
    def __init__(self, size):
        """ Implements a psueudo-LRU algorithm (CLOCK) """
        if size < 1:
            raise ValueError('size must be >1')
        self.clock = []
        for i in xrange(0, size):
            self.clock.append({'key':_marker, 'ref':False})
        self.size = size
        self.maxpos = size - 1
        self.hand = 0
        self.data = {}
        self.lock = threading.Lock()
    
    def __contains__(self, key):
        return key in self.data

    def __getitem__(self, key, default=None):
        try:
            datum = self.data[key]
        except KeyError:
            return default
        pos, val = datum
        self.clock[pos]['ref'] = True
        hand = pos + 1
        if hand > self.maxpos:
            hand = 0
        self.hand = hand
        return val

    def __setitem__(self, key, val, _marker=_marker):
        hand = self.hand
        maxpos = self.maxpos
        clock = self.clock
        data = self.data
        lock = self.lock

        end = hand - 1
        if end < 0:
            end = maxpos

        while 1:
            current = clock[hand]
            ref = current['ref']
            if ref is True:
                current['ref'] = False
                hand = hand + 1
                if hand > maxpos:
                    hand = 0
            elif ref is False or hand == end:
                lock.acquire()
                try:
                    oldkey = current['key']
                    if oldkey in data:
                        del data[oldkey]
                    current['key'] = key
                    current['ref'] = True
                    data[key] = (hand, val)
                    hand += 1
                    if hand > maxpos:
                        hand = 0
                    self.hand = hand
                finally:
                    lock.release()
                break