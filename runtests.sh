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
./macropy3 main
if [ $? -ne 0 ]; then
  echo -ne "\e[91m*** FAIL in macro_extras ***\e[39m\n"
  let FAILS+=1
else
  echo -ne "\e[92m*** PASS ***\e[39m\n"
fi
cd ..

if [ $FAILS -gt 0 ]; then
      echo -ne "\e[91m*** At least one FAIL ***\e[39m\n"
else
      echo -ne "\e[92m*** ALL OK ***\e[39m\n"
fi

