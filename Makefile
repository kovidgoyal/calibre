PYTHON = python

all : gui2 translations resources pictureflow

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
	mkdir -p plugins && rm -f plugins/*pictureflow* && \
	cd src/calibre/gui2/pictureflow && \
	mkdir -p .build && cd .build && rm -f * && \
	qmake ../pictureflow-lib.pro && make && \
	cd ../PyQt && \
	mkdir -p .build && \
	cd .build && rm -f * && \
	python ../configure.py && make && \
	cd ../../../../../.. && \
	cp src/calibre/gui2/pictureflow/.build/libpictureflow.so.?.?.? src/calibre/gui2/pictureflow/PyQt/.build/pictureflow.so plugins/ && \
	python -c "import os, glob; lp = glob.glob('plugins/libpictureflow.so.*')[0]; os.rename(lp, lp[:-4])"


