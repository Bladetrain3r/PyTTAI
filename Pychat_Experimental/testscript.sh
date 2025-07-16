#!/bin/bash
find . -type f | grep -v "__pycache__" > list.txt
while read -r file; do
    if [[ -f "$file" ]]; then
        echo "Processing $file"
        # Add your processing commands here
        cp $file "temp.txt"
        python3 main.py -a -c test.pyt > $file.explain
    else
        echo "$file is not a regular file, skipping."
    fi
done < list.txt
