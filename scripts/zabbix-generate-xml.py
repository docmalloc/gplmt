#!/usr/bin/python

import sys

templateFile = 'import.template'
if len(sys.argv) > 2:
    templateFile = sys.argv[2]

try:
    nodeFile = sys.argv[1]
except:
    print 'Usage:', sys.argv[0], '<nodes file> [template file]'
    sys.exit(2)

print '<?xml version="1.0" encoding="UTF-8"?>'
print '<hosts>'

t = open(templateFile, 'r')
template = t.read()
t.close()

f = open(nodeFile, 'r')
for node in f.readlines():
    print template.replace('[name]', node.rstrip())
f.close()

print '</hosts>'
