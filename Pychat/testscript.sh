#!/bin/bash
[ -d temp ] || mkdir temp
find . -type f | grep -v "__pycache__" | grep -v "config.json" | grep -v "*.explain"> list.txt
while read -r file; do
    if [[ -f "$file" ]]; then
        echo "Processing $file"
        # Add your processing commands here
        explainfile=$(basename "$file").explain
        cp $file "temp.txt"
        python3 main.py -a -c test.ptt > ./temp/$explainfile
    else
        echo "$file is not a regular file, skipping."
    fi
done < list.txt

echo '' > output.txt
find ./temp -type f -name "*.explain" -exec sh -c 'echo "File: {}"; cat {}' \; >> output.txt
rm list.txt
rm temp.txt
find . -type f -name "*.explain" -delete

python3 main.py -a -c "/file output.txt Summarize this application based on the explanations in this file. Keep it reasonably brief." > final_summary.txt
echo "Final summary saved to final_summary.txt"
