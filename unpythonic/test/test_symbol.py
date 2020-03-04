# -*- coding: utf-8; -*-

import pickle

from ..symbol import Symbol as S

def test():
    # Basic idea: lightweight, human-readable, process-wide unique marker,
    # that can be quickly compared by object identity.
    assert S("foo") is S("foo")

    # Works even if pickled.
    foo = S("foo")
    s = pickle.dumps(foo)
    o = pickle.loads(s)
    assert o is foo
    assert o is S("foo")

    # str() returns the human-readable name as a string.
    assert str(S("foo")) == "foo"

    # Has nothing to do with string interning.
    assert "λ" * 80 is not "λ" * 80
    assert S("λ" * 80) is S("λ" * 80)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
