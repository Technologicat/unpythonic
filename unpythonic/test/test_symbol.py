# -*- coding: utf-8; -*-

from ..syntax import macros, test, the  # noqa: F401
from .fixtures import session, testset

import pickle
import threading
from queue import Queue
import gc

from ..symbol import sym, gensym
from ..misc import slurp
from ..it import allsame

def runtests():
    # Basic idea: lightweight, human-readable, process-wide unique marker,
    # that can be quickly compared by object identity.
    with testset("sym (interned symbol)"):
        test[the[sym("foo") is sym("foo")]]

        # Works even if pickled.
        foo = sym("foo")
        s = pickle.dumps(foo)
        o = pickle.loads(s)
        test[the[o is foo]]
        test[the[o is sym("foo")]]

        # str() returns the human-readable name as a string.
        test[str(sym("foo")) == "foo"]

        # repr() returns the source code that can be used to re-create the symbol.
        test[the[eval(repr(foo))] is the[foo]]

        # Symbol interning has nothing to do with string interning.
        many = 5000
        test[the[sym("λ" * many) is sym("λ" * many)]]
        # To defeat string interning, used to be that 80 exotic characters
        # would be enough in Python 3.6 to make CPython decide not to intern it,
        # but Python 3.7 bumped that up.
        test[the["λ" * many is not "λ" * many]]

    with testset("sym thread safety"):
        with test:  # just interested that it runs to completion
            que = Queue()
            def worker():
                que.put(sym("hello world"))
            n = 1000
            threads = [threading.Thread(target=worker) for _ in range(n)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            lst = slurp(que)
            test[the[len(lst)] == the[n]]
            test[allsame(lst)]

    with testset("gensym (uninterned symbol, nonce value)"):
        # Gensyms are uninterned symbols, useful as nonce/sentinel values.
        #
        # This has nothing to do with MacroPy's `gen_sym`, which picks a
        # locally unused name for a new identifier.
        tabby = gensym("cat")
        scottishfold = gensym("cat")
        test[the[tabby] is not the[scottishfold]]

        # Gensyms also survive a pickle roundtrip (this is powered by an UUID).
        s = pickle.dumps(tabby)
        o = pickle.loads(s)
        test[the[o is tabby]]
        o2 = pickle.loads(s)
        test[the[o2 is tabby]]
        print(tabby)
        print(scottishfold)
        print(repr(tabby))
        print(repr(scottishfold))

    with testset("gensym thread safety"):
        # TODO: These must be outside the `with test` because a test block
        # implicitly creates a function (whence a local scope).
        g = gensym("hello")
        s = pickle.dumps(g)
        del g  # blammo. Due to the gensym registry being a weakref, it should really be gone.
        gc.collect()  # PyPy3
        with test:  # just interested that it runs to completion
            que = Queue()
            def worker():
                que.put(pickle.loads(s))
            n = 1000
            threads = [threading.Thread(target=worker) for _ in range(n)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            lst = slurp(que)
            test[the[len(lst)] == the[n]]
            test[allsame(lst)]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
