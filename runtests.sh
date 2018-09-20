#!/bin/bash
# TODO: Should probably look into pytest, but this quick hack will do for now.
for MODULE in unpythonic/*.py; do
  if [ "$MODULE" != "unpythonic/__init__.py" ]; then
    # https://misc.flogisoft.com/bash/tip_colors_and_formatting
    echo -ne "\e[32m*** Testing $MODULE ***\e[39m\n"
    python3 "$MODULE"
    if [ $? -ne 0 ]; then
      echo -ne "\e[91m*** FAIL in $MODULE ***\e[39m\n"
    else
      echo -ne "\e[92m*** PASS ***\e[39m\n"
    fi
    echo -ne "\n"
  fi
done
