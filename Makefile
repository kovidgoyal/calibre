APIDOCS=/var/www/libprs500.kovidgoyal.net//htdocs/apidocs

all: doc sdist egg

sdist:
	python setup.py sdist --formats=gztar,zip

egg:
	python setup.py bdist_egg 

doc:
	epydoc --config epydoc.conf
	cp -r docs/html ${APIDOCS}/
	epydoc -v --config epydoc-pdf.conf
	cp docs/pdf/api.pdf ${APIDOCS}/
