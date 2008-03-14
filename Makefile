PYTHON = python

all : gui2 translations resources

clean : 
	cd src/libprs500/gui2 && ${PYTHON} make.py clean

gui2 :
	 cd src/libprs500/gui2 && ${PYTHON} make.py

test : gui2
	cd src/libprs500/gui2 && ${PYTHON} make.py test

translations :
	cd src/libprs500 && ${PYTHON} translations/__init__.py

resources:	
	${PYTHON} resources.py
    
    
