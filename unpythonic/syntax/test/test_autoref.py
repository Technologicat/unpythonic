# -*- coding: utf-8 -*-
"""Implicitly reference attributes of an object."""

from ...syntax import macros, autoref

from ...env import env

def test():
    e = env(a=1, b=2)
    c = 3
    with autoref(e):
        assert a == 1  # a --> e.a
        assert b == 2  # b --> e.b
        assert c == 3  # no c in e, so just c

    print("All tests PASSED")

if __name__ == '__main__':
    test()
