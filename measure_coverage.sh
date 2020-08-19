#!/bin/bash

# https://github.com/nedbat/coveragepy
# pip install coverage

# https://coverage.readthedocs.io/en/coverage-5.2.1/#quick-start

echo -ne "Measuring...\n"
coverage run --source=. -m runtests
echo -ne "Generating report...\n"
coverage html
echo -ne "Done. Open htmlcov/index.html in your browser to view.\n"
