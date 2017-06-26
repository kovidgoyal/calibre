The calibre Content server
==============================

The calibre :guilabel:`Content server` allows you to access your calibre
libraries and read books directly in a browser on your favorite mobile phone or
tablet device. As a result, you do not need to install any dedicated book
reading/management apps on your phone. Just use the browser. The server
downloads and stores the book you are reading in an off-line cache so that you
can read it even when there is no internet connection.

.. contents:: Contents
  :depth: 2
  :local:

To start the server, click the :guilabel:`Connect/share` button and choose
:guilabel:`Start Content server`. You might get a message from your computer's
firewall or anti-virus program asking if it is OK to allow access to
``calibre.exe``. Click the ``Allow`` or ``OK`` button.  Then open a browser
(preferably Chrome or Firefox) in your computer and type in the following
address:

    http://127.0.0.1:8080

This will open a page in the browser showing you your calibre libraries, click
on any one and browse the books in it. Click on a book, and it will show you
all the metadata about the book, along with buttons to :guilabel:`Read book`
and :guilabel:`Download book`. Click the :guilabel:`Read book` button to
start reading the book. 

.. note:: The address used above ``http://127.0.0.1:8080`` will only work on
    the computer that is running calibre. To access the server from other
    computers/phones/tablets/etc. you will need to do a little more work,
    as described in the next section.


Accessing the Content server from other devices
---------------------------------------------------

There are two types of remote device access that you will typically need. The
first, simpler kind is from within your home network. If you are running
calibre on a computer on your home network and you have also connected your
other devices to the same home network, then you should be easily able to
access the server on those devices. 

Accessing the server from devices on your home network
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

After starting the server in calibre as described above, click the
:guilabel:`Connect/share` button again. Instead of the :guilabel:`Start Content
server` action, you should see a :guilabel:`Stop Content server` action
instead. To the right of this action will be listed an IP address
and port number. These look like a bunch of numbers separated by periods. For
example::

    Stop Content server [192.168.1.5, port 8080]

These numbers tell you what address to use to connect to the server in your
devices. Following the example above, the address becomes::

    http://192.168.1.5:8080

The first part of the address is always ``http://`` the next part is the IP
address, which is the numbers before the comma and finally we have the port
number which must be added to the IP address with a colon (``:``). If you are
lucky, that should be all you need and you will be looking at the
calibre libraries on your device. If not, read on. 


Trouble-shooting the home network connection
__________________________________________________

If you are unable to access the server from your device, try the following
steps:

  #. Check that the server is running by opening the address
     ``http://127.0.0.1:8080`` in a browser running on the same computer as
     the server.

  #. Check that your firewall/anti-virus is allowing connections to your
     computer on the port ``8080`` and to the calibre program. The
     easiest way to eliminate the firewall/anti-virus as the source of
     problems is to temporarily turn them both off and then try connecting. You
     should first disconnect from the internet, before turning off the
     firewall, to keep your computer safe.

  #. Check that your device and computer are on the same network. This means
     they should both be connected to the same wireless router. In particular
     neither should be using a cellular or ISP provided direct-WiFi connection.

  #. If you have non-standard networking setup, it might be that the IP
     address shown on the :guilabel:`Connect/share` menu is incorrect.
     In such a case you will have to figure out what the correct IP address 
     to use is, yourself. Unfortunately, given the infinite diversity of
     network configurations possible, it is not possible to give you a
     roadmap for doing so.

  #. If you are stuck, you can always ask for help in the `calibre user forums`_.


Accessing the server from anywhere on the internet
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. warning:: 

    Before doing this you should turn on username/password protection in the
    server, otherwise anyone in the world will be able to access your books.
    Go to :guilabel:`Preferences->Sharing->Sharing over the net` and enable the
    option to :guilabel:`Require username and password to access the content
    server`.

While the particular details on setting up internet access vary depending on
the network configuration and type of computer you are using, the basic schema
is as follows.

  #. Find out the external IP address of the computer you are going to run the
     server on. You can do that by visiting the site `What is my IP address
     <https://www.whatismyip.com/>`_ in a browser running on the computer.

  #. If the computer is behind a router, enable port forwarding on the router
     to forward the port ``8080`` (or whatever port you choose to run the
     calibre Content server on) to the computer. 

  #. Make sure the calibre server is allowed through any firewalls/anti-virus
     programs on your computer.

  #. Now you should be able to access the server on any internet-connected
     device using the IP address you found in the first step. For example,
     if the IP address you found was ``123.123.123.123`` and the port you are
     using for the calibre server is ``8080``, the address to use on your
     device becomes: ``http://123.123.123.123:8080``.

  #. Optionally, use a service like `no-ip <https://www.noip.com/free>`_ to
     setup an easy to remember address to use instead of the IP address you
     found in the first step.

.. note:: 
    For maximum security, you should also enable HTTPS on the content server.
    You can either do so directly in the server by providing the path to
    the HTTPS certificate to use in the advanced configuration options for
    the server, or you can setup a reverse proxy as described below, to use
    an existing https setup.


The server interface
-----------------------

The server interface is a simplified version of the main calibre interface,
optimised for use with touch screens. The home screen shows you books
you are currently reading as well as allowing to choose a calibre library you
want to browse. The server in calibre 3 gives you access to all your libraries,
not just a single one, as before. 

The book list
^^^^^^^^^^^^^^

The server book list is a simple grid of covers. Tap on a cover to see the
detailed metadata for a book, or to read the book. If you prefer a more
detailed list, you can change the default view by clicking the three vertical
dots in the top right corner.

Sorting and searching of the book list should be familiar to calibre users.
They can be accessed by clicking their icons in the top right area. They both
work exactly the same as in the main calibre program. The search page even
allows you to construct search queries by clicking on authors/tags/etc., just as
you can using the Tag browser in the main program.

A much loved feature of the main program, :guilabel:`Virtual libraries` is
present in the server interface as well. Click the three vertical dots in the
top right corner to choose a virtual library.

The book reader
^^^^^^^^^^^^^^^^

You can read any book in your calibre library by simply tapping on
it and then tapping the :guilabel:`Read book` button. The books reader
is very simple to operate. You can both tap and swipe to turn pages. Swiping
up/down skips between chapters. Tapping the top quarter of the screen gets you
the detailed controls and viewer preferences.

If you leave the Content server running, you can even open the same book on
multiple devices and it will remember your last read position. If it does not
you can force a sync by tapping in the top quarter and choosing
:guilabel:`Sync`.

.. note:: On initial release, the book reader is fully functional but is
    missing some more advanced features from the main calibre viewer, such as 
    popup footnotes, bookmarks and annotations in general.
    These will be added in due course. In fact, the browser reader is designed
    to eventually replace the main viewer, once it matures.

Browser support
------------------

The new calibre server makes lots of use of advanced HTML 5 and CSS 3 features.
As such it requires an up-to-date browser to use. It has been tested on Android
Chrome and iOS Safari as well as Chrome and Firefox on the desktop. It is known
not to work with Internet Explorer and Microsoft Edge (hopefully Edge will
start working when Microsoft gets around to implementing a few missing
standards). 

The server is careful to use functionality that has either been already
standardised or is on the standards track. As such if it does not currently
work with your favorite browser, it probably will once that browser has caught
up. 

If you are using a particular old or limited browser or you don't like to run
JavaScript, you can use the *mobile* view, by simply adding ``/mobile`` to the
the server address.

.. note:: 
    On iOS, Apple allows only a single browser engine, so Firefox, Chrome and
    Safari are all actually the same browser under the hood. The new server
    interface requires iOS 10.3.2 or newer. On Android, the server has been 
    tested with Chrome version 58 and newer.

Managing user accounts from the command-line only
-----------------------------------------------------

The calibre program has a nice section in :guilabel:`Preferences` to allow you
to manage user accounts for the server. However, if you want to run the
standalone server and cannot run the main calibre program on the same
computer/user account, you can also manage users using just the command-line.

You can manage user accounts using the ``--manage-users`` option
to the standalone ``calibre-server`` program. Suppose you want to store
the user database in the directory ``/srv/calibre``, then you create it
by running::

    calibre-server --userdb /srv/calibre/users.sqlite --manage-users

Just follow the prompts to create user accounts, set their permission, etc.
Once you are done, you can run the server as::

    calibre-server --userdb /srv/calibre/users.sqlite --enable-auth 

It will use the user accounts you created in the previous step.


Integrating the calibre Content server into other servers
------------------------------------------------------------

Here, we will show you how to integrate the calibre Content server into another
server. The most common reason for this is to make use of SSL. The basic
technique is to run the calibre server and setup a reverse proxy to it from the
main server.

A reverse proxy is when your normal server accepts incoming requests and passes
them onto the calibre server. It then reads the response from the calibre
server and forwards it to the client. This means that you can simply run the
calibre server as normal without trying to integrate it closely with your main
server, and you can take advantage of whatever authentication systems your main
server has in place. 

Using a full virtual host
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The simplest configuration is to dedicate a full virtual host to the calibre
server. In this case, run the calibre server as::

    calibre-server 

Now setup the virtual host in your main server, for example, for nginx::

    server {
        listen [::]:80;
        server_name myserver.example.com;

        location / {
            proxy_pass http://127.0.0.1:8080;
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
^^^^^^^^^^^^^^^^^^^^^^^

If you do not want to dedicate a full virtual host to calibre, you can have it
use a URL prefix. Start the calibre server as::

    calibre-server --url-prefix /calibre --port 8080 

The key parameter here is ``--url-prefix /calibre``. This causes the Content server to serve all URLs prefixed by calibre. To see this in action, visit ``http://localhost:8080/calibre`` in your browser. You should see the normal Content server website, but now it will run under /calibre.

With nginx, the required configuration is::

    proxy_set_header X-Forwarded-For $remote_addr;
    location /calibre/ {
        proxy_buffering off;
        proxy_pass http://127.0.0.1:8080/$request_uri;
    }
    location /calibre {
        # we need a trailing slash for the Application Cache to work
        return 301 $scheme://$host$uri/;
    }


For Apache, first enable the proxy modules in Apache, by adding the following to :file:`httpd.conf`::

    LoadModule proxy_module modules/mod_proxy.so
    LoadModule proxy_http_module modules/mod_proxy_http.so

The exact technique for enabling the proxy modules will vary depending on your Apache installation. Once you have the proxy modules enabled, add the following rules to httpd.conf (or if you are using virtual hosts to the conf file for the virtual host in question)::

    RewriteEngine on
    RewriteRule ^/calibre/(.*) http://127.0.0.1:8080/calibre/$1 [proxy]
    RedirectMatch permanent ^/calibre$ /calibre/

That's all, you will now be able to access the calibre Content server under the /calibre URL in your main server. The above rules pass all requests under /calibre to the calibre server running on port 8080 and thanks to the --url-prefix option above, the calibre server handles them transparently.


.. note:: 

    If you have setup SSL for your main server, you should tell the calibre
    server to use basic authentication instead of digest authentication, as it
    is faster. To do so, pass the ``--auth-mode=basic`` option to
    ``calibre-server``.

.. _calibre user forums: https://www.mobileread.com/forums/forumdisplay.php?f=166
