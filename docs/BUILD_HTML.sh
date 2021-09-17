#!/bin/bash

rm -r _build

sphinx-build . _build/html

xdg-open _build/html/index.html

echo `basename $0`

read
