PYTHON = python

all : gui2 translations resources 

clean : 
	cd src/calibre/gui2 && ${PYTHON} make.py clean

gui2 :
	 cd src/calibre/gui2 && ${PYTHON} make.py

test : gui2
	cd src/calibre/gui2 && ${PYTHON} make.py test

translations :
	cd src/calibre/translations && ${PYTHON} __init__.py

resources:	
	${PYTHON} resources.py
    
manual:
	make -C src/calibre/manual clean html

pot :
	cd src/calibre/translations && ${PYTHON} __init__.py pot

egg : 
	${PYTHON} setup.py bdist_egg --exclude-source-files

linux_binary:
	${PYTHON} -c "import upload; upload._build_linux()"
