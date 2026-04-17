# -*- coding: utf-8 -*-
"""Monads for unpythonic.

A monad is really just a design pattern, describable as:

- chaining of operations with custom processing between steps, or
- generalization of function composition.

The OO(F)P-ish approach taken here uses the class constructor for each
monad as its ``unit`` (in Haskell: ``return``), and spells bind as ``>>``
via ``__rshift__``. (In Python the standard Haskell bind symbol ``>>=``
maps to ``__irshift__``, which is an in-place operation that does not
chain, so we can't use that.)

The general pattern: wrap an initial value with unit, then send it
through a sequence of monadic functions using bind. Each function in the
chain must use the same type of monad for the chain to compose.

**Start here**: ``Maybe`` and ``List`` are perhaps the most important to
understand first — they're straightforward *container* monads. Move on
to ``Writer`` for another container-ish example, then ``State`` and
``Reader`` for the more mind-bending *computation* monads.

Seven monads plus the two base classes:

- ``Monad``, ``LiftableMonad`` — the base classes
- ``Identity`` — pedagogical no-op
- ``Maybe`` — simple short-circuiting on "nothing"
- ``Either``, ``Left``, ``Right`` — short-circuiting with a carried error
- ``List`` — non-deterministic / multivalued computation
- ``Writer`` — pure-functional audit log
- ``State`` — threading a state value through a pure chain
- ``Reader`` — reading from a shared immutable environment

plus:

- ``liftm``, ``liftm2``, ``liftm3`` — lift regular functions into monadic ones

The subpackage is **not** re-exported at the top level of ``unpythonic`` —
import directly as ``from unpythonic.monads import Maybe``, etc. This
matches the pattern of ``from unpythonic.env import env``.

For do-notation syntax over any of these monads, see the macro
``from unpythonic.syntax import monadic_do``.

**Approachable explanations**:

- http://blog.sigfpe.com/2006/08/you-could-have-invented-monads-and.html
- http://nikgrozev.com/2013/12/10/monads-in-15-minutes/
- https://stackoverflow.com/questions/44965/what-is-a-monad
- https://www.stephanboyer.com/post/9/monads-part-1-a-design-pattern
- https://www.stephanboyer.com/post/10/monads-part-2-impure-computations
- https://www.stephanboyer.com/post/83/super-quick-intro-to-monads
- http://learnyouahaskell.com/functors-applicative-functors-and-monoids

**Further reading — other Python monad libraries**:

- https://github.com/dbrattli/OSlash
- https://github.com/justanr/pynads
- https://bitbucket.org/jason_delaat/pymonad/
- https://github.com/dpiponi/Monad-Python
- http://www.valuedlessons.com/2008/01/monads-in-python-with-nice-syntax.html

This subpackage is ported from the teaching code at
https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/monads.py.
"""

from .abc import *  # noqa: F401, F403
from .core import *  # noqa: F401, F403

from .identity import *  # noqa: F401, F403
from .maybe import *  # noqa: F401, F403
from .either import *  # noqa: F401, F403
from .list import *  # noqa: F401, F403
from .writer import *  # noqa: F401, F403
from .state import *  # noqa: F401, F403
from .reader import *  # noqa: F401, F403
