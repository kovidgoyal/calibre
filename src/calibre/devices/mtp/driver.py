#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json, pprint
from io import BytesIO

from calibre.constants import iswindows, numeric_version
from calibre.utils.config import from_json, to_json
from calibre.utils.date import now, isoformat

if iswindows:
    from calibre.devices.mtp.windows.driver import MTP_DEVICE as BASE
    BASE
else:
    from calibre.devices.mtp.unix.driver import MTP_DEVICE as BASE
pprint

class MTP_DEVICE(BASE):

    METADATA_CACHE = 'metadata.calibre'
    DRIVEINFO = 'driveinfo.calibre'

    def _update_drive_info(self, storage, location_code, name=None):
        import uuid
        f = storage.find_path((self.DRIVEINFO,))
        dinfo = {}
        if f is not None:
            stream = self.get_file(f)
            try:
                dinfo = json.load(stream, object_hook=from_json)
            except:
                dinfo = None
        if dinfo.get('device_store_uuid', None) is None:
            dinfo['device_store_uuid'] = unicode(uuid.uuid4())
        if dinfo.get('device_name', None) is None:
            dinfo['device_name'] = self.current_friendly_name
        if name is not None:
            dinfo['device_name'] = name
        dinfo['location_code'] = location_code
        dinfo['last_library_uuid'] = getattr(self, 'current_library_uuid', None)
        dinfo['calibre_version'] = '.'.join([unicode(i) for i in numeric_version])
        dinfo['date_last_connected'] = isoformat(now())
        dinfo['mtp_prefix'] = storage.storage_prefix
        raw = json.dumps(dinfo, default=to_json)
        self.put_file(storage, self.DRIVEINFO, BytesIO(raw), len(raw))
        self.driveinfo = dinfo

    def open(self, devices, library_uuid):
        self.current_library_uuid = library_uuid
        BASE.open(self, devices, library_uuid)

    def get_device_information(self, end_session=True):
        self.report_progress(1.0, _('Get device information...'))
        self.driveinfo = {}
        for sid, location_code in ( (self._main_id, 'main'), (self._carda_id,
            'A'), (self._cardb_id, 'B')):
            if sid is None: continue
            self._update_drive_info(self.filesystem_cache.storage(sid), location_code)
        dinfo = self.get_basic_device_information()
        return tuple( list(dinfo) + [self.driveinfo] )

    def card_prefix(self, end_session=True):
        ans = [None, None]
        if self._carda_id is not None:
            ans[0] = self.filesystem_cache.storage(self._carda_id).storage_prefix
        if self._cardb_id is not None:
            ans[1] = self.filesystem_cache.storage(self._cardb_id).storage_prefix
        return tuple(ans)

    def set_driveinfo_name(self, location_code, name):
        sid = {'main':self._main_id, 'A':self._carda_id,
                'B':self._cardb_id}.get(location_code, None)
        if sid is None:
            return
        self._update_drive_info(self.filesystem_cache.storage(sid),
                location_code, name=name)

if __name__ == '__main__':
    dev = MTP_DEVICE(None)
    dev.startup()
    try:
        from calibre.devices.scanner import DeviceScanner
        scanner = DeviceScanner()
        scanner.scan()
        devs = scanner.devices
        cd = dev.detect_managed_devices(devs)
        if cd is None:
            raise ValueError('Failed to detect MTP device')
        dev.open(cd, None)
        pprint.pprint(dev.get_device_information())
    finally:
        dev.shutdown()


