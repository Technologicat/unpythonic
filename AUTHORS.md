**Direct contributors**:

- Juha Jeronen (@Technologicat) - original author
- @aisha-w - documentation improvements

**Design inspiration from the internet**:

Dynamic assignment based on [StackOverflow answer by Jason Orendorff (2010)](https://stackoverflow.com/questions/2001138/how-to-create-dynamical-scoped-variables-in-python), used under CC-BY-SA. The threading support is original to our version.

Core idea of ``lispylet`` based on [StackOverflow answer by divs1210 (2017)](https://stackoverflow.com/a/44737147), used under the MIT license.

Core idea of ``view`` based on [StackOverflow answer by Mathieu Caroff (2018)](https://stackoverflow.com/a/53253136), used under the MIT license. Our additions include support for sequences with changing length, write support, iteration based on ``__iter__``, in-place reverse, and the abstract base classes.

Recursion cycle breaker ``fix`` based on original idea and implementation by [Matthew Might](http://matt.might.net/articles/parsing-with-derivatives/) and [Per Vognsen](https://gist.github.com/pervognsen/8dafe21038f3b513693e) (the latter linked from the [Python implementation](https://gist.github.com/pervognsen/815b208b86066f6d7a00) of the Brzozowski-derivative based language recognizer). Matthew Might's original Racket code is under [The CRAPL](http://matt.might.net/articles/crapl/); the license for Per Vognsen's Python implementation is not specified, but the file is publicly linked from Matthew Might's blog post. Our version is a rewrite with kwargs support and thread safety.

Conditions system (`restarts`, `handlers`) based on studying the implementation of [python-cl-conditions](https://github.com/svetlyak40wt/python-cl-conditions/) by Alexander Artemenko (@svetlyak40wt), which is released under the 2-clause BSD license.
