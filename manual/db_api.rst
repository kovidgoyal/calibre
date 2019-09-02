.. _db_api:

API documentation for the database interface
======================================================

.. module:: calibre.db.cache
    :synopsis: The API accessing and manipulating a calibre library. 
    
This API is thread safe (it uses a multiple reader, single writer locking scheme).  You can access this API like this::

        from calibre.library import db
        db = db('Path to calibre library folder').new_api

If you are in a calibre plugin that is part of the main calibre GUI, you
get access to it like this instead::

        db = self.gui.current_db.new_api

.. autoclass:: Cache
   :members:
 

