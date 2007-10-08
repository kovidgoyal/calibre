all : gui2

clean : 
	${MAKE} -C src/libprs500/gui2 clean

gui2 :
	${MAKE} -C src/libprs500/gui2
