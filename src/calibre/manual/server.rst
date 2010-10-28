.. include:: global.rst

.. _servertutorial:

Integrating the |app| content server into other servers
==========================================================

Here, we will show you how to integrate the |app| content server into another server. The most common reason for this is to make use of SSL or more sophisticated authentication. There are two main techniques: Running the |app| content server as a standalone process and using a reverse proxy to connect it with your main server or running the content server in process in your main server with WSGI. The examples below are all for Apache 2.x on linux, but should be easily adaptable to other platforms.

.. contents:: Contents
  :depth: 2
  :local:

.. note:: This only applies to calibre releases >= 0.7.25

Using a reverse proxy
-----------------------

This is the simplest approach as it allows you to use the binary calibre install with no external dependencies/system integration requirements.

First start the |app| content server as shown below::

    calibre-server --url-prefix /calibre --port 8080 

Now suppose you are using Apache as your main server. First enable the proxy modules in apache, by adding the following to :file:`httpd.conf`::

    LoadModule proxy_module modules/mod_proxy.so
    LoadModule proxy_http_module modules/mod_proxy_http.so

The exact technique for enabling the proxy modules will vary depending on your Apache installation. Once you have the proxy modules enabled, add the following rules to httpd.conf (or if you are using virtual hosts to the conf file for the virtual host in question::

    RewriteEngine on
    RewriteRule ^/calibre/(.*) http://localhost:8080/calibre/$1 [proxy]
    RewriteRule ^/calibre http://localhost:8080 [proxy]

That's all, you will now be able to access the |app| Content Server under the /calibre URL in your apache server.

.. note:: If you are willing to devote an entire VirtualHost to the content server, then there is no need to use --url-prefix and RewriteRule, instead just use the ProxyPass directive.

Using WSGI
------------

The calibre content server can be run directly, in process, inside a host server like Apache using the WSGI framework.

.. note:: For this to work, all the dependencies needed by calibre must be installed on your system. On linux, this can be achieved fairly easily by installing the distribution provided calibre package (provided it is up to date).

First, we have to create a WSGI *adapter* for the calibre content server. Here is a template you can use for the purpose. Replace the paths as directed in the comments

.. code-block:: python

    # WSGI script file to run calibre content server as a WSGI app

    import sys, os


    # You can get the paths referenced here by running
    # calibre-debug --paths
    # on your server

    # The first entry from CALIBRE_PYTHON_PATH
    sys.path.insert(0, '/home/kovid/work/calibre/src')

    # CALIBRE_RESOURCES_PATH
    sys.resources_location = '/home/kovid/work/calibre/resources'

    # CALIBRE_EXTENSIONS_PATH
    sys.extensions_location = '/home/kovid/work/calibre/src/calibre/plugins'

    # Path to directory containing calibre executables
    sys.executables_location = '/usr/bin'

    # Path to a directory for which the server has read/write permissions
    # calibre config will be stored here
    os.environ['CALIBRE_CONFIG_DIRECTORY'] = '/var/www/localhost/calibre-config'

    del sys
    del os

    from calibre.library.server.main import create_wsgi_app
    application = create_wsgi_app(
            # The mount point of this WSGI application (i.e. the first argument to
            # the WSGIScriptAlias directive). Set to empty string is mounted at /
            prefix='/calibre',

            # Path to the calibre library to be served
            # The server process must have write permission for all files/dirs
            # in this directory or BAD things will happen
            path_to_library='/home/kovid/documents/demo library'
    )

    del create_wsgi_app

Save this adapter as :file:`calibre-wsgi-adpater.py` somewhere your server will have access to it. 

Let's suppose that we want to use WSGI in Apache. First enable WSGI in Apache by adding the following to :file:`httpd.conf`::

    LoadModule proxy_module modules/mod_wsgi.so

The exact technique for enabling the wsgi module will vary depending on your Apache installation. Once you have the proxy modules enabled, add the following rules to httpd.conf (or if you are using virtual hosts to the conf file for the virtual host in question::

    WSGIScriptAlias /calibre /var/www/localhost/cgi-bin/calibre-wsgi-adapter.py

Change the path to :file:`calibre-wsgi-adapter.py` to wherever you saved it previously (make sure Apache has access to it).

That's all, you will now be able to access the |app| Content Server under the /calibre URL in your apache server.

.. note:: For more help with using mod_wsgi in Apache, see `mod_wsgi <http://code.google.com/p/modwsgi/wiki/WhereToGetHelp>`_.

