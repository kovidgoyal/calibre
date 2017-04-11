.. _servertutorial:

Integrating the calibre content server into other servers
==========================================================

Here, we will show you how to integrate the calibre content server into another server. The most common reason for this is to make use of SSL or more sophisticated authentication. The basic technique is to run the calibre server and setup reverse proxying to it from the main server.

.. contents:: Contents
  :depth: 2
  :local:

A reverse proxy is when your normal server accepts incoming requests and passes them onto the calibre server. It then reads the response from the calibre server and forwards it to the client. This means that you can simply run the calibre server as normal without trying to integrate it closely with your main server, and you can take advantage of whatever authentication systems your main server has in place. 

Using a full virtual host
----------------------------

The simplest configuration is to dedicate a full virtual host to the calibre
server. In this case, run the calibre server as::

    calibre-server 

Now setup the virtual host in your main server, for example, for nginx::

    server {
        listen [::]:80;
        server_name myserver.example.com;

        location / {
            proxy_pass http://localhost:8080;
        }
    }

Or, for Apache::

    LoadModule proxy_module modules/mod_proxy.so
    LoadModule proxy_http_module modules/mod_proxy_http.so

    <VirtualHost *:80>
        ServerName myserver.example.com
        ProxyPreserveHost On
        ProxyPass "/"  "http://localhost:8080"
    </VirtualHost>



Using a URL prefix
-----------------------

If you do not want to dedicate a full virtual host to calibre, you can have it
use a URL prefix. Start the calisre server as::

    calibre-server --url-prefix /calibre --port 8080 

The key parameter here is ``--url-prefix /calibre``. This causes the content server to serve all URLs prefixed by calibre. To see this in action, visit ``http://localhost:8080/calibre`` in your browser. You should see the normal content server website, but now it will run under /calibre.

Now suppose you are using Apache as your main server. First enable the proxy modules in apache, by adding the following to :file:`httpd.conf`::

    LoadModule proxy_module modules/mod_proxy.so
    LoadModule proxy_http_module modules/mod_proxy_http.so

The exact technique for enabling the proxy modules will vary depending on your Apache installation. Once you have the proxy modules enabled, add the following rules to httpd.conf (or if you are using virtual hosts to the conf file for the virtual host in question)::

    RewriteEngine on
    RewriteRule ^/calibre/(.*) http://localhost:8080/calibre/$1 [proxy]
    RewriteRule ^/calibre http://localhost:8080 [proxy]

That's all, you will now be able to access the calibre Content Server under the /calibre URL in your apache server. The above rules pass all requests under /calibre to the calibre server running on port 8080 and thanks to the --url-prefix option above, the calibre server handles them transparently.
