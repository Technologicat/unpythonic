**Direct contributors**:

- Juha Jeronen (@Technologicat) - original author
- @aisha-w - documentation improvements

**Design inspiration from the internet**:

Dynamic assignment based on [StackOverflow answer by Jason Orendorff (2010)](https://stackoverflow.com/questions/2001138/how-to-create-dynamical-scoped-variables-in-python), used under CC-BY-SA. The threading support is original to our version.

Core idea of ``lispylet`` based on [StackOverflow answer by divs1210 (2017)](https://stackoverflow.com/a/44737147), used under the MIT license.

The trampoline implementation of ``unpythonic.tco`` takes its remarkably clean and simple approach from ``recur.tco`` in [fn.py](https://github.com/fnpy/fn.py). Our main improvements are a cleaner syntax for the client code, and the addition of the FP looping constructs. Another important source of inspiration was [tco](https://github.com/baruchel/tco) by Thomas Baruchel, for thinking about the possibilities of TCO in Python.

Core idea of ``view`` based on [StackOverflow answer by Mathieu Caroff (2018)](https://stackoverflow.com/a/53253136), used under the MIT license. Our additions include support for sequences with changing length, write support, iteration based on ``__iter__``, in-place reverse, and the abstract base classes.

Recursion cycle breaker ``fix`` based on original idea and implementation by [Matthew Might](http://matt.might.net/articles/parsing-with-derivatives/) and [Per Vognsen](https://gist.github.com/pervognsen/8dafe21038f3b513693e) (the latter linked from the [Python implementation](https://gist.github.com/pervognsen/815b208b86066f6d7a00) of the Brzozowski-derivative based language recognizer). Matthew Might's original Racket code is under [The CRAPL](http://matt.might.net/articles/crapl/); the license for Per Vognsen's Python implementation is not specified, but the file is publicly linked from Matthew Might's blog post. Our version is a redesign with kwargs support, thread safety, and TCO support.

Conditions system (`restarts`, `handlers`) based on studying the implementation of [python-cl-conditions](https://github.com/svetlyak40wt/python-cl-conditions/) by Alexander Artemenko (@svetlyak40wt), which is released under the 2-clause BSD license.

`PTYSocketProxy` based on [StackOverflow answer by gowenfawr](https://stackoverflow.com/questions/48781155/how-to-connect-inet-socket-to-pty-device-in-python).

Asynchronous exception injector (`async_raise`) is *"one of the dirtiest hacks ever seen"*, [by Federico Ficarelli for Python 3.4](https://gist.github.com/nazavode/84d1371e023bccd2301e)), and originally by [LIU Wei for Python 2.x](https://gist.github.com/liuw/2407154).
