# Deferred Issues

- **D1**: Document pyc cache pitfall and test result reading for other projects using mcpyrate/unpythonic.test.fixtures. The CLAUDE.md additions from the 2.0.0 modernization (never `py_compile` macro-enabled code; how to read test framework output with Pass/Fail/Error) are useful guidance for any project using these tools. Consider adding similar notes to mcpyrate's docs and/or unpythonic's user-facing documentation. (Discovered during Phase 3.)

- **D4**: `typecheck.py` — expand runtime type checker to support more `typing` features: NamedTuple, DefaultDict, Counter, ChainMap, OrderedDict, IO/TextIO/BinaryIO, Pattern/Match, Generic, Type, Awaitable, Coroutine, AsyncIterable, AsyncIterator, ContextManager, AsyncContextManager, Generator, AsyncGenerator, NoReturn, ClassVar, Final, Protocol, TypedDict, Literal, ForwardRef. Would improve `unpythonic.dispatch` (multiple dispatch). (Discovered during Phase 4 cleanup.)

