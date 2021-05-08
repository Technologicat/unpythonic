# -*- coding: utf-8 -*-
"""Local **syntactic** bindings - splice code at macro expansion time.

**CAUTION**: a toy macro system within the real macro system. Read the docstrings."""

# Look at the various examples by surrounding them "with step_expansion:"
# to see the expanded code.
#
# from mcpyrate.debug import macros, step_expansion  # noqa: F401
#
# Note let_syntax completely goes away at macro expansion time; it just instructs
# the expander to perform some substitutions in a particular section of code.
# At runtime (after macro expansion), let_syntax has zero performance overhead.

from ...syntax import macros, test, test_raises  # noqa: F401
from ...test.fixtures import session, testset

from ...syntax import macros, let_syntax, abbrev, block, expr  # noqa: F401, F811
from ...syntax import where

def runtests():
    with testset("expression variant"):
        evaluations = 0
        def verylongfunctionname(x=1):
            nonlocal evaluations
            evaluations += 1
            return x
        y = let_syntax(f << verylongfunctionname)[[  # extra brackets: implicit do  # noqa: F821, `let_syntax` defines `f` here.
                         f(),  # noqa: F821
                         f(5)]]  # noqa: F821
        test[evaluations == 2]
        test[y == 5]

        # haskelly syntax
        y = let_syntax[[f << verylongfunctionname]  # noqa: F821
                       in [f(),  # noqa: F821
                           f(17)]]  # noqa: F821
        test[evaluations == 4]
        test[y == 17]

        y = let_syntax[[f(),  # noqa: F821
                        f(23)],  # noqa: F821
                       where[f << verylongfunctionname]]  # noqa: F821
        test[evaluations == 6]
        test[y == 23]

        # templates
        #   - positional parameters only, no default values
        # TODO: updating this to use bracket syntax requires changes to `_destructure_and_apply_let`.
        y = let_syntax(f[a] << verylongfunctionname(2 * a))[[  # noqa: F821
                         f[2],  # noqa: F821
                         f[3]]]  # noqa: F821
        test[evaluations == 8]
        test[y == 6]

        # Renaming via let_syntax also affects attributes
        class Silly:
            realthing = 42
        # This test will either pass, or error out with an AttributeError.
        test[let_syntax[[alias << realthing] in Silly.alias] == 42]  # noqa: F821

    with testset("block variant"):
        with let_syntax:
            with block as make123:  # capture one or more statements
                lst = []
                lst.append(1)
                lst.append(2)
                lst.append(3)
            make123
            test_raises[NameError,
                        snd == 2,  # noqa: F821, `snd` being undefined is the point of this test.
                        "snd should not be defined yet"]
            test[lst == [1, 2, 3]]
            with expr as snd:  # capture a single expression
                lst[1]
            test[snd == 2]
            with block as make456:
                lst = []
                lst.append(4)
                lst.append(5)
                lst.append(6)
            if 42 % 2 == 0:
                make456
            else:
                make123
            test[lst == [4, 5, 6]]
            test[snd == 5]

        with let_syntax:
            with block[a, b, c] as makeabc:  # block template - parameters are expressions  # noqa: F821, `let_syntax` defines `a`, `b`, `c` when we call `makeabc`.
                lst = [a, b, c]  # noqa: F821
            makeabc(3 + 4, 2**3, 3 * 3)
            test[lst == [7, 8, 9]]
            with expr[n] as nth:  # single-expression template  # noqa: F821, `let_syntax` defines `n` when we call `nth`.
                lst[n]  # noqa: F821
            test[nth(2) == 9]

        # blocks may refer to ones defined previously in the same let_syntax
        with let_syntax:
            lst = []
            with block as append123:
                lst += [1, 2, 3]
            with block as maketwo123s:
                append123
                append123
            maketwo123s
            test[lst == [1, 2, 3] * 2]

        # Renaming via let_syntax also affects names of class and function definitions
        with let_syntax:
            # when the identifier "alias" is encountered, change it to "realthing"
            with expr as alias:
                realthing  # noqa: F821
            with expr as Alias:
                Realthing  # noqa: F821
            class Alias:
                x = 42
            def alias():
                return 42
            # These tests will either pass, or error out with a NameError.
            test[realthing() == 42]  # noqa: F821
            test[Realthing.x == 42]  # noqa: F821

    with testset("lexical scoping"):
        with let_syntax:
            with block as makelst:
                lst = [1, 2, 3]
            with let_syntax:
                with block as makelst:
                    lst = [4, 5, 6]
                makelst
                test[lst == [4, 5, 6]]
            makelst
            test[lst == [1, 2, 3]]

    with testset("block variant with templates"):
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
            with block[a] as twice:  # noqa: F821
                a  # noqa: F821
                a  # noqa: F821
            lst = []
            twice(append123)  # name of a barename substitution as a parameter
            test[lst == [1, 2, 3] * 2]
            lst = []
            twice(append456)
            test[lst == [4, 5, 6] * 2]

        with let_syntax:
            # in this example, both substitutions are templates, so they must be
            # defined in the same order they are meant to be applied.
            with block[a] as twice:  # noqa: F821
                a  # noqa: F821
                a  # noqa: F821
            with block[x, y, z] as appendxyz:  # noqa: F821
                lst += [x, y, z]  # noqa: F821
            lst = []
            # template substitution invoked in a parameter
            twice(appendxyz(7, 8, 9))  # a call is an expression, so as long as not yet expanded, this is ok
            test[lst == [7, 8, 9] * 2]

    with testset("abbrev (outside-in let_syntax)"):
        # abbrev: like let_syntax, but expands outside-in
        #   - no lexically scoped nesting
        #   - but can locally rename also macros (since abbrev itself expands before its body)
        y = abbrev((f, verylongfunctionname))[[  # noqa: F821
                     f(),  # noqa: F821
                     f(5)]]  # noqa: F821
        test[y == 5]

        # haskelly syntax
        y = abbrev[[f << verylongfunctionname]  # noqa: F821
                   in [f(),  # noqa: F821
                       f(17)]]  # noqa: F821
        test[y == 17]

        y = abbrev[[f(),  # noqa: F821
                    f(23)],  # noqa: F821
                   where[f << verylongfunctionname]]  # noqa: F821
        test[y == 23]

        # in abbrev, outer expands first, so in the test,
        #     f -> longishname -> verylongfunctionname
        with abbrev:
            with expr as f:
                longishname  # noqa: F821
            with abbrev:
                with expr as longishname:  # noqa: F841
                    verylongfunctionname
                test[f(10) == 10]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
