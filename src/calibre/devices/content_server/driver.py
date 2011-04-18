'''
Created on 17 Apr 2011

@author: GRiker, modeled on charles's Folder Device

'''

from calibre.constants import DEBUG
from calibre.devices.interface import DevicePlugin
from calibre.devices.usbms.deviceconfig import DeviceConfig
from calibre.devices.usbms.driver import USBMS, BookList

class DriverBase(DeviceConfig, DevicePlugin):
    # Reduce to just the formats eligible for plugboard xforms
    # These formats are shown in the customization dialog
    FORMATS = ['epub', 'mobi']
    USER_CAN_ADD_NEW_FORMATS = False

    # Hide the standard customization widgets
    SUPPORTS_SUB_DIRS = False
    MUST_READ_METADATA = True
    SUPPORTS_USE_AUTHOR_SORT = False


# This class is added to the standard device plugin chain, so that it can
# be configured. It has invalid vendor_id etc, so it will never match a
# device. The 'real' CONTENT_SERVER will use the config from it.
class CONTENT_SERVER_FOR_CONFIG(USBMS):
    name           = 'Content Server Interface'
    gui_name       = 'Content Server'
    description    = _('Enables metadata plugboards to be used with Content Server.')
    author         = 'GRiker'
    supported_platforms = ['windows', 'osx', 'linux']

    VENDOR_ID   = [0xffff]
    PRODUCT_ID  = [0xffff]
    BCD         = [0xffff]
    DEVICE_PLUGBOARD_NAME = 'CONTENT_SERVER'

    def config_widget(cls):
        '''
        Configure a minimal QWidget
        Better to simply disable the config_widget altogether
        '''
        cw = DriverBase.config_widget()
        # Turn off the Save template
        cw.opt_save_template.setVisible(False)
        cw.label.setVisible(False)
        # Hide the up/down arrows
        cw.column_up.setVisible(False)
        cw.column_down.setVisible(False)
        # Retitle
        cw.groupBox.setTitle(_("Enable metadata plugboards for the following formats:"))
        return cw

class CONTENT_SERVER(USBMS):

    FORMATS     = CONTENT_SERVER_FOR_CONFIG.FORMATS
    DEVICE_PLUGBOARD_NAME = 'CONTENT_SERVER'

    def __init__(self):
        if DEBUG:
            print("CONTENT_SERVER.init()")
        pass

    def set_plugboards(self, plugboards, pb_func):
        # This method is called with the plugboard that matches the format
        # declared in use_plugboard_ext and a device name of CONTENT_SERVER
        if DEBUG:
            print("CONTENT_SERVER.set_plugboards()")
            print('  using plugboard %s' % plugboards)
        self.plugboards = plugboards
        self.plugboard_func = pb_func

