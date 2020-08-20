# -*- coding: utf-8; -*-

from ..syntax import macros, test  # noqa: F401
from .fixtures import session, testset

import pickle

from ..symbol import sym, gensym

def runtests():
    # Basic idea: lightweight, human-readable, process-wide unique marker,
    # that can be quickly compared by object identity.
    with testset("sym (interned symbol)"):
        test[sym("foo") is sym("foo")]

        # Works even if pickled.
        foo = sym("foo")
        s = pickle.dumps(foo)
        o = pickle.loads(s)
        test[o is foo]
        test[o is sym("foo")]

        # str() returns the human-readable name as a string.
        test[str(sym("foo")) == "foo"]

        # repr() returns the source code that can be used to re-create the symbol.
        test[eval(repr(foo)) is foo]

        # Symbol interning has nothing to do with string interning.
        test["λ" * 80 is not "λ" * 80]
        test[sym("λ" * 80) is sym("λ" * 80)]

    with testset("gensym (uninterned symbol, nonce value)"):
        # Gensyms are uninterned symbols, useful as nonce/sentinel values.
        tabby = gensym("cat")
        scottishfold = gensym("cat")
        test[tabby is not scottishfold]

        # Gensyms also survive a pickle roundtrip (this is powered by an UUID).
        s = pickle.dumps(tabby)
        o = pickle.loads(s)
        test[o is tabby]
        o2 = pickle.loads(s)
        test[o2 is tabby]
        print(tabby)
        print(scottishfold)
        print(repr(tabby))
        print(repr(scottishfold))

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
