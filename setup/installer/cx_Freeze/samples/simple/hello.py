import sys

print "Hello from cx_Freeze"
print

print "sys.executable", sys.executable
print "sys.prefix", sys.prefix
print

print "ARGUMENTS:"
for a in sys.argv:
    print a
print

print "PATH:"
for p in sys.path:
    print p
print

