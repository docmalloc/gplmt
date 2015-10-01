#!/bin/bash
# Generate a XML Schema Definition (.xsd) and RELAXNG grammar (.rng)
# from the GPLMT grammar in RELAXNG compact form.
# Requires trang (http://www.thaiopensource.com/relaxng/trang.html).

pushd "$( dirname "${BASH_SOURCE[0]}" )"

trang -I rnc -O xsd gplmt.rnc gplmt.xsd
trang -I rnc -O rng gplmt.rnc gplmt.rng

popd
