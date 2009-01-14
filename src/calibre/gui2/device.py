__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os, traceback, Queue, time
from threading import Thread

from calibre.devices import devices
from calibre.parallel import Job
from calibre.devices.scanner import DeviceScanner

        
class DeviceJob(Job):
    
    def __init__(self, func, *args, **kwargs):
        Job.__init__(self, *args, **kwargs)
        self.func = func
        
    def run(self):
        self.start_work()
        try:
            self.result = self.func(*self.args, **self.kwargs)
        except (Exception, SystemExit), err:
            self.exception = err
            self.traceback = traceback.format_exc()
        finally:
            self.job_done()
        

class DeviceManager(Thread):
    '''
    Worker thread that polls the USB ports for devices. Emits the
    signal connected(PyQt_PyObject, PyQt_PyObject) on connection and
    disconnection events.
    '''
    def __init__(self, connected_slot, job_manager, sleep_time=2):
        '''        
        @param sleep_time: Time to sleep between device probes in millisecs
        @type sleep_time: integer
        '''
        Thread.__init__(self)
        self.setDaemon(True)
        self.devices        = [[d, False] for d in devices()]
        self.device         = None
        self.device_class   = None
        self.sleep_time     = sleep_time
        self.connected_slot = connected_slot
        self.jobs           = Queue.Queue(0)
        self.keep_going     = True
        self.job_manager    = job_manager
        self.current_job    = None
        self.scanner        = DeviceScanner()
        
    def detect_device(self):
        self.scanner.scan()
        for device in self.devices:
            connected = self.scanner.is_device_connected(device[0])
            if connected and not device[1]:
                try:
                    dev = device[0]()
                    dev.open()
                    self.device       = dev
                    self.device_class = dev.__class__
                    self.connected_slot(True)
                except:
                    print 'Unable to open device'
                    traceback.print_exc()
                finally:                        
                    device[1] = True                    
            elif not connected and device[1]:
                while True:
                    try:
                        job = self.jobs.get_nowait()
                        job.abort(Exception(_('Device no longer connected.')))
                    except Queue.Empty:
                        break
                self.device = None
                self.connected_slot(False)
                device[1] ^= True
                
    def next(self):
        if not self.jobs.empty():
            try:
                return self.jobs.get_nowait()
            except Queue.Empty:
                pass
    
    def run(self):
        while self.keep_going:
            self.detect_device()
            while True:
                job = self.next()
                if job is not None:
                    self.current_job = job
                    self.device.set_progress_reporter(job.update_status)
                    self.current_job.run()
                    self.current_job = None
                else:
                    break 
            time.sleep(self.sleep_time)
            
    def create_job(self, func, done, description, args=[], kwargs={}):
        job = DeviceJob(func, done, self.job_manager, 
                        args=args, kwargs=kwargs, description=description)
        self.job_manager.add_job(job)
        self.jobs.put(job)
        return job
    
    def _get_device_information(self):
        info = self.device.get_device_information(end_session=False)
        info = [i.replace('\x00', '').replace('\x01', '') for i in info]
        cp = self.device.card_prefix(end_session=False)
        fs = self.device.free_space()
        return info, cp, fs
    
    def get_device_information(self, done):
        '''Get device information and free space on device'''
        return self.create_job(self._get_device_information, done, 
                    description=_('Get device information'))
        
    
    def _books(self):
        '''Get metadata from device'''
        mainlist = self.device.books(oncard=False, end_session=False)
        cardlist = self.device.books(oncard=True)
        return (mainlist, cardlist)
    
    def books(self, done):
        '''Return callable that returns the list of books on device as two booklists'''
        return self.create_job(self._books, done, description=_('Get list of books on device'))
    
    def _sync_booklists(self, booklists):
        '''Sync metadata to device'''
        self.device.sync_booklists(booklists, end_session=False)
        return self.device.card_prefix(end_session=False), self.device.free_space()
    
    def sync_booklists(self, done, booklists):
        return self.create_job(self._sync_booklists, done, args=[booklists],
                        description=_('Send metadata to device'))
    
    def _upload_books(self, files, names, on_card=False, metadata=None):
        '''Upload books to device: '''
        return self.device.upload_books(files, names, on_card, 
                                        metadata=metadata, end_session=False)
        
    def upload_books(self, done, files, names, on_card=False, titles=None, 
                     metadata=None):
        desc = _('Upload %d books to device')%len(names)
        if titles:
            desc += u':' + u', '.join(titles)
        return self.create_job(self._upload_books, done, args=[files, names], 
                kwargs={'on_card':on_card,'metadata':metadata}, description=desc)
        
    def add_books_to_metadata(self, locations, metadata, booklists):
        self.device.add_books_to_metadata(locations, metadata, booklists)
    
    def _delete_books(self, paths):
        '''Remove books from device'''
        self.device.delete_books(paths, end_session=True)
        
    def delete_books(self, done, paths):
        return self.create_job(self._delete_books, done, args=[paths],
                        description=_('Delete books from device'))
    
    def remove_books_from_metadata(self, paths, booklists):
        self.device.remove_books_from_metadata(paths, booklists)
        
    def _save_books(self, paths, target):
        '''Copy books from device to disk'''
        for path in paths:
            name = path.rpartition('/')[2]
            f = open(os.path.join(target, name), 'wb')
            self.device.get_file(path, f)
            f.close()
        
    def save_books(self, done, paths, target):
        return self.create_job(self._save_books, done, args=[paths, target],
                        description=_('Download books from device'))
    
    def _view_book(self, path, target):
        f = open(target, 'wb')
        self.device.get_file(path, f)
        f.close()
        return target
    
    def view_book(self, done, path, target):
        return self.create_job(self._view_book, done, args=[path, target],
                        description=_('View book on device'))
        