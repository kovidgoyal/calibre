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
	cd src/calibre && ${PYTHON} translations/__init__.py

resources:	
	${PYTHON} resources.py
    
manual:
	make -C src/calibre/manual clean html

pictureflow :
	mkdir -p src/calibre/plugins && rm -f src/calibre/plugins/*pictureflow* && \
	cd src/calibre/gui2/pictureflow && rm -f *.o *.so* && \
	mkdir -p .build && cd .build && rm -f * && \
	qmake ../pictureflow-lib.pro && make && \
	cd ../PyQt && \
	mkdir -p .build && \
	cd .build && rm -f * && \
	python ../configure.py && make && \
	cd ../../../../../.. && \
	cp src/calibre/gui2/pictureflow/libpictureflow.so.?.?.? src/calibre/gui2/pictureflow/PyQt/.build/pictureflow.so src/calibre/plugins/ && \
	python -c "import os, glob; lp = glob.glob('src/calibre/plugins/libpictureflow.so.*')[0]; os.rename(lp, lp[:-4])"


