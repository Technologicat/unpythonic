# -*- coding: utf-8 -*-
"""Importer for custom dialects of Python.

**Using dialects**

Place a *lang-import* at the start of your module::

    from __lang__ import piethon

and run your main program (in this example written in the ``piethon`` dialect)
through the ``pydialect`` bootstrapper instead of ``python3`` directly.
Any imported module that uses a registered dialect will be detected and
the appropriate transformations will be applied.

The lang-import must appear as the first statement of the module; only the module
docstring is allowed to appear before it. This is to make it explicit that a
dialect applies to the whole module.

The lang-import is a customization added by the dialect machinery. This ensures
that the module will immediately fail if run by standard Python (because there
is no actual module named ``__lang__``). This syntax was chosen as a close
pythonic equivalent for Racket's ``#lang foo``.

**Creating dialects**

The core of a dialect is defined as a set of macros and functions. In Python's
case, the macros are implemented using MacroPy.

With a whole-module AST transform, a dialect can import its core macros and
functions implicitly, to make them appear as builtins to the dialect user.

The dialect can also perform any other AST transformation, including lifting the
whole module body into a ``with`` block, which is useful for enabling some MacroPy
block macros for the whole module.

Before the AST transformation, a dialect may also define new surface syntax by
operating on the source code text. Usually this implies a customized tokenizer.
See the stdlib module ``tokenize`` as a base to work from.

The ``pydialect`` bootstrapper should then be told about the new dialect, so that
it can install the import hook.

**Notes**

Adapted from ``core/import_hooks.py`` in MacroPy 1.1.0b2.

In the Lisp community, surface syntax transformations are known as *reader macros*
(although technically it's something done at the parsing step, unrelated to
syntactic macros).

Further reading:

    http://stupidpythonideas.blogspot.com/2015/06/hacking-python-without-hacking-python.html
"""

# TODO: inject a __lang__ module attribute that has .dialect_name?

import ast
import importlib
from importlib.util import spec_from_loader
import logging
import sys

import macropy.core

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

class DialectFinder:
    """Importer that matches only a given dialect."""
    def __init__(self, name, source_transformer=None, ast_transformer=None):
        """Constructor.

        Both ``source_transformer`` and ``ast_transformer`` are optional;
        but for a dialect definition to make any sense, at least one of them
        should be specified.

        Parameters::

            name: str
                Name of the dialect for the ``from __lang__ import xxx`` trigger.
                Here ``__lang__`` is literal, the ``xxx`` is the name.

            source_transformer: callable: source text -> source text

                The full source code of the module being imported (*including*
                the lang-import) is sent to the the source transformer.

                Source transformers are useful e.g. for defining custom infix
                operators. For example, the monadic bind syntax ``a >>= b``
                could be made to transform into the syntax ``a.__mbind__(b)``.

                For a token-based approach, see stdlib's ``tokenize`` module
                as a base to work from. Be sure to untokenize when done, because
                the next stage expects source text.

                **After the source transformer, the source text must be valid
                surface syntax for standard Python**, i.e. valid input for
                ``ast.parse``.

            ast_transformer: callable: Python AST -> Python AST

                The full AST of the module being imported (*minus* the lang-import)
                is sent to the AST transformer.

                This allows injecting imports to create builtins for the dialect,
                as well as e.g. placing the whole module inside a ``with`` block
                to apply some MacroPy block macro to the whole module.

                **After the AST transformer**, the module is sent to MacroPy for
                macro expansion (if it has macros at this point), and after that,
                the result is imported normally.
        """
        self.dialect_name = name
        self.source_transformer = source_transformer
        self.ast_transformer = ast_transformer

    def install(self):
        """Install the import hook.

        MacroPy must be activated before installing any dialect hooks.
        The ``pydialect`` bootstrapper takes care of this.
        """
        if self not in sys.meta_path:
            sys.meta_path.insert(0, self)

    def _find_spec_nomacro(self, fullname, path, target=None):
        """Try to find the original, non macro-expanded module using all the
        remaining meta_path finders (except other dialects, and except MacroPy's,
        to avoid handling macros twice).
        """
        spec = None
        for finder in sys.meta_path:
            # when testing with pytest, it installs a finder that for
            # some yet unknown reasons makes macros expansion
            # fail. For now it will just avoid using it and pass to
            # the next one
            if isinstance(finder, DialectFinder) or finder is macropy.core.MacroFinder or \
               'pytest' in finder.__module__:
                continue
            if hasattr(finder, 'find_spec'):
                spec = finder.find_spec(fullname, path, target=target)
            elif hasattr(finder, 'load_module'):
                spec = spec_from_loader(fullname, finder)
            if spec is not None:
                break
        return spec

    def expand_macros(self, source_code, filename, fullname, spec):
        """Parse, apply AST transforms, and compile.

        Parses the source_code, applies the ast_transformer, and macro-expands
        the resulting AST if it has macros. Then compiles the final AST.

        Returns both the compiled new AST, and the raw new AST.
        """
        logger.info('Parse in file {} (module {})'.format(filename, fullname))
        tree = ast.parse(source_code)

        if not (isinstance(tree, ast.Module) and tree.body):
            msg = "Expected at least one statement or expression in file {} (module {})".format(filename, fullname)
            logger.exception(msg)
            raise SyntaxError(msg)

        # discard the "from __lang__ import xxx", it's done its job
        def isimportthisdialect(tree):
            return type(tree) is ast.ImportFrom and tree.module == "__lang__" and \
                   tree.names[0].name == self.dialect_name
        if isimportthisdialect(tree.body[0]):
            tree.body = tree.body[1:]
        # variant with module docstring
        elif len(tree.body) > 1 and isinstance(tree.body[0], ast.Expr) and \
             isimportthisdialect(tree.body[1]):
            tree.body = [tree.body[0]] + tree.body[2:]
        else:  # we know the lang-import is there; it's in some other position
            msg = "Misplaced 'from __lang__ import {}' in file {} (module {})".format(self.dialect_name, filename, fullname)
            logger.exception(msg)
            raise SyntaxError(msg)

        if self.ast_transformer:
            logger.info('AST transform in file {} (module {})'.format(filename, fullname))
            tree = self.ast_transformer(tree)

        # detect macros **after** any dialect-level whole-module transform
        bindings = macropy.core.macros.detect_macros(tree, spec.name,
                                                     spec.parent,
                                                     spec.name)
        if bindings:  # expand macros
            modules = []
            for mod, bind in bindings:
                modules.append((importlib.import_module(mod), bind))
            new_tree = macropy.core.macros.ModuleExpansionContext(
                tree, source_code, modules).expand_macros()
        else:
            new_tree = tree

        try:
            # MacroPy uses the old tree here as input to compile(), but it doesn't matter,
            # since ``ModuleExpansionContext.expand_macros`` mutates the tree in-place.
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

        lang_import = "from __lang__ import {}".format(self.dialect_name)
        if lang_import not in source:
            return  # not this dialect

        if self.source_transformer:
            logger.info('Source transform in {}'.format(fullname))
            source = self.source_transformer(source)
            if lang_import not in source:  # preserve invariant
                msg = 'Source transformer for {} should not delete the lang-import'.format(fullname)
                logging.exception(msg)
                raise RuntimeError(msg)

        if not source:
            msg = "Empty source text after source transform in {}".format(fullname)
            logger.exception(msg)
            raise SyntaxError(msg)

        code, tree = self.expand_macros(source, origin, fullname, spec)

        # Unlike macropy.core.MacroLoader, which exits at this point if there were
        # no macros, we always process the module (because it was explicitly tagged
        # as this dialect, and pure source-transform dialects are also allowed).

        loader = DialectLoader(spec, code, tree)
        return spec_from_loader(fullname, loader)
