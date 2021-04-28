# -*- coding: utf-8 -*-
"""Simple let construct with real lexical variables, no assignment."""

from ...syntax import macros, test  # noqa: F401
from ...test.fixtures import session, testset

from ...syntax.simplelet import macros, let, letseq  # noqa: F401, F811

def runtests():
    with testset("let"):
        test[let[[x, 21]][2 * x] == 42]  # noqa: F821, the `let` defines `x`.
        test[let[[x, 21], [y, 2]][y * x] == 42]  # noqa: F821

    with testset("letseq"):
        test[letseq[[x, 1]][2 * x] == 2]  # noqa: F821
        test[letseq[[x, 1],  # noqa: F821
                    [x, 2 * x]][2 * x] == 4]  # noqa: F821

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
