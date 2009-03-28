Test
=====

    * Install django
    * Run ``python manage.py syncdb`` to create database in /tmp/planet.db
    * Run ``python manage.py runserver``
    * Goto `http://localhost:8000/admin` and create Feeds, Sites and Subscribers
    * Planet is at `http://localhost:8000`



Update feeds by running::

    DJANGO_SETTINGS_MODULE=calibre.www.planet.settings feedjack_update.py

Deploy
=======

    * Add settings for deployment environment to settings.py
      * In particular setup caching

    * Run python manage.py syncdb
        * Add super user when asked

    * Setup Apache

    * Goto /admin and add feeds


