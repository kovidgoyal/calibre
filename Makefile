TRAC_ROOT=/var/lib/trac/libprs500/htdocs/apidocs

all: doc sdist egg

sdist:
	python setup.py sdist --formats=gztar,zip

egg:
	python setup.py bdist_egg 

doc:
	epydoc --config epydoc.conf
	cp -r docs/html ${TRAC_ROOT}/
	epydoc -v --config epydoc-pdf.conf
	cp docs/pdf/api.pdf ${TRAC_ROOT}/
