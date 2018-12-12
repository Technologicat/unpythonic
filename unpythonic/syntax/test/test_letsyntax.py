# -*- coding: utf-8 -*-
"""Local **syntactic** bindings - splice code at macro expansion time.

**CAUTION**: a toy macro system within the real macro system. Read the docstrings."""

# Look at the various examples by surrounding them "with show_expanded:"
# to see the expanded code.
#
# Note let_syntax completely goes away at macro expansion time; it just instructs
# the expander to perform some substitutions in a particular section of code.
# At runtime (after macro expansion), let_syntax has zero performance overhead.
#from macropy.tracing import macros, show_expanded

from ...syntax import macros, let_syntax, abbrev, block, expr, where

def test():
    # expression variant
    evaluations = 0
    def verylongfunctionname(x=1):
        nonlocal evaluations
        evaluations += 1
        return x
    y = let_syntax((f, verylongfunctionname))[[  # extra brackets: implicit do
                     f(),
                     f(5)]]
    assert evaluations == 2
    assert y == 5

    # haskelly syntax
    y = let_syntax[((f, verylongfunctionname))
                   in [f(),
                       f(17)]]
    assert evaluations == 4
    assert y == 17

    y = let_syntax[[f(),
                    f(23)],
              where((f, verylongfunctionname))]
    assert evaluations == 6
    assert y == 23

    # templates
    #   - positional parameters only, no default values
    y = let_syntax((f(a), verylongfunctionname(2*a)))[[
                     f(2),
                     f(3)]]
    assert evaluations == 8
    assert y == 6

    # block variant
    with let_syntax:
        with block as make123:  # capture one or more statements
            lst = []
            lst.append(1)
            lst.append(2)
            lst.append(3)
        make123
        try:
            assert snd == 2
        except NameError:
            pass  # "snd" not defined yet
        else:
            assert False, "snd should not be defined yet"
        assert lst == [1, 2, 3]
        with expr as snd:  # capture a single expression
            lst[1]
        assert snd == 2
        with block as make456:
            lst = []
            lst.append(4)
            lst.append(5)
            lst.append(6)
        if 42 % 2 == 0:
            make456
        else:
            make123
        assert lst == [4, 5, 6]
        assert snd == 5

    with let_syntax:
        with block(a, b, c) as makeabc:  # block template - parameters are expressions
            lst = [a, b, c]
        makeabc(3 + 4, 2**3, 3 * 3)
        assert lst == [7, 8, 9]
        with expr(n) as nth:  # single-expression template
            lst[n]
        assert nth(2) == 9

    # blocks may refer to ones defined previously in the same let_syntax
    with let_syntax:
        lst = []
        with block as append123:
            lst += [1, 2, 3]
        with block as maketwo123s:
            append123
            append123
        maketwo123s
        assert lst == [1, 2, 3]*2

    # lexical scoping
    with let_syntax:
        with block as makelst:
            lst = [1, 2, 3]
        with let_syntax:
            with block as makelst:
                lst = [4, 5, 6]
            makelst
            assert lst == [4, 5, 6]
        makelst
        assert lst == [1, 2, 3]

    # even in block templates, parameters are always expressions
    #   - but there's a trick: names and calls are expressions
    #     - ...so a parameter can refer to a previously defined substitution
    #   - definition order is important!
    #     - all template substitutions are applied before any barename substitutions
    #     - within each kind (template, barename), substitutions are applied
    #       in the same order they are defined
    with let_syntax:
        # barenames (no parameters)
        with block as append123:
            lst += [1, 2, 3]
        with block as append456:
            lst += [4, 5, 6]
        # template - applied before any barenames
        with block(a) as twice:
            a
            a
        lst = []
        twice(append123)  # name of a barename substitution as a parameter
        assert lst == [1, 2, 3]*2
        lst = []
        twice(append456)
        assert lst == [4, 5, 6]*2

    with let_syntax:
        # in this example, both substitutions are templates, so they must be
        # defined in the same order they are meant to be applied.
        with block(a) as twice:
            a
            a
        with block(x, y, z) as appendxyz:
            lst += [x, y, z]
        lst = []
        # template substitution invoked in a parameter
        twice(appendxyz(7, 8, 9))  # a call is an expression, so as long as not yet expanded, this is ok
        assert lst == [7, 8, 9]*2

    # abbrev: like let_syntax, but expands in the first pass, outside in
    #   - no lexically scoped nesting
    #   - but can locally rename also macros (since abbrev itself expands before its body)
    y = abbrev((f, verylongfunctionname))[[
                 f(),
                 f(5)]]
    assert y == 5

    # haskelly syntax
    y = abbrev[((f, verylongfunctionname))
               in [f(),
                   f(17)]]
    assert y == 17

    y = abbrev[[f(),
                f(23)],
          where((f, verylongfunctionname))]
    assert y == 23

    # in abbrev, outer expands first, so in the assert,
    #     f -> longishname -> verylongfunctionname
    with abbrev:
        with expr as f:
            longishname
        with abbrev:
            with expr as longishname:
                verylongfunctionname
            assert f(10) == 10

    print("All tests PASSED")
