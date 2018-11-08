#!/bin/bash
# TODO: Should probably look into pytest, but this quick hack will do for now.
let FAILS=0
for FILE in unpythonic/test/*.py; do
  # https://misc.flogisoft.com/bash/tip_colors_and_formatting
  echo -ne "\e[32m*** Testing $FILE ***\e[39m\n"
  # https://superuser.com/questions/731227/how-to-extract-the-filename-without-the-extension-from-a-full-path
  MODULE=$(echo ${FILE%.py} | sed -e 's!/!.!g;')
  python3 -m "$MODULE"
  if [ $? -ne 0 ]; then
    echo -ne "\e[91m*** FAIL in $FILE ***\e[39m\n"
    # https://www.shell-tips.com/2010/06/14/performing-math-calculation-in-bash/
    let FAILS+=1
  else
    echo -ne "\e[92m*** PASS ***\e[39m\n"
  fi
  echo -ne "\n"
done

echo -ne "\e[32m*** Testing macro_extras (DANGER: against INSTALLED unpythonic) ***\e[39m\n"
cd macro_extras
for FILE in test*.py; do
  echo -ne "\e[32m*** Running $FILE ***\e[39m\n"
  ./macropy3 $(basename $FILE .py)
  if [ $? -ne 0 ]; then
    echo -ne "\e[91m*** FAIL in $FILE ***\e[39m\n"
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
