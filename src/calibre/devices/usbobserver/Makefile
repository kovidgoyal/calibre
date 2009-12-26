usbobserver.so : usbobserver.o
	gcc -arch i386 -arch ppc -bundle usbobserver.o -o usbobserver.so -framework Python -framework IOKit -framework CoreFoundation

usbobserver.o : usbobserver.c
	gcc -arch i386 -arch ppc -dynamic -I/Library/Frameworks/Python.framework/Versions/Current/Headers -c usbobserver.c -o usbobserver.o 

clean : 
	rm -f *.o *.so
