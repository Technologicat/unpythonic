#!/bin/bash
# TODO: Should probably look into pytest, but this quick hack will do for now.
let FAILS=0
for MODULE in unpythonic/*.py; do
  if [ "$MODULE" != "unpythonic/__init__.py" ]; then
    # https://misc.flogisoft.com/bash/tip_colors_and_formatting
    echo -ne "\e[32m*** Testing $MODULE ***\e[39m\n"
    python3 "$MODULE"
    if [ $? -ne 0 ]; then
      echo -ne "\e[91m*** FAIL in $MODULE ***\e[39m\n"
      # https://www.shell-tips.com/2010/06/14/performing-math-calculation-in-bash/
      let FAILS+=1
    else
      echo -ne "\e[92m*** PASS ***\e[39m\n"
    fi
    echo -ne "\n"
  fi
done

echo -ne "\e[32m*** Testing macro_extras (DANGER: against INSTALLED unpythonic) ***\e[39m\n"
cd macro_extras
for MODULE in test*.py; do
  echo -ne "\e[32m*** Running $MODULE ***\e[39m\n"
  ./macropy3 $(basename $MODULE .py)
  if [ $? -ne 0 ]; then
    echo -ne "\e[91m*** FAIL in $MODULE ***\e[39m\n"
    # https://www.shell-tips.com/2010/06/14/performing-math-calculation-in-bash/
    let FAILS+=1
  else
    echo -ne "\e[92m*** PASS ***\e[39m\n"
  fi
  echo -ne "\n"
done
cd ..

if [ $FAILS -gt 0 ]; then
      echo -ne "\e[91m*** At least one FAIL ***\e[39m\n"
else
      echo -ne "\e[92m*** ALL OK ***\e[39m\n"
fi
