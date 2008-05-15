TARGET = pictureflow.so
OFILES = sippictureflowcmodule.o sippictureflowPictureFlow.o
HFILES = sipAPIpictureflow.h 

CC = gcc
CXX = g++
LINK = g++
CPPFLAGS = -DQT_NO_DEBUG -DQT_THREAD_SUPPORT -I. -I/usr/include/python2.5 -I/usr/lib/qt-3.3/mkspecs/default -I/usr/lib/qt-3.3/include
CFLAGS = -O2 -g -pipe -Wall -Wp,-D_FORTIFY_SOURCE=2 -fexceptions -fstack-protector --param=ssp-buffer-size=4 -m32 -march=i386 -mtune=generic -fasynchronous-unwind-tables -fPIC -Wall -W -D_REENTRANT
CXXFLAGS = -O2 -g -pipe -Wall -Wp,-D_FORTIFY_SOURCE=2 -fexceptions -fstack-protector --param=ssp-buffer-size=4 -m32 -march=i386 -mtune=generic -fasynchronous-unwind-tables -fPIC -Wall -W -D_REENTRANT
LFLAGS = -shared -Wl,--version-script=pictureflow.exp
LIBS = -L.. -L/usr/lib/qt-3.3/lib -lpictureflow -lqt-mt -lXext -lX11 -lm -lpthread
MOC = /usr/lib/qt-3.3/bin/moc
.SUFFIXES: .c .o .cpp .cc .cxx .C


.cpp.o:
	$(CXX) -c $(CXXFLAGS) $(CPPFLAGS) -o $@ $<

.cc.o:
	$(CXX) -c $(CXXFLAGS) $(CPPFLAGS) -o $@ $<

.cxx.o:
	$(CXX) -c $(CXXFLAGS) $(CPPFLAGS) -o $@ $<

.C.o:
	$(CXX) -c $(CXXFLAGS) $(CPPFLAGS) -o $@ $<

.c.o:
	$(CC) -c $(CFLAGS) $(CPPFLAGS) -o $@ $<

$(TARGET): $(OFILES)
	@echo '{ global: initpictureflow; local: *; };' > pictureflow.exp
	$(LINK) $(LFLAGS) -o $(TARGET) $(OFILES) $(LIBS)

$(OFILES): $(HFILES)

install: $(TARGET)
	@test -d $(DESTDIR)/usr/lib/python2.5/site-packages || mkdir -p $(DESTDIR)/usr/lib/python2.5/site-packages
	cp -f $(TARGET) $(DESTDIR)/usr/lib/python2.5/site-packages/$(TARGET)

clean:
	-rm -f $(TARGET)
	-rm -f sippictureflowcmodule.o
	-rm -f sippictureflowPictureFlow.o
	-rm -f pictureflow.exp
