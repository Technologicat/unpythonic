#!/bin/bash
VERSION="$1"
twine upload dist/unpythonic-${VERSION}.tar.gz dist/unpythonic-${VERSION}-py3-none-any.whl
