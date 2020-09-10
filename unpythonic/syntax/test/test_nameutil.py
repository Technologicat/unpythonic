# -*- coding: utf-8 -*-
"""Utilities for working with identifiers in macros."""

from ...syntax import macros, test
from ...test.fixtures import session, testset

from macropy.core.quotes import macros, q  # noqa: F811
from macropy.core.hquotes import macros, hq  # noqa: F811, F401

from ...syntax.nameutil import isx, make_isxpred, getname

from ast import Call

def runtests():
    with testset("isx"):
        # test data
        def capture_this():
            pass  # pragma: no cover
        barename = q[ok]  # noqa: F821
        captured = hq[capture_this()]
        attribute = q[someobj.ok]  # noqa: F821

        test[isx(barename, "ok")]
        test[type(captured) is Call]
        test[isx(captured.func, "capture_this")]
        test[isx(attribute, "ok")]
        test[not isx(attribute, "ok", accept_attr=False)]

    with testset("make_isxpred"):
        isfab = make_isxpred("fab")
        test[isx(q[fab], isfab)]  # noqa: F821
        test[isx(q[fab4], isfab)]  # noqa: F821
        test[isx(q[someobj.fab4], isfab)]  # noqa: F821

    with testset("getname"):
        test[getname(barename) == "ok"]
        test[getname(captured.func) == "capture_this"]
        test[getname(attribute) == "ok"]
        test[getname(attribute, accept_attr=False) is None]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
