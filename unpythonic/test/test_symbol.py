# -*- coding: utf-8; -*-

import pickle

from ..symbol import sym, gensym

def test():
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
    assert str(sym("foo")) == "foo"

    # Has nothing to do with string interning.
    assert "λ" * 80 is not "λ" * 80
    assert sym("λ" * 80) is sym("λ" * 80)

    tabby = gensym("cat")
    scottishfold = gensym("cat")
    assert tabby is not scottishfold
    print(tabby)         # cat-gensym0
    print(scottishfold)  # cat-gensym1

    print("All tests PASSED")

if __name__ == '__main__':
    test()
