# Python Module Guidelines

Цель: каждый Python-модуль должен быть **понятным**, **тестируемым**, **стабильным**, **минимально связанным** и готовым к production-использованию.

Формат оптимизирован для LLM-агентов: короткие правила, ключевые слова `MUST / SHOULD / MUST NOT`, workflow и checklist.

---

## 1. Scope

Эти правила применяются к любому Python-модулю независимо от домена.

Модуль **MUST** также следовать соседнему файлу:

```text
coq_program_module_guidelines.md
```

Если Python-код реализует или вызывает логику, для которой есть Coq-спецификация, Python-модуль **MUST** сохранять доказанный контракт и не расширять поведение за пределами verified boundary.

---

## 2. Hard rules

1. **MUST** иметь одну понятную ответственность.
2. **MUST** быть импортируемым без side effects.
3. **MUST NOT** выполнять I/O, сетевые вызовы, чтение env, запуск потоков или изменение global state при import.
4. **MUST** явно описывать public API через имена, type hints и docstrings.
5. **MUST** иметь deterministic behavior для одинаковых входов, кроме явно переданных источников nondeterminism.
6. **MUST** валидировать входы на границе public API.
7. **MUST** явно моделировать ошибки: exceptions, result types или domain-specific error objects.
8. **MUST NOT** глотать исключения через bare `except` или `except Exception` без явного восстановления/оборачивания.
9. **MUST NOT** скрывать важную логику в implicit globals, monkey patching или runtime mutation.
10. **MUST** иметь автоматические тесты для public behavior.
11. **MUST** проходить formatter, linter, type checker и tests в CI/local validation.

---

## 3. Module structure

Рекомендуемый порядок внутри файла:

```text
1. Module docstring
2. Future imports
3. Standard library imports
4. Third-party imports
5. Local imports
6. Constants
7. Public types / protocols / dataclasses
8. Private helpers
9. Public functions / classes
10. Explicit exports via __all__, if useful
```

Модуль **SHOULD** оставаться малым. Если файл стал трудно читать или тестировать, раздели его по ответственности.

---

## 4. Public API rules

1. **MUST** отделять public API от private helpers.
2. **MUST** использовать `_private_name` для internal-only функций, классов и констант.
3. **SHOULD** задавать `__all__` для библиотечных модулей.
4. **MUST** не ломать public API без явного migration path.
5. **MUST** не возвращать internal mutable state напрямую.
6. **SHOULD** предпочитать immutable value objects для данных без lifecycle.
7. **MUST** документировать units, ranges, optionality и error behavior.

Минимальный docstring для public function:

```python
def normalize_score(value: float) -> float:
    """Return score normalized to [0.0, 1.0].

    Raises:
        ValueError: If value is outside the accepted input range.
    """
```

---

## 5. Typing rules

1. **MUST** использовать type hints для public API.
2. **SHOULD** использовать `typing.Protocol` для behavior contracts.
3. **SHOULD** использовать `dataclass(frozen=True)` или immutable structures для value objects.
4. **MUST NOT** использовать `Any` в public API без причины, указанной рядом в комментарии.
5. **MUST** уточнять optional values как `T | None` и явно обрабатывать `None`.
6. **SHOULD** использовать narrow types: `Literal`, `NewType`, `Enum`, domain-specific classes.
7. **MUST** избегать mutable default arguments.

Bad:

```python
def add_item(item, items=[]): ...
```

Good:

```python
def add_item(item: str, items: list[str] | None = None) -> list[str]: ...
```

---

## 6. Dependency rules

1. **MUST** импортировать только прямые зависимости.
2. **MUST** держать imports на верхнем уровне, кроме случаев lazy import для optional/heavy dependency.
3. **MUST NOT** создавать циклические зависимости.
4. **SHOULD** инвертировать зависимости через параметры, protocols или small interfaces.
5. **MUST NOT** читать config/env внутри core logic; передавай config явно.
6. **SHOULD** изолировать внешние adapters от pure/domain logic.

---

## 7. State and side effects

1. **MUST** делать side effects явными в имени, docstring или dependency signature.
2. **SHOULD** предпочитать pure functions для core logic.
3. **MUST** передавать clock, random, filesystem, network и process execution как зависимости, если они влияют на результат.
4. **MUST NOT** изменять входные mutable объекты без явного контракта.
5. **MUST** ограничивать global mutable state.
6. **SHOULD** возвращать новые значения вместо mutation.

---

## 8. Error handling

1. **MUST** использовать domain-specific exceptions для domain failures.
2. **MUST** сохранять original exception через `raise ... from exc`, если ошибка оборачивается.
3. **MUST NOT** возвращать `None` как ошибку, если `None` является валидным значением.
4. **SHOULD** различать programmer errors и expected domain errors.
5. **MUST** добавлять context к ошибкам без утечки secrets.
6. **MUST** тестировать error paths.

---

## 9. Logging and observability

1. **MUST NOT** использовать `print` в production module logic.
2. **SHOULD** использовать module-level logger:

```python
logger = logging.getLogger(__name__)
```

3. **MUST NOT** логировать secrets, tokens, passwords, private keys или raw personal data.
4. **SHOULD** логировать decisions, boundary failures и retry-relevant context.
5. **MUST** не менять logging configuration внутри importable module.

---

## 10. Security rules

1. **MUST** считать внешние inputs недоверенными.
2. **MUST** валидировать paths, URLs, serialized data и commands перед использованием.
3. **MUST NOT** использовать `eval`, `exec`, unsafe deserialization или shell execution без строгого allowlist-контракта.
4. **MUST** хранить secrets вне кода и тестовых fixtures.
5. **MUST** минимизировать exposed surface area.
6. **SHOULD** использовать safe defaults.

---

## 11. Testing rules

1. **MUST** тестировать public behavior, not implementation details.
2. **MUST** покрывать happy path, boundary values и error paths.
3. **SHOULD** использовать property-based tests для pure/domain logic.
4. **MUST** фиксировать regression tests для найденных bugs.
5. **MUST** mock/fake только внешние boundaries, не core logic.
6. **MUST** делать tests deterministic.
7. **SHOULD** держать test names как behavior statements.

Good test name:

```python
def test_normalize_score_rejects_values_above_maximum() -> None: ...
```

---

## 12. Performance and resource rules

1. **MUST** иметь понятную complexity для non-trivial algorithms.
2. **SHOULD** избегать hidden O(n²) на expected large inputs.
3. **MUST** закрывать files, sockets и handles через context managers.
4. **MUST** не кэшировать unbounded data без eviction/limit.
5. **SHOULD** benchmark only performance-critical paths.
6. **MUST** не оптимизировать ценой потери контракта, читаемости или correctness.

---

## 13. Style rules

1. **MUST** следовать formatter/linter project config.
2. **MUST** использовать ясные domain names вместо generic names.
3. **MUST NOT** оставлять dead code, commented-out experiments или debug prints.
4. **SHOULD** писать маленькие функции с явным input/output contract.
5. **SHOULD** предпочитать early return для guard clauses.
6. **MUST** держать comments рядом с неочевидным why, не с obvious what.

---

## 14. LLM-agent workflow

Агент **MUST** работать циклом:

```text
1. Read module purpose and public API.
2. Read coq_program_module_guidelines.md located next to this file.
3. Identify verified boundary, if any.
4. Identify inputs, outputs, errors, state and side effects.
5. Check imports and import-time behavior.
6. Check type hints and public docstrings.
7. Check validation and error handling.
8. Check tests for public behavior and edge cases.
9. Run formatter, linter, type checker and tests.
10. Remove dead code, debug code and unused dependencies.
11. Report changed files, commands run and unresolved risks.
```

Агент **MUST NOT**:

```text
- introduce hidden side effects at import time;
- weaken validation to make tests pass;
- bypass Coq-backed contracts;
- replace explicit errors with silent fallback;
- add broad Any types to avoid type errors;
- mock the unit under test instead of its external dependencies;
- claim production-ready if validation commands were not run.
```

Финальный отчёт агента **SHOULD** иметь формат:

```text
Changed files:
- ...

Public API changed:
- yes/no

Verified boundary affected:
- yes/no

Validation commands run:
- ruff format --check ...
- ruff check ...
- mypy ...
- pytest ...

Unresolved risks:
- none
```

---

## 15. Definition of Done

```text
[ ] Module has one clear responsibility.
[ ] Importing the module has no unintended side effects.
[ ] Public API has type hints and docstrings.
[ ] Inputs are validated at public boundaries.
[ ] Errors are explicit and tested.
[ ] Core logic is isolated from external side effects.
[ ] Mutable state is minimized and controlled.
[ ] No secrets, unsafe eval/exec, or unsafe deserialization.
[ ] Tests cover public behavior, edge cases and errors.
[ ] Formatter passes.
[ ] Linter passes.
[ ] Type checker passes.
[ ] Tests pass.
[ ] Coq-backed contract is preserved, if applicable.
[ ] Agent report lists changed files, commands run and risks.
```
