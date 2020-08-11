# -*- coding: utf-8; -*-

import pickle

from ..symbol import sym, gensym

def runtests():
    # Basic idea: lightweight, human-readable, process-wide unique marker,
    # that can be quickly compared by object identity.
    assert sym("foo") is sym("foo")

    # Works even if pickled.
    foo = sym("foo")
    s = pickle.dumps(foo)
    o = pickle.loads(s)
    assert o is foo
    assert o is sym("foo")

    # str() returns the human-readable name as a string.
    print(foo)
    assert str(sym("foo")) == "foo"

    # repr() returns the source code that can be used to re-create the symbol.
    print(repr(foo))

    # Symbol interning has nothing to do with string interning.
    assert "λ" * 80 is not "λ" * 80
    assert sym("λ" * 80) is sym("λ" * 80)

    # Gensyms are uninterned symbols, useful as nonce/sentinel values.
    tabby = gensym("cat")
    scottishfold = gensym("cat")
    assert tabby is not scottishfold

    # Gensyms also survive a pickle roundtrip (this is powered by an UUID).
    s = pickle.dumps(tabby)
    o = pickle.loads(s)
    assert o is tabby
    o2 = pickle.loads(s)
    assert o2 is tabby
    print(tabby)
    print(scottishfold)
    print(repr(tabby))
    print(repr(scottishfold))

    print("All tests PASSED")

if __name__ == '__main__':
    runtests()
