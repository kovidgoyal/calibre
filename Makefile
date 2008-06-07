PYTHON = python

all : plugins pictureflow gui2 translations resources 

plugins:
	mkdir -p src/calibre/plugins

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

pictureflow :
	mkdir -p src/calibre/plugins && rm -f src/calibre/plugins/*pictureflow* && \
	cd src/calibre/gui2/pictureflow && rm -f *.o && \
	mkdir -p .build && cd .build && rm -f * && \
	qmake ../pictureflow.pro && make staticlib && \
	cd ../PyQt && \
	mkdir -p .build && \
	cd .build && rm -f * && \
	python ../configure.py && make && \
	cd ../../../../../.. && \
	cp src/calibre/gui2/pictureflow/PyQt/.build/pictureflow.so src/calibre/plugins/ && \
	rm -rf src/calibre/gui2/pictureflow/.build rm -rf src/calibre/gui2/pictureflow/PyQt/.build


pot :
	cd src/calibre/translations && ${PYTHON} __init__.py pot

egg : all
	${PYTHON} setup.py register bdist_egg --exclude-source-files upload

