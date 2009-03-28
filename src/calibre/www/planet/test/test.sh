#!/bin/sh
cp planet.db /tmp
cd ..
python manage.py runserver
