usbobserver.so : usbobserver.o
	gcc -arch i386 -arch ppc -bundle usbobserver.o -o usbobserver.so -framework Python -framework IOKit -framework CoreFoundation

usbobserver.o : usbobserver.c
	gcc -arch i386 -arch ppc -dynamic -I/Library/Frameworks/Python.framework/Versions/2.5/include/python2.5 -c usbobserver.c -o usbobserver.o 


install : usbobserver.so
	cp usbobserver.so /Library/Frameworks/Python.framework/Versions/2.5/lib/python2.5/site-packages/

clean : 
	rm -f *.o *.so
