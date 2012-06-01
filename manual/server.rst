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

A reverse proxy is when your normal server accepts incoming requests and passes them onto the calibre server. It then reads the response from the calibre server and forwards it to the client. This means that you can simply run the calibre server as normal without trying to integrate it closely with your main server, and you can take advantage of whatever authentication systems you main server has in place. This is the simplest approach as it allows you to use the binary calibre install with no external dependencies/system integration requirements. Below, is an example of how to achieve this with Apache as your main server, but it will work with any server that supports Reverse Proxies.

First start the |app| content server as shown below::

    calibre-server --url-prefix /calibre --port 8080 

The key parameter here is ``--url-prefix /calibre``. This causes the content server to serve all URLs prefixed by calibre. To see this in action, visit ``http://localhost:8080/calibre`` in your browser. You should see the normal content server website, but now it will run under /calibre.

Now suppose you are using Apache as your main server. First enable the proxy modules in apache, by adding the following to :file:`httpd.conf`::

    LoadModule proxy_module modules/mod_proxy.so
    LoadModule proxy_http_module modules/mod_proxy_http.so

The exact technique for enabling the proxy modules will vary depending on your Apache installation. Once you have the proxy modules enabled, add the following rules to httpd.conf (or if you are using virtual hosts to the conf file for the virtual host in question::

    RewriteEngine on
    RewriteRule ^/calibre/(.*) http://localhost:8080/calibre/$1 [proxy]
    RewriteRule ^/calibre http://localhost:8080 [proxy]
    SetEnv force-proxy-request-1.0 1
    SetEnv proxy-nokeepalive 1

That's all, you will now be able to access the |app| Content Server under the /calibre URL in your apache server. The above rules pass all requests under /calibre to the calibre server running on port 8080 and thanks to the --url-prefix option above, the calibre server handles them transparently.

.. note:: If you are willing to devote an entire VirtualHost to the content server, then there is no need to use --url-prefix and RewriteRule, instead just use the ProxyPass directive.

.. note:: The server engine calibre uses, CherryPy, can have trouble with proxying and KeepAlive requests, so turn them off in Apache, with the SetEnv directives shown above.

In process
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

