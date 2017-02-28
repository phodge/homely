#!/usr/bin/env bash
cd docs && pandoc slides.rst -t slidy -s -o ../slides.html --template default.slidy
