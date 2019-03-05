# -*- coding: utf-8 -*-
"""Importer for Python dialects.

Pydialect: make Python into a language platform, à la Racket; in Python, create
dialects that compile into Python.

**Using dialects**

Place a *lang-import* at the start of your module::

    from __lang__ import piethon

and run your main program (in this example written in the ``piethon`` dialect)
through the ``pydialect`` bootstrapper instead of ``python3`` directly.
Any imported module that has a lang-import will be detected, and the appropriate
dialect module (if and when found) will be invoked.

The lang-import must appear as the first statement of the module; only the module
docstring is allowed to appear before it. This is to make it explicit that a
dialect applies to the whole module.

The lang-import is a customization added by the dialect machinery. This ensures
that the module will immediately fail if run by standard Python (because there
is no actual module named ``__lang__``). This syntax was chosen as a close
pythonic equivalent for Racket's ``#lang foo``.

If you intend to use MacroPy, the Pydialect import hook must be installed after
``import macropy.activate``. The ``pydialect`` bootstrapper takes care of this.

The dialect importer replaces the lang-import with an assignment statement that
sets the ``__lang__`` magic variable to the dialect name, for introspection.
(If ``__lang__`` is missing, the module does not use a dialect, i.e. it was
written in standard Python.)

**Pydialect API**

In Pydialect, a dialect is any module that exports one or both of the following
callables:

    source_transformer: callable: source text -> source text

        The full source code of the module being imported (*including*
        the lang-import) is sent to the the source transformer.

        Source transformers are useful e.g. for defining custom infix
        operators. For example, the monadic bind syntax ``a >>= b``
        could be made to transform into the syntax ``a.__mbind__(b)``.

        Although the input is text, in practice a token-based approach is
        recommended; see stdlib's ``tokenize`` module as a base to work from.
        (Be sure to untokenize when done, because the next stage expects text.)

        **After the source transformer**, the source text must be valid
        surface syntax for **standard Python**, i.e. valid input for
        ``ast.parse``.

    ast_transformer: callable: Python AST -> Python AST

        After the source transformer, but before macro expansion, the full AST
        of the module being imported (*minus* the lang-import, which is converted
        at this stage to set the ``__lang__`` magic variable instead) is sent
        to this whole-module AST transformer.

        This allows injecting implicit imports to create builtins for the
        dialect, as well as e.g. placing the whole module inside a ``with``
        block to apply some MacroPy block macro(s) to the whole module.

        **After the AST transformer**, the module is sent to MacroPy for
        macro expansion (if MacroPy is installed, and the module has macros
        at that point), and after that, the result is imported normally.

**The name** of a dialect is simply the *fully qualified name* of the module
or package implementing the dialect. In other words, it's the name that needs
to be imported to find the transformer functions. For example ``piethon``, or
``mylibrary.mylanguage``.

A dialect can be implemented in another dialect, as long as there are no
dependency loops. *Whenever* a lang-import is detected, the dialect importer
is applied (especially, also during the import of a module that defines a
new dialect).

**Implementing a dialect**

A dialect can do anything from simply adding a monadic bind operator syntax,
to completely changing Python's semantics, e.g. by adding automatic tail-call
optimization, continuations, and/or lazy functions. The only limitation is that
the desired functionality must be macro-expressible in Python.

The core of a dialect is defined as a set of functions and macros, which typically
live inside a library. The role of a dialect is to package that core functionality
into a whole that can be concisely loaded with a single import.

Typically a dialect implicitly imports its core functions and macros, to make
them appear as builtins (in the sense of *implicitly defined by default*)
to modules that are written in the dialect.

A dialect may also define non-core functions and macros that live in the same
library; those essentially comprise *the standard library* of the dialect.

(For example, the ``lispython`` dialect itself is defined by a subset of
``unpythonic`` and ``unpythonic.syntax``; the rest of the library is available
to be imported manually; it makes up the standard library of ``lispython``.)

For macros, Pydialect supports MacroPy. Technically, macros are optional,
so Pydialect's dependency on MacroPy is strictly speaking optional.
Pydialect already defines a hook for a full-module AST transform;
if that (and/or a source transform) is all you need, there's no need
to have your dialect depend on MacroPy.

However, where MacroPy shines is its infrastructure. It provides a uniform
syntax to direct AST transformations to apply to particular expressions or
blocks in the user code, and it provides a hygienic quasiquote system, which
is absolutely essential for avoiding name conflicts (identifier capture,
free variable injection). It's also good at fixing missing location info for
macro-generated AST nodes, which is extremely useful since in Python the location
info is compulsory.

Since you're reading this, you probably already know, but be aware that, unlike
how it was envisioned during the *extensible languages* movement in the 1970s,
language extension is hardly an exercise requiring only "moderate amounts of labor
by unsophisticated users". Especially the interaction between different macros
needs a lot of thought, and as the number of language features grows, the
complexity skyrockets. (For an example, look at what hoops other parts of
``unpythonic`` must jump through to make ``lazify`` happy.)

Also, Python is a notoriously irregular language, so it is likely harder to extend
than a Lisp. Be prepared for some head-scratching, especially when dealing with
function call arguments, assignments and the two different kinds of function
definitions (def and lambda - one of which supports the full Python language
while the other is limited to the expression sublanguage). Green Tree Snakes
(the missing AST docs) is a highly useful resource here.

**Combining dialects**

*Dangerous things should be difficult to do _by accident_.* --John Shutt

Due to the potentially unlimited complexity of interactions between language
features defined by different dialects, there is *by design* no automation for
combining dialects. In the general case, this is something that requires human
intervention.

If you know (or at least suspect) that two or more dialects are compatible,
you can define a new dialect whose ``source_transformer`` and ``ast_transformer``
simply chain those of the existing dialects (in the desired order; consider how
the macros expand), and then use that dialect.

**Notes**

Based on ``core/import_hooks.py`` in MacroPy 1.1.0b2 and then heavily customized.

In the Lisp community, surface syntax transformations are known as *reader macros*
(although technically it's something done at the parsing step, unrelated to
syntactic macros).

Further reading:

    http://stupidpythonideas.blogspot.com/2015/06/hacking-python-without-hacking-python.html
    http://stupidpythonideas.blogspot.com/2015/05/operator-sectioning-for-python.html
    http://www.robots.ox.ac.uk/~bradley/blog/2017/12/loader-finder-python.html
    https://greentreesnakes.readthedocs.io/en/latest/nodes.html
"""

import ast
import importlib
from importlib.util import spec_from_loader
import logging
import sys
import re

try:
    import macropy.core
except ImportError:
    macropy = None

logger = logging.getLogger(__name__)

# This is essentially a copy of ``macropy.core.MacroLoader``, copied to make sure
# that the implementation won't go out of sync with our ``DialectFinder``.
# The export machinery has been removed as unnecessary for language experimentation;
# but is trivial to add back if needed (see the sources of MacroPy 1.1.0b2).
class DialectLoader:
    def __init__(self, nomacro_spec, code, tree):
        self.nomacro_spec = nomacro_spec
        self.code = code
        self.tree = tree

    def create_module(self, spec):
        pass

    def exec_module(self, module):
        exec(self.code, module.__dict__)

    def get_filename(self, fullname):
        return self.nomacro_spec.loader.get_filename(fullname)

    def is_package(self, fullname):
        return self.nomacro_spec.loader.is_package(fullname)

def singleton(cls):
    return cls()

# Like MacroPy's MacroFinder:
#
# - This is a meta_path finder, because we're looking for nonstandard things
#   inside standard-ish Python modules that can be found/loaded using the
#   standard mechanisms.
#
# - Macro expansion is performed already at the finder step, because in order to
#   detect whether to use the macro loader, the input must be parsed and scanned
#   for macros.

@singleton
class DialectFinder:
    """Importer that matches 'from __lang__ import xxx'."""

    def _find_spec_nomacro(self, fullname, path, target=None):
        """Try to find the original, non macro-expanded module using all the
        remaining meta_path finders (except MacroPy's, to avoid handling
        macros twice).
        """
        spec = None
        for finder in sys.meta_path:
            # when testing with pytest, it installs a finder that for
            # some yet unknown reasons makes macros expansion
            # fail. For now it will just avoid using it and pass to
            # the next one
            if finder is self or (macropy and finder is macropy.core.MacroFinder) or \
               'pytest' in finder.__module__:
                continue
            if hasattr(finder, 'find_spec'):
                spec = finder.find_spec(fullname, path, target=target)
            elif hasattr(finder, 'load_module'):
                spec = spec_from_loader(fullname, finder)
            if spec is not None:
                break
        return spec

    def expand_macros(self, source_code, filename, fullname, spec, lang_module):
        """Parse, apply AST transforms, and compile.

        Parses the source_code, applies the ast_transformer of the dialect,
        and macro-expands the resulting AST if it has macros. Then compiles
        the final AST.

        Returns both the compiled new AST, and the raw new AST.
        """
        logger.info('Parse in file {} (module {})'.format(filename, fullname))
        tree = ast.parse(source_code)

        if not (isinstance(tree, ast.Module) and tree.body):
            msg = "Expected a Module node with at least one statement or expression in file {} (module {})".format(filename, fullname)
            logger.exception(msg)
            raise SyntaxError(msg)

        # The 'from __lang__ import xxx' has done its job, replace it with
        # '__lang__ = "xxx"' for run-time introspection.
        def isimportdialect(tree):
            return type(tree) is ast.ImportFrom and tree.module == "__lang__"
        # q[] would be much easier but we want to keep MacroPy optional.
        # We need to be careful to insert a location to each AST node
        # in case we're not invoking MacroPy (which fixes missing locations).
        def make_langname_setter(tree):
            s = ast.Str(s=tree.names[0])
            s = ast.copy_location(s, tree)
            n = ast.Name(id="__lang__", ctx=ast.Store())
            n = ast.copy_location(n, tree)
            a = ast.Assign(targets=[n], value=s)
            a = ast.copy_location(a, tree)
            return a

        if isimportdialect(tree.body[0]):
            tree.body = [make_langname_setter(tree.body[0])] + tree.body[1:]
        # variant with module docstring
        elif len(tree.body) > 1 and isinstance(tree.body[0], ast.Expr) and \
             isimportdialect(tree.body[1]):
            tree.body = [tree.body[0], make_langname_setter(tree.body[1])] + tree.body[2:]
        else:  # we know the lang-import is there; it's in some other position
            msg = "Misplaced lang-import in file {} (module {})".format(filename, fullname)
            logger.exception(msg)
            raise SyntaxError(msg)

        if hasattr(lang_module, "ast_transformer"):
            logger.info('Dialect AST transform in file {} (module {})'.format(filename, fullname))
            tree = lang_module.ast_transformer(tree)

        # detect macros **after** any dialect-level whole-module transform
        new_tree = tree
        if macropy:
            logger.info('Detect macros in file {} (module {})'.format(filename, fullname))
            bindings = macropy.core.macros.detect_macros(tree, spec.name,
                                                         spec.parent,
                                                         spec.name)
            if bindings:  # expand macros
                logger.info('Expand macros in file {} (module {})'.format(filename, fullname))
                modules = []
                for mod, bind in bindings:
                    modules.append((importlib.import_module(mod), bind))
                new_tree = macropy.core.macros.ModuleExpansionContext(
                    tree, source_code, modules).expand_macros()

        try:
            # MacroPy uses the old tree here as input to compile(), but it doesn't matter,
            # since ``ModuleExpansionContext.expand_macros`` mutates the tree in-place.
            logger.info('Compile file {} (module {})'.format(filename, fullname))
            return compile(new_tree, filename, "exec"), new_tree
        except Exception:
            logger.exception("Error while compiling file {} (module {})".format(filename, fullname))
            raise

    def find_spec(self, fullname, path, target=None):
        spec = self._find_spec_nomacro(fullname, path, target)
        if spec is None or not (hasattr(spec.loader, 'get_source') and
                                callable(spec.loader.get_source)):  # noqa: E128
            if fullname != 'org':
                # stdlib pickle.py at line 94 contains a ``from
                # org.python.core for Jython which is always failing,
                # of course
                logging.debug('Failed finding spec for {}'.format(fullname))
            return
        origin = spec.origin
        if origin == 'builtin':
            return
        try:
            source = spec.loader.get_source(fullname)
        except ImportError:
            logging.debug('Loader for {} was unable to find the sources'.format(fullname))
            return
        except Exception:
            logging.exception('Loader for {} raised an error'.format(fullname))
            return

        lang_import = "from __lang__ import"
        if lang_import not in source:
            return  # this module does not use a dialect

        # Detect the dialect... ugh!
        #   - At this point, the input is text.
        #   - It's not parseable by ast.parse, because a dialect may introduce
        #     new surface syntax.
        #   - Similarly, it's not tokenizable by stdlib's tokenizer, because
        #     a dialect may customize what constitutes a token.
        #   - So we can only rely on the literal text "from __lang__ import xxx".
        #   - This is rather similar to how Racket heavily constrains what may
        #     appear on the #lang line.
        matches = re.findall(r"from __lang__ import\s+(.*)\s*$", source, re.MULTILINE)
        if len(matches) != 1:
            msg = "Expected exactly one lang-import with one dialect name"
            logging.exception(msg)
            raise SyntaxError(msg)
        dialect_name = matches[0]

        try:
            lang_module = importlib.import_module(dialect_name)
        except ImportError as err:
            msg = "Could not import dialect module '{}'".format(dialect_name)
            logging.exception(msg)
            raise ImportError(msg) from err
        if not any(hasattr(lang_module, x) for x in ("source_transformer", "ast_transformer")):
            msg = "Module '{}' has no dialect transformers".format(dialect_name)
            logging.exception(msg)
            raise ImportError(msg)

        if hasattr(lang_module, "source_transformer"):
            logger.info('Dialect source transform in {}'.format(fullname))
            source = lang_module.source_transformer(source)
            if lang_import not in source:  # preserve invariant
                msg = 'Dialect source transformer for {} should not delete the lang-import'.format(fullname)
                logging.exception(msg)
                raise RuntimeError(msg)

        if not source:
            msg = "Empty source text after dialect source transform in {}".format(fullname)
            logger.exception(msg)
            raise SyntaxError(msg)

        code, tree = self.expand_macros(source, origin, fullname, spec, lang_module)

        # Unlike macropy.core.MacroLoader, which exits at this point if there were
        # no macros, we always process the module (because it was explicitly tagged
        # as this dialect, and pure source-transform dialects are also allowed).

        loader = DialectLoader(spec, code, tree)
        return spec_from_loader(fullname, loader)
