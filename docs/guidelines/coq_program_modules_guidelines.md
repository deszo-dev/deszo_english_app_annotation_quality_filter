# Best Guidelines: program-модули с логикой, доказанной в Coq

Цель: каждый программный модуль имеет **исполняемую логику**, **явную спецификацию** и **машинно проверяемые доказательства**, что логика удовлетворяет спецификации.

Формат оптимизирован для LLM-агентов: короткие правила, ключевые слова `MUST / SHOULD / MUST NOT`, шаблон и чеклист.

---

## 1. Hard rules

1. **MUST** компилироваться через `coqc`/CI из чистого checkout.
2. **MUST NOT** оставлять `Admitted`, `admit`, `Abort`, незакрытые obligations или скрытые holes.
3. **MUST NOT** добавлять `Axiom` в implementation-файлы. Внешние предположения — только в отдельном `Assumptions.v` и считаются debt/blocker для full verification.
4. **MUST NOT** ослаблять spec ради прохождения proof. Менять spec можно только при изменении требований.
5. **MUST** использовать `Qed` по умолчанию. `Defined` — только если proof term должен участвовать в вычислении.
6. **MUST** держать все `Require`/`Import` сверху файла и импортировать только прямые зависимости.
7. **MUST** доказывать public behavior, а не “что тактика сработала”. Контракт — это имена и statements теорем.
8. **MUST** делать каждый invariant именованным `Definition`/`Theorem`.

---

## 2. Минимальная структура модуля

Рекомендуемый layout:

```text
Foo/
  FooModel.v        # data model, domains, invariants
  FooSpec.v         # pre/postconditions, abstract behavior
  FooImpl.v         # executable Gallina/program logic
  FooProofs.v       # correctness/preservation/refinement proofs
  FooExtraction.v   # optional extraction boundary
```

Для маленьких модулей можно один файл, но порядок внутри файла должен быть таким:

```coq
From Coq Require Import ...

Module FooModel.  ... End FooModel.
Module FooSpec.   ... End FooSpec.
Module FooImpl.   ... End FooImpl.
Module FooProofs. ... End FooProofs.
```

---

## 3. Контракт verified module

Каждый verified module **SHOULD** иметь 4 слоя:

1. **Types**: `state`, `input`, `output`, `error`, `event`.
2. **Implementation**: исполняемые функции (`step`, `run`, `eval`, `update`).
3. **Specification**: `valid_*`, `post_*`, `invariant_*`, abstract relation.
4. **Theorems**: `*_correct`, `*_sound`, `*_complete`, `*_preserves_*`.

Минимальный шаблон:

```coq
Module Type FOO_SPEC.
  Parameter state input output : Type.

  Parameter valid_input : state -> input -> Prop.
  Parameter step : state -> input -> output * state.
  Parameter post : state -> input -> output * state -> Prop.

  Parameter step_correct :
    forall st x,
      valid_input st x ->
      post st x (step st x).
End FOO_SPEC.
```

Implementation должен закрыть этот контракт реальными definitions и proofs:

```coq
Module Foo <: FOO_SPEC.
  Definition state := ... .
  Definition input := ... .
  Definition output := ... .

  Definition valid_input (st : state) (x : input) : Prop := ... .
  Definition step (st : state) (x : input) : output * state := ... .
  Definition post (st : state) (x : input) (r : output * state) : Prop := ... .

  Theorem step_correct :
    forall st x,
      valid_input st x ->
      post st x (step st x).
  Proof.
    ...
  Qed.
End Foo.
```

---

## 4. Spec rules

1. **MUST** сначала определить preconditions/postconditions, затем доказывать implementation.
2. **MUST** отделять validity от execution: лучше `valid_input st x -> post st x (step st x)`, чем partial logic без явной области определения.
3. **SHOULD** моделировать ошибки явно: `option`, `sum`, `result`/domain-specific error type.
4. **MUST** именовать observable behavior: `returns_ok`, `emits_event`, `preserves_balance`, `does_not_mutate_config`.
5. **SHOULD** покрывать минимум:
   - safety: плохое состояние недостижимо;
   - preservation: invariant сохраняется;
   - correctness: output соответствует spec;
   - refinement/equivalence: implementation соответствует abstract model.
6. **MUST NOT** использовать пустые specs вроде `post := fun _ => True`, кроме явно заблокированных placeholder-задач.

---

## 5. Proof rules

1. **MUST** дробить proofs на маленькие named lemmas. Если proof длиннее ~30 строк или pattern повторился дважды — вынести lemma.
2. **SHOULD** идти по лестнице: model lemmas → invariant lemmas → function lemmas → module theorem.
3. **MUST** использовать bullets/focus (`-`, `+`, `*`) стабильно.
4. **SHOULD** предпочитать явные шаги: `intros`, `destruct ... as ... eqn:...`, `induction ... as ...`, `rewrite`, `inversion`, `subst`, `lia`, `congruence`.
5. **MUST** bound automation: `eauto 6 with foo_db`, а не безграничный proof search.
6. **MUST NOT** прятать главную логику в custom tactic. Tactic может сокращать, но ключевые факты должны быть named lemmas.
7. **MUST NOT** зависеть от случайных имён hypotheses, созданных Coq. Именуй cases явно.
8. **SHOULD** делать proof scripts устойчивыми к малым изменениям definitions: меньше `unfold` всего подряд, больше named lemmas.

---

## 6. Imports / namespace rules

1. **MUST** размещать final `Require`/`From ... Require ...` в начале файла.
2. **MUST** импортировать только используемые direct dependencies.
3. **SHOULD** использовать qualified names для редких/конфликтных facts.
4. **SHOULD** использовать `Local Open Scope`, `Local Hint`, named hint DB (`foo_db`).
5. **MUST NOT** делать global `Hint Resolve` без named DB.
6. **SHOULD** делить независимые темы на отдельные файлы для меньших зависимостей и parallel compilation.

---

## 7. LLM-agent workflow

Агент **MUST** работать циклом:

```text
1. Read target theorem statement.
2. Identify definitions used in the theorem.
3. Expand only definitions needed for the current goal.
4. Search existing lemmas before creating new ones.
5. If stuck, create one small helper lemma with precise statement.
6. Prove helper lemma.
7. Return to main theorem.
8. Compile with coqc/CI command.
9. Remove experiments/debug commands.
10. Grep forbidden tokens: Admitted, admit, Abort, Axiom, TODO-proof.
```

Агент **MUST NOT**:

```text
- change theorem statement because proof is hard;
- replace meaningful postcondition with True;
- introduce Axiom to bypass proof failure;
- hide failures behind try/auto;
- claim verified if batch compilation was not run.
```

Финальный отчёт агента **SHOULD** иметь формат:

```text
Changed files:
- ...

Proved theorems:
- Foo.step_correct
- Foo.step_preserves_invariant

Assumptions added:
- none

Commands run:
- coqc Foo/FooProofs.v
- grep -R "Admitted\|admit\|Abort\|Axiom" Foo/
```

---

## 8. Naming conventions

```text
Types:              state, input, output, error, event
Predicates:         valid_*, invariant_*, preserves_*, post_*
Functions:          step, eval, run, update, check, parse
Safety:             *_safe, *_no_error, *_preserves_*
Correctness:        *_correct, *_sound, *_complete
Refinement:         *_refines_*, *_equiv_*
Helper lemmas:      <function>_<property>_lemma
Hint DB:            foo_db
```

---

## 9. Extraction boundary

1. **MUST** держать executable code в computational types (`Set`/`Type`), а specs/proofs — в `Prop`, если proof не должен вычисляться.
2. **MUST** явно указать extraction root в `FooExtraction.v`.
3. **MUST NOT** считать wrapper-код автоматически verified. Доказана только та Gallina-функция, которая является root или частью доказанного root.
4. **SHOULD** держать target-language adapters маленькими и тестировать отдельно.

---

## 10. Definition of Done

```text
[ ] Clean checkout compiles.
[ ] No Admitted/admit/Abort/unfinished obligations.
[ ] No implementation Axiom or undocumented assumption.
[ ] Public functions have named specs.
[ ] Public specs have named correctness theorems.
[ ] Invariants are named and preserved.
[ ] Imports are minimal and at top of file.
[ ] Automation is bounded/local.
[ ] Proofs use stable bullets and explicit case names.
[ ] Extraction root is explicit, if extraction exists.
[ ] Agent report lists changed files, proven theorems, assumptions, commands run.
```

---

## 11. Minimal good example

```coq
From Coq Require Import Arith Lia.

Module Counter.
  Definition state := nat.
  Definition input := nat.
  Definition output := nat.

  Definition invariant_state (st : state) : Prop := 0 <= st.
  Definition valid_input (_st : state) (_x : input) : Prop := True.

  Definition step (st : state) (x : input) : output * state :=
    let st' := st + x in (st', st').

  Definition post (st : state) (x : input) (r : output * state) : Prop :=
    r = (st + x, st + x) /\ invariant_state (snd r).

  Theorem step_preserves_invariant :
    forall st x,
      invariant_state st ->
      valid_input st x ->
      invariant_state (snd (step st x)).
  Proof.
    intros st x _ _.
    unfold step, invariant_state.
    lia.
  Qed.

  Theorem step_correct :
    forall st x,
      invariant_state st ->
      valid_input st x ->
      post st x (step st x).
  Proof.
    intros st x Hinv Hvalid.
    unfold post, step.
    split.
    - reflexivity.
    - apply step_preserves_invariant; assumption.
  Qed.
End Counter.
```

---

## 12. Source notes

Правила согласованы с документацией Coq/Rocq и common proof-engineering practice:

- `Qed` запускает kernel check и сохраняет proof как opaque; `Defined` сохраняет transparent proof.
- `Admitted` превращает текущий statement в axiom.
- `Require`/`Import` порядок важен; imports должны быть явными, минимальными и в начале файла.
- `Module Type` подходит для публичного контракта модуля.
- `Program` может генерировать proof obligations из rich specifications.
- Extraction генерирует functional programs из Coq functions/proofs, но extraction boundary должен быть явным.
