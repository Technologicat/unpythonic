# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, error, warn, the  # noqa: F401
from ..test.fixtures import session, testset, returns_normally

import threading
from time import sleep
import sys

from ..excutil import (raisef, tryf,
                       equip_with_traceback,
                       reraise_in, reraise,
                       async_raise)
from ..env import env

def runtests():
    # raisef: raise an exception from an expression position
    with testset("raisef (raise exception from an expression)"):
        raise_instance = lambda: raisef(ValueError("all ok"))  # the argument works the same as in `raise ...`
        test_raises[ValueError, raise_instance()]
        try:
            raise_instance()
        except ValueError as err:
            test[err.__cause__ is None]  # like plain `raise ...`, no cause set (default behavior)

        # using the `cause` parameter, raisef can also perform a `raise ... from ...`
        exc = TypeError("oof")
        raise_instance = lambda: raisef(ValueError("all ok"), cause=exc)
        test_raises[ValueError, raise_instance()]
        try:
            raise_instance()
        except ValueError as err:
            test[err.__cause__ is exc]  # cause specified, like `raise ... from ...`

        # can also raise an exception class (no instance)
        test_raises[StopIteration, raisef(StopIteration)]

    # tryf: handle an exception in an expression position
    with testset("tryf (try/except/finally in an expression)"):
        raise_instance = lambda: raisef(ValueError("all ok"))
        raise_class = lambda: raisef(ValueError)

        test[tryf(lambda: "hello") == "hello"]
        test[tryf(lambda: "hello",
                  elsef=lambda: "there") == "there"]
        test[tryf(lambda: raise_instance(),
                  (ValueError, lambda: "got a ValueError")) == "got a ValueError"]
        test[tryf(lambda: raise_instance(),
                  (ValueError, lambda err: f"got a ValueError: '{err.args[0]}'")) == "got a ValueError: 'all ok'"]
        test[tryf(lambda: raise_instance(),
                  ((RuntimeError, ValueError), lambda err: f"got a RuntimeError or ValueError: '{err.args[0]}'")) == "got a RuntimeError or ValueError: 'all ok'"]
        test[tryf(lambda: "hello",
                  (ValueError, lambda: "got a ValueError"),
                  elsef=lambda: "there") == "there"]
        test[tryf(lambda: raisef(ValueError("oof")),
                  (TypeError, lambda: "got a TypeError"),
                  ((TypeError, ValueError), lambda: "got a TypeError or a ValueError"),
                  (ValueError, lambda: "got a ValueError")) == "got a TypeError or a ValueError"]

        e = env(finally_ran=False)
        test[e.finally_ran is False]
        test[tryf(lambda: "hello",
                  elsef=lambda: "there",
                  finallyf=lambda: e << ("finally_ran", True)) == "there"]
        test[e.finally_ran is True]

        test[tryf(lambda: raise_class(),
                  (ValueError, lambda: "ok")) == "ok"]
        test[tryf(lambda: raise_class(),
                  ((RuntimeError, ValueError), lambda: "ok")) == "ok"]

        test_raises[TypeError, tryf(lambda: "hello",
                                    (str, lambda: "got a string"))]  # str is not an exception type
        test_raises[TypeError, tryf(lambda: "hello",
                                    ((ValueError, str), lambda: "got a string"))]  # same, in the tuple case
        test_raises[TypeError, tryf(lambda: "hello",
                                    ("not a type at all!", lambda: "got a string"))]

    with testset("equip_with_traceback"):
        e = Exception("just testing")
        e = equip_with_traceback(e)
        test[e.__traceback__ is not None]  # Can't do meaningful testing on the result, so just check it's there.

        test_raises[TypeError, equip_with_traceback("not an exception")]

    with testset("reraise_in, reraise"):
        class LibraryException(Exception):
            pass
        class MoreSophisticatedLibraryException(LibraryException):
            pass
        class UnrelatedException(Exception):
            pass
        class ApplicationException(Exception):
            pass

        test_raises[ApplicationException, reraise_in(lambda: raisef(LibraryException),
                                                     {LibraryException: ApplicationException})]
        # subclasses
        test_raises[ApplicationException, reraise_in(lambda: raisef(MoreSophisticatedLibraryException),
                                                     {LibraryException: ApplicationException})]
        # tuple of types as input
        test_raises[ApplicationException, reraise_in(lambda: raisef(UnrelatedException),
                                                     {(LibraryException, UnrelatedException):
                                                           ApplicationException})]
        test[returns_normally(reraise_in(lambda: 42,
                                         {LibraryException: ApplicationException}))]

        with test_raises[ApplicationException]:
            with reraise({LibraryException: ApplicationException}):
                raise LibraryException
        with test_raises[ApplicationException]:
            with reraise({LibraryException: ApplicationException}):
                raise MoreSophisticatedLibraryException
        with test_raises[ApplicationException]:
            with reraise({(LibraryException, UnrelatedException): ApplicationException}):
                raise LibraryException
        with test["should return normally"]:
            with reraise({LibraryException: ApplicationException}):
                42

    # async_raise - evil ctypes hack to inject an asynchronous exception into another running thread
    if sys.implementation.name != "cpython":
        warn["async_raise only supported on CPython, skipping test."]  # pragma: no cover
    else:
        with testset("async_raise (inject KeyboardInterrupt)"):
            try:
                # Test whether the Python we're running on provides ctypes. At least CPython and PyPy3 do.
                # For PyPy3, the general rule is "if it imports, it should work", so let's go along with that.
                import ctypes  # noqa: F401
                out = []  # box, really, but let's not depend on unpythonic.collections in this unrelated unit test module
                def test_async_raise_worker():
                    try:
                        for j in range(10):
                            sleep(0.1)
                    except KeyboardInterrupt:  # normally, KeyboardInterrupt is only raised in the main thread
                        pass
                    out.append(j)
                t = threading.Thread(target=test_async_raise_worker)
                t.start()
                sleep(0.1)  # make sure we're in the while loop
                async_raise(t, KeyboardInterrupt)
                t.join()
                test[out[0] < 9]  # terminated early due to the injected KeyboardInterrupt
            except NotImplementedError:  # pragma: no cover
                error["async_raise not supported on this Python interpreter."]

            test_raises[TypeError, async_raise(42, KeyboardInterrupt)]  # not a thread

            t = threading.Thread(target=lambda: None)
            t.start()
            t.join()
            test_raises[ValueError, async_raise(t, KeyboardInterrupt)]  # thread no longer running

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
