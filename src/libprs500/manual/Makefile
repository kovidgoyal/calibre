QTDIR=/usr/local/Trolltech/Qt-4.4.0-tp1
QCG=${QTDIR}/bin/qcollectiongenerator
ASSISTANT=${QTDIR}/bin/assistant_new
LD_LIBRARY_PATH=${QTDIR}/lib

all : clean
	LD_LIBRARY_PATH=${LD_LIBRARY_PATH} ${QCG} libprs500.qhcp && \
	LD_LIBRARY_PATH=${LD_LIBRARY_PATH} ${ASSISTANT} -collectionFile libprs500.qhc &

clean :
	rm -rf *.qhc *.qch ~/.assistant/libprs500.qhc
