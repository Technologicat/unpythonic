# -*- coding: utf-8 -*-
# TODO: refactor much of the docstring into a Pydialect README
"""Importer for Python dialects.

Pydialect: make Python into a language platform, à la Racket; in Python, create
dialects that compile into Python at import time.

A Python-based language extension doesn't need to make it into the Python core,
*or even be desirable for inclusion* into the Python core, in order to be useful.

This is not only a game of experimentation with language features, either;
language extensions have the potential to benefit production. Building on
functions and syntactic macros, customization of the language is one more tool
for extracting patterns, at a higher level.

Pydialect places language-creation power in the hands of its users, without the
need to go to extreme lengths to hack CPython itself or implement from scratch
a custom language that compiles to Python AST or bytecode.

Pydialect is geared toward creating languages that extend Python and look
almost like Python, but extend or modify its syntax and/or semantics.
Hence *dialects*.

Pydialect dialects compile to Python and are implemented in Python, allowing
the rest of the user program to benefit from new versions of Python, mostly
orthogonally to the development of any dialect.

At its simplest, a custom dialect can alleviate the need to spam a combination
of block macros in every module of a project that uses a macro-based language
extension. Being named as a dialect, that particular combination then becomes
instantly recognizable, and DRY: the dialect definition becomes the only place
in the codebase that defines the macro combination to be used by each module in
the project. The same argument applies to custom builtins: any functions or
macros that feel like they "should be" part of the language itself, so that
they won't have to be explicitly imported in each module where they are used.

**Using dialects**

Place a *lang-import* at the start of your module::

    from __lang__ import piethon

and run your main program (in this example written in the ``piethon`` dialect)
through the ``pydialect`` bootstrapper instead of ``python3`` directly.
Any imported module that has a lang-import will be detected, and the appropriate
dialect module (if and when found) will be invoked.

The lang-import must appear as the first statement of the module; only the
module docstring is allowed to appear before it. This is to make it explicit
that **a dialect applies to the whole module**. (Local changes to semantics
are better represented as a block macro.)

At import time, the dialect importer replaces the lang-import with an
assignment that sets the module's ``__lang__`` attribute to the dialect name,
for introspection. If a module does not have a ``__lang__`` attribute, then
it was not compiled by Pydialect. Note that just like with bare MacroPy,
at run time the code is pure Python.

The lang-import is a customization added by Pydialect. This ensures that the
module will immediately fail if run under standard Python, because there is
no actual module named ``__lang__``. This syntax was chosen as a close pythonic
equivalent for Racket's ``#lang foo``.

If you use MacroPy, the Pydialect import hook must be installed at index ``0``
in ``sys.meta_path``, so that the dialect importer triggers before MacroPy's
standard macro expander. The ``pydialect`` bootstrapper takes care of this.

**Dialect API**

In Pydialect, a dialect is any module that exports one or both of the following
callables:

    ``source_transformer``: source text -> source text

        The **full source code** of the module being imported (*including*
        the lang-import) is sent to the the source transformer. The data type
        is whatever the loader's ``get_source`` returns, usually ``str``.

        Source transformers are useful e.g. for defining custom infix
        operators. For example, the monadic bind syntax ``a >>= b``
        could be made to transform into the syntax ``a.__mbind__(b)``.

        Although the input is text, in practice a token-based approach is
        recommended; see stdlib's ``tokenize`` module as a base to work from.
        (Be sure to untokenize when done, because the next stage expects text.)

        **After the source transformer**, the source text must be valid
        surface syntax for **standard Python**, i.e. valid input for
        ``ast.parse``.

    ``ast_transformer``: ``list`` of AST nodes -> ``list`` of AST nodes

        After the source transformer, but before macro expansion, the full AST
        of the module being imported (*minus* the module docstring and the
        lang-import) is sent to this whole-module AST transformer.

        This allows injecting implicit imports to create builtins for the
        dialect, as well as e.g. lifting the whole module (except the docstring
        and the code to set ``__lang__``) into a ``with`` block to apply
        some MacroPy block macro(s) to the whole module.

        **After the AST transformer**, the module is sent to MacroPy for
        macro expansion (if MacroPy is installed, and the module has macros
        at that point), and after that, the result is finally imported normally.

**The name** of a dialect is simply the name of the module or package that
implements the dialect. In other words, it's the name that needs to be imported
to find the transformer functions.

Note that a dotted name in place of the ``xxx`` in ``from __lang__ import xxx``
is not valid Python syntax, so (currently) a dialect should be defined in a
top-level module (no dots in the name). Strictly, the dialect finder doesn't
need to care about this (though it currently does), but IDEs and tools in
general are much happier with code that does not contain syntax errors.
(This allows using standard Python tools with dialects that do not introduce
any new surface syntax.)

A dialect can be implemented using another dialect, as long as there are no
dependency loops. *Whenever* a lang-import is detected, the dialect importer
is invoked (especially, also during the import of a module that defines a
new dialect). This allows creating a tower of languages.

**Implementing a dialect**

A dialect can do anything from simply adding some surface syntax (such as a
monadic bind operator), to completely changing Python's semantics, e.g. by adding
automatic tail-call optimization, continuations, and/or lazy functions. The only
limitation is that the desired functionality must be (macro-)expressible in Python.

The core of a dialect is defined as a set of functions and macros, which typically
live inside a library. The role of the dialect module is to package that core
functionality into a whole that can be concisely loaded with a single lang-import.

Typically a dialect implicitly imports its core functions and macros, to make
them appear as builtins (in the sense of *defined by default*) to modules that
use the dialect.

A dialect may also define non-core functions and macros that live in the same
library; those essentially comprise *the standard library* of the dialect.

For example, the ``lispython`` dialect itself is defined by a subset of
``unpythonic`` and ``unpythonic.syntax``; the rest of the library is available
to be imported manually; it makes up the standard library of ``lispython``.

For macros, Pydialect supports MacroPy. Technically, macros are optional,
so Pydialect's dependency on MacroPy is strictly speaking optional.
Pydialect already defines a hook for a full-module AST transform;
if that (and/or a source transform) is all you need, there's no need
to have your dialect depend on MacroPy.

However, where MacroPy shines is its infrastructure. It provides a uniform
syntax to direct AST transformations to apply to particular expressions or
blocks in the user code, and it provides a hygienic quasiquote system, which
is absolutely essential for avoiding inadvertent name conflicts (identifier
capture, free variable injection). It's also good at fixing missing source
location info for macro-generated AST nodes, which is extremely useful, since
in Python the source location info is compulsory for every AST node.

Since you're reading this, you probably already know, but be aware that, unlike
how it was envisioned during the *extensible languages* movement in the 1970s,
language extension is hardly an exercise requiring only "moderate amounts of labor
by unsophisticated users". Especially the interaction between different macros
needs a lot of thought, and as the number of language features grows, the
complexity skyrockets. (For an example, look at what hoops other parts of
``unpythonic`` must jump through to make ``lazify`` happy.) Seams between parts
of the user program that use or do not use some particular feature (or a
combination of features) also require special attention.

Python is a notoriously irregular language, not to mention a far cry from
homoiconic, so it is likely harder to extend than a Lisp. Be prepared for some
head-scratching, especially when dealing with function call arguments,
assignments and the two different kinds of function definitions (def and lambda,
one of which supports the full Python language while the other is limited to
the expression sublanguage). Green Tree Snakes (the missing Python AST docs)
is a highly useful resource here.

Be sure to understand the role of ``ast.Expr`` (the *expression statement*) and
its implications when working with MacroPy. (E.g. ``ast_literal[tree]`` by itself
in a block-quasiquote is an ``Expr``, where the value is the ``Subscript``
``ast_literal[tree]``. This may not be what you want, if you're aiming to
splice in a block of statements, but it's unavoidable given Python's AST
representation.

Dialects implemented via macros will mainly require maintenance when Python's
AST representation changes (if incompatible changes or interesting new features
hit a relevant part). Large parts of the AST representation have remained
stable over several of the latest minor releases, or even all of Python 3.
Perhaps most notably, the handling of function call arguments changed in an
incompatible way in 3.5, along with introducing MatMult and the async
machinery. The other changes between 3.4 (2014) and 3.7 (2018) are just
a couple of new node types.

Long live language-oriented programming, and have fun!

**When to make a dialect**

Often explicit is better than implicit. There is however a tipping point with
regard to complexity, and/or simply length, after which implicit becomes
better.

This already applies to functions and macros; code in a ``with continuations``
block is much more readable and maintainable than code manually converted to
continuation-passing style (CPS). There's obviously a tradeoff; as PG mentions
in On Lisp, each abstraction is another entity for the reader to learn and
remember, so it must save several times its own length to become an overall win.

So, when to make a dialect depends on how much it will save (in a project or
across several), and on the other hand on how important it is to have a shared
central definition that specifies a "language-level" common ground for a set of
user modules.

**Combining existing dialects**

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

Ground-up extension efforts that replace Python's syntax:

    Dogelang, Python with Haskell-like syntax; compiles to Python bytecode:
        https://pyos.github.io/dg/

    Hy, a Lisp-2 that compiles to Python AST:
        http://docs.hylang.org/en/stable/
"""

import ast
from ast import Expr, Name, If, Num, ImportFrom, Pass, copy_location

import importlib
from importlib.util import spec_from_loader
import logging
import sys
import re

try:
    import macropy.core
    from macropy.core.walkers import Walker
except ImportError:
    macropy = Walker = None

logger = logging.getLogger(__name__)

# This is essentially a copy of ``macropy.core.import_hooks.MacroLoader``, copied to
# make sure that the implementation won't go out of sync with our ``DialectFinder``.
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
#   detect whether to use the macro loader, the input must be scanned for macros.
#   We could dispatch to a custom loader immediately after detecting that the
#   module uses a dialect, but have chosen to just inherit this design.

@singleton
class DialectFinder:
    """Importer that matches any module that has a 'from __lang__ import xxx'."""

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
            if finder is self or (macropy and finder is macropy.core.import_hooks.MacroFinder) or \
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
            logger.error(msg)
            raise SyntaxError(msg)

        # The 'from __lang__ import xxx' has done its job, replace it with
        # '__lang__ = "xxx"' for run-time introspection.
        def isimportdialect(tree):
            return type(tree) is ast.ImportFrom and tree.module == "__lang__"
        # q[] would be much easier but we want to keep MacroPy optional.
        # We need to be careful to insert a location to each AST node
        # in case we're not invoking MacroPy (which fixes missing locations).
        def make_langname_setter(tree):
            s = ast.Str(s=tree.names[0].name)
            s = ast.copy_location(s, tree)
            n = ast.Name(id="__lang__", ctx=ast.Store())
            n = ast.copy_location(n, tree)
            a = ast.Assign(targets=[n], value=s)
            a = ast.copy_location(a, tree)
            return a

        if isimportdialect(tree.body[0]):
            preamble = [make_langname_setter(tree.body[0])]
            thebody = tree.body[1:]
        # variant with module docstring
        elif len(tree.body) > 1 and isinstance(tree.body[0], ast.Expr) and \
             isimportdialect(tree.body[1]):
            preamble = [tree.body[0], make_langname_setter(tree.body[1])]
            thebody = tree.body[2:]
        else:  # we know the lang-import is there; it's in some other position
            msg = "Misplaced lang-import in file {} (module {})".format(filename, fullname)
            logger.error(msg)
            raise SyntaxError(msg)

        if hasattr(lang_module, "ast_transformer"):
            logger.info('Dialect AST transform in file {} (module {})'.format(filename, fullname))
            thebody = lang_module.ast_transformer(thebody)
        tree.body = preamble + thebody

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
            logger.error("Error while compiling file {} (module {})".format(filename, fullname))
            raise

    def find_spec(self, fullname, path, target=None):
        spec = self._find_spec_nomacro(fullname, path, target)
        if spec is None or not (hasattr(spec.loader, 'get_source') and
                                callable(spec.loader.get_source)):  # noqa: E128
            if fullname != 'org':
                # stdlib pickle.py at line 94 contains a ``from
                # org.python.core for Jython which is always failing,
                # of course
                logger.debug('Failed finding spec for {}'.format(fullname))
            return
        origin = spec.origin
        if origin == 'builtin':
            return
        try:
            source = spec.loader.get_source(fullname)
        except ImportError:
            logger.debug('Loader for {} was unable to find the sources'.format(fullname))
            return
        except Exception:
            logger.error('Loader for {} raised an error'.format(fullname))
            return
        if not source:  # some loaders may return None for the sources, without raising an exception
            logger.debug('Loader returned empty sources for {}'.format(fullname))
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
        matches = re.findall(r"from __lang__ import\s+([0-9a-zA-Z_]+)\s*$", source, re.MULTILINE)
        if len(matches) != 1:
            msg = "Expected exactly one lang-import with one dialect name"
            logger.error(msg)
            raise SyntaxError(msg)
        dialect_name = matches[0]

        try:
            logger.info("Detected dialect '{}' in module '{}', loading dialect".format(dialect_name, fullname))
            lang_module = importlib.import_module(dialect_name)
        except ImportError as err:
            msg = "Could not import dialect module '{}'".format(dialect_name)
            logger.error(msg)
            raise ImportError(msg) from err
        if not any(hasattr(lang_module, x) for x in ("source_transformer", "ast_transformer")):
            msg = "Module '{}' has no dialect transformers".format(dialect_name)
            logger.error(msg)
            raise ImportError(msg)

        if hasattr(lang_module, "source_transformer"):
            logger.info('Dialect source transform in {}'.format(fullname))
            source = lang_module.source_transformer(source)
            if not source:
                msg = "Empty source text after dialect source transform in {}".format(fullname)
                logger.error(msg)
                raise SyntaxError(msg)
            if lang_import not in source:  # preserve invariant
                msg = 'Dialect source transform for {} should not delete the lang-import'.format(fullname)
                logger.error(msg)
                raise RuntimeError(msg)

        code, tree = self.expand_macros(source, origin, fullname, spec, lang_module)

        # Unlike macropy.core.import_hooks.MacroLoader, which exits at this point if there
        # were no macros, we always process the module (because it was explicitly tagged
        # as a dialect, and pure source-transform dialects are also allowed).

        loader = DialectLoader(spec, code, tree)
        return spec_from_loader(fullname, loader)

def splice_ast(body, template, tag):
    """Utility: in an AST transformer, splice module body into template.

    Imports for MacroPy macros are handled specially, gathering them all at the
    front, so that MacroPy sees them. Any macro imports in the template are
    placed first (in the order they appear in the template), followed by any
    macro imports in the user code (in the order they appear in the user code).

    This utility is provided as a convenience for modules that define dialects.
    We use MacroPy to perform the splicing, so this function is only available
    when MacroPy is installed (``ImportError`` is raised if not). Installation
    status is checked only once per session, when ``dialects`` is first imported.

    Parameters:

        ``body``: ``list`` of statements
            Module body of the original user code (input).

        ``template``: ``list`` of statements
            Template for the module body of the new module (output).

            Must contain a marker that indicates where ``body`` is to be
            spliced in. The marker is an ``ast.Name`` node whose ``id``
            attribute matches the value of the ``tag`` string.

        ``tag``: ``str``
            The value of the ``id`` attribute of the marker in ``template``.

    Returns the new module body, i.e. ``template`` with ``body`` spliced in.

    Example::

        marker = q[name["__paste_here__"]]      # MacroPy, or...
        marker = ast.Name(id="__paste_here__")  # ...manually

        ...  # create template, place the marker in it

        dialects.splice_ast(body, template, "__paste_here__")

    """
    if not Walker:  # optional dependency
        raise ImportError("macropy.core.walkers.Walker not found; MacroPy likely not installed")
    if not body:  # ImportError because this occurs during the loading of a module written in a dialect.
        raise ImportError("expected at least one statement or expression in module body")

    def is_paste_here(tree):
        return type(tree) is Expr and type(tree.value) is Name and tree.value.id == tag
    def is_macro_import(tree):
        return type(tree) is ImportFrom and tree.names[0].name == "macros"

    # XXX: MacroPy's debug logger will sometimes crash if a node is missing a source location.
    # In general, dialect templates are fully macro-generated with no source location info to start with.
    # Pretend it's all at the start of the user module.
    locref = body[0]
    @Walker
    def fix_template_srcloc(tree, **kw):
        if not all(hasattr(tree, x) for x in ("lineno", "col_offset")):
            tree = copy_location(tree, locref)
        return tree

    @Walker
    def extract_macro_imports(tree, *, collect, **kw):
        if is_macro_import(tree):
            collect(tree)
            tree = copy_location(Pass(), tree)  # must output a node so replace by a pass stmt
        return tree

    template = fix_template_srcloc.recurse(template)
    template, template_macro_imports = extract_macro_imports.recurse_collect(template)
    body, user_macro_imports = extract_macro_imports.recurse_collect(body)

    @Walker
    def splice_body_into_template(tree, *, stop, **kw):
        if not is_paste_here(tree):
            return tree
        stop()  # prevent infinite recursion in case the user code contains a Name that looks like the marker
        return If(test=Num(n=1),
                  body=body,
                  orelse=[],
                  lineno=tree.lineno, col_offset=tree.col_offset)
    finalbody = splice_body_into_template.recurse(template)
    return template_macro_imports + user_macro_imports + finalbody
