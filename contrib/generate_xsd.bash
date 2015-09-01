#!/bin/bash
# Generate XML Schema Definitions from RELAXNG compact form files with trang.

trang -I rnc -O xsd gplmt.rnc gplmt.xsd
