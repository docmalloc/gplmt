#!/bin/bash

file=/tmp/stat-cache
expiration_time=120

if [ -f "$file" ]; then
        current=`date +%s`
        modified=`stat -c "%Y" $file`
        if [ $(($current-$modified)) -gt $expiration_time ]; then
                gnunet-statistics > $file
        fi
else
        gnunet-statistics > $file
fi

# parse file here
val=$(grep "$1 .* $2" $file | awk '{print $NF}')
if [ -z "$val" ]; then
        echo "0"
else
        echo $val
fi
