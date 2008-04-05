PYTHON = python

all : gui2 translations resources

clean : 
	cd src/calibre/gui2 && ${PYTHON} make.py clean

gui2 :
	 cd src/calibre/gui2 && ${PYTHON} make.py

test : gui2
	cd src/calibre/gui2 && ${PYTHON} make.py test

translations :
	cd src/calibre && ${PYTHON} translations/__init__.py

resources:	
	${PYTHON} resources.py
    
manual:
	make -C src/calibre/manual clean html
