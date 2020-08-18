# -*- coding: utf-8 -*-
"""Test exotic program topologies.

For pictures, see ``doc/callcc_topology.pdf`` in the source distribution.
"""

from ...syntax import macros, test  # noqa: F401
from ...test.fixtures import testset

from inspect import stack

from ...syntax import macros, continuations, call_cc  # noqa: F401, F811

def me():
    """Return the caller's function name."""
    callstack = stack()
    framerecord = callstack[1]  # ignore me() itself, get caller's record
    return framerecord[3]       # function name

def runtests():
    with testset("unpythonic.syntax.continuations (exotic program topologies)"):
        with testset("basic case: one continuation"):
            with continuations:
                out = []
                def g(cc):
                    out.append(me())
                def f():
                    out.append(me())
                    call_cc[g()]
                    out.append(me())
                f()
                test[out == ['f', 'g', 'f_cont']]

        with testset("sequence of continuations"):
            with continuations:
                out = []
                def g(cc):  # noqa: F811, the previous one is no longer used.
                    out.append(me())
                def h(cc):
                    out.append(me())
                def f():
                    out.append(me())
                    call_cc[g()]
                    out.append(me())
                    call_cc[h()]
                    out.append(me())
                f()
                test[out == ['f', 'g', 'f_cont1', 'h', 'f_cont2']]  # gensym -> cont1, ...

        with testset("nested continuations, case 1"):  # left in the picture
            with continuations:
                out = []
                def h(cc):  # noqa: F811, the previous one is no longer used.
                    out.append(me())
                def g(cc):  # noqa: F811, the previous one is no longer used.
                    out.append(me())
                    call_cc[h()]
                    out.append(me())
                def f():
                    out.append(me())
                    call_cc[g()]
                    out.append(me())
                f()
                test[out == ['f', 'g', 'h', 'g_cont', 'f_cont3']]

        with testset("nested continuations, case 2a, tail-call in f1"):  # right in the picture
            with continuations:
                out = []
                def w(cc):
                    out.append(me())
                def v():
                    out.append(me())
                    call_cc[w()]
                    out.append(me())
                def f1(cc):
                    out.append(me())
                    return v()
                # To be eligible to act as a continuation, f2 must accept
                # one positional arg, because the implicit "return None" in v()
                # will send one (then passed along by f1).
                def f2(dummy):
                    out.append(me())
                f1(cc=f2)
                test[out == ['f1', 'v', 'w', 'v_cont', 'f2']]

        with testset("nested continuations, case 2b, call_cc in f1"):
            with continuations:
                out = []
                def w(cc):  # noqa: F811, the previous one is no longer used.
                    out.append(me())
                def v(cc):  # noqa: F811, the previous one is no longer used.
                    out.append(me())
                    call_cc[w()]
                    out.append(me())
                def f1(cc):
                    out.append(me())
                    call_cc[v()]
                    out.append(me())
                def f2(dummy):
                    out.append(me())
                f1(cc=f2)
                test[out == ['f1', 'v', 'w', 'v_cont1', 'f1_cont', 'f2']]

        # preparation for confetti, create a saved chain
        with continuations:
            out = []
            k = None
            def h(cc):  # noqa: F811, the previous one is no longer used.
                nonlocal k
                k = cc
                out.append(me())
            def g(cc):  # noqa: F811, the previous one is no longer used.
                out.append(me())
                call_cc[h()]
                out.append(me())  # g_cont1
            def f():
                out.append(me())
                call_cc[g()]
                out.append(me())  # f_cont4
            f()

        with testset("confetti 1a - call_cc'ing into a saved continuation"):
            with continuations:
                out = []
                def v():  # noqa: F811, the previous one is no longer used.
                    out.append(me())
                    call_cc[k()]
                    out.append(me())
                v()
                test[out == ['v', 'g_cont1', 'f_cont4', 'v_cont2']]

        with testset("confetti 1b - tail-calling a saved continuation"):
            with continuations:
                out = []
                def f2(dummy):
                    out.append(me())
                def f1():
                    out.append(me())
                    return k(cc=f2)
                f1()
                test[out == ['f1', 'g_cont1', 'f_cont4', 'f2']]

        # more preparation for confetti
        with continuations:
            out = []
            k2 = None
            def t(cc):
                nonlocal k2
                k2 = cc
                out.append(me())
            def s(cc):
                out.append(me())
                call_cc[t()]
                out.append(me())  # s_cont
            def r():
                out.append(me())
                call_cc[s()]
                out.append(me())  # r_cont
            r()

            out = []
            k3 = None
            def qq(cc):
                nonlocal k3
                k3 = cc
                out.append(me())
            def q(cc):
                out.append(me())
                call_cc[qq()]
                out.append(me())  # q_cont
            def p():
                out.append(me())
                call_cc[q()]
                out.append(me())  # p_cont
                return k2()
            p()

        with testset("confetti 2a"):  # second picture from bottom
            with continuations:
                out = []
                def f2(dummy):
                    out.append(me())
                def f1():
                    out.append(me())
                    return k3(cc=f2)
                f1()
                test[out == ['f1', 'q_cont', 'p_cont', 's_cont', 'r_cont', 'f2']]

        # more preparation for confetti
        with continuations:
            out = []
            k4 = None
            def z(cc):
                nonlocal k4
                k4 = cc
                out.append(me())
            def y(cc):
                out.append(me())
                call_cc[z()]
                out.append(me())  # y_cont
                return k2()
            def x():
                out.append(me())
                call_cc[y()]
                out.append(me())  # x_cont
            x()

        with testset("confetti 2b"):  # bottommost picture
            with continuations:
                out = []
                def f2(dummy):
                    out.append(me())
                def f1():
                    out.append(me())
                    return k4(cc=f2)
                f1()
                test[out == ['f1', 'y_cont', 's_cont', 'r_cont', 'x_cont', 'f2']]

if __name__ == '__main__':
    runtests()
