# Deferred Issues

- **D4**: `typecheck.py` — expand runtime type checker to support more `typing` features. Split into three sets:

  **Set 1 — Easy wins** (do first):
  - `NoReturn` — always `False`
  - `Type[X]` — check `isinstance(value, type) and issubclass(value, X)`
  - `Literal[v1, v2, ...]` — check `value in args`
  - `ClassVar[T]`, `Final[T]` — strip wrapper, check inner type
  - `DefaultDict[K, V]`, `Counter[T]`, `OrderedDict[K, V]`, `ChainMap[K, V]` — slot into existing mapping/collection patterns
  - Also: deprecation markers on `typing.Text` and `typing.ByteString` (remove when floor bumps to Python 3.12); clean up stale `Python 3.6+` guard in `test_typecheck.py:182`

  **Set 2 — Useful for dispatch** (follow-up):
  - `IO`, `TextIO`, `BinaryIO` — simple `isinstance` checks
  - `Pattern[T]`, `Match[T]` — `isinstance` against `re.Pattern`/`re.Match`
  - `ContextManager`, `AsyncContextManager` — `isinstance` checks
  - `Awaitable`, `Coroutine`, `AsyncIterable`, `AsyncIterator` — `isinstance` checks
  - `Generator`, `AsyncGenerator` — `isinstance` checks (no yield/send/return type checking)
  - `NamedTuple` — tricky but doable

  **Set 3 — Hard / questionable value** (defer or discuss):
  - `Protocol` — full structural subtyping, heavy
  - `TypedDict` — required vs. optional keys, medium-hard
  - `Generic` — abstract, unclear semantics for value checking
  - `ForwardRef` — needs a namespace to resolve the string

