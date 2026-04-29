From Stdlib Require Import Arith.Arith.
From Stdlib Require Import Bool.Bool.
From Stdlib Require Import Lists.List.
From Stdlib Require Import Lia.
From Stdlib Require Import Strings.String.

Import ListNotations.
Open Scope nat_scope.
Open Scope string_scope.
Open Scope list_scope.

Module AnnotationQualityFilterSpec.

Inductive FilterLabel : Type :=
| Accept
| WeakAccept
| Reject.

Inductive ExitCode : Type :=
| Success
| ExpectedError
| SystemError.

Record Word : Type := {
  word_text : string;
  word_upos : string;
  word_head : nat;
  word_deprel : string;
  word_start_char : nat;
  word_end_char : nat
}.

Record Entity : Type := {
  entity_text : string;
  entity_type : string;
  entity_start_char : nat;
  entity_end_char : nat
}.

Record Sentence : Type := {
  sentence_text : string;
  sentence_words : list Word
}.

Record AnnotatedDocument : Type := {
  doc_sentences : list Sentence;
  doc_entities : list Entity
}.

Definition valid_word (w : Word) : Prop :=
  word_start_char w <= word_end_char w.

Definition valid_entity (e : Entity) : Prop :=
  entity_start_char e <= entity_end_char e.

Definition valid_sentence (s : Sentence) : Prop :=
  Forall valid_word (sentence_words s).

Definition valid_document (d : AnnotatedDocument) : Prop :=
  Forall valid_sentence (doc_sentences d) /\
  Forall valid_entity (doc_entities d).

Record AnnotationQualityConfig : Type := {
  cfg_accept_threshold : nat;
  cfg_weak_accept_threshold : nat;
  cfg_keep_weak_accept : bool
}.

Definition valid_config (cfg : AnnotationQualityConfig) : Prop :=
  0 < cfg_weak_accept_threshold cfg /\
  cfg_weak_accept_threshold cfg <= cfg_accept_threshold cfg /\
  cfg_accept_threshold cfg <= 100.

Definition default_config : AnnotationQualityConfig := {|
  cfg_accept_threshold := 80;
  cfg_weak_accept_threshold := 60;
  cfg_keep_weak_accept := true
|}.

Theorem default_config_valid : valid_config default_config.
Proof.
  unfold valid_config, default_config; simpl; lia.
Qed.

Record Penalties : Type := {
  structural_penalty : nat;
  dependency_penalty : nat;
  morphology_penalty : nat;
  sentence_penalty : nat;
  distribution_penalty : nat
}.

Definition weighted_penalty (p : Penalties) : nat :=
  30 * structural_penalty p +
  35 * dependency_penalty p +
  15 * morphology_penalty p +
  10 * sentence_penalty p +
  10 * distribution_penalty p.

Definition score_from_penalties (hard_failure : bool) (p : Penalties) : nat :=
  if hard_failure then 0 else 100 - (weighted_penalty p / 100).

Theorem hard_failure_score_zero :
  forall p, score_from_penalties true p = 0.
Proof.
  reflexivity.
Qed.

Theorem score_from_penalties_upper_bound :
  forall hard p, score_from_penalties hard p <= 100.
Proof.
  intros hard p.
  unfold score_from_penalties.
  destruct hard.
  - lia.
  - change (100 - (weighted_penalty p / 100) <= 100).
    apply Nat.le_sub_l.
Qed.

Definition classify_score (cfg : AnnotationQualityConfig) (score : nat)
  : FilterLabel :=
  if Nat.leb (cfg_accept_threshold cfg) score then Accept
  else if Nat.leb (cfg_weak_accept_threshold cfg) score then WeakAccept
  else Reject.

Definition label_allowed (cfg : AnnotationQualityConfig) (label : FilterLabel)
  : bool :=
  match label with
  | Accept => true
  | WeakAccept => cfg_keep_weak_accept cfg
  | Reject => false
  end.

Theorem reject_is_never_allowed :
  forall cfg, label_allowed cfg Reject = false.
Proof.
  reflexivity.
Qed.

Theorem accept_is_always_allowed :
  forall cfg, label_allowed cfg Accept = true.
Proof.
  reflexivity.
Qed.

Theorem classify_accept_at_threshold :
  forall cfg score,
    cfg_accept_threshold cfg <= score -> classify_score cfg score = Accept.
Proof.
  intros cfg score Hge.
  unfold classify_score.
  destruct (Nat.leb (cfg_accept_threshold cfg) score) eqn:Hleb.
  - reflexivity.
  - apply Nat.leb_gt in Hleb. lia.
Qed.

Theorem classify_weak_between_thresholds :
  forall cfg score,
    score < cfg_accept_threshold cfg ->
    cfg_weak_accept_threshold cfg <= score ->
    classify_score cfg score = WeakAccept.
Proof.
  intros cfg score Hlt_accept Hge_weak.
  unfold classify_score.
  destruct (Nat.leb (cfg_accept_threshold cfg) score) eqn:Hacc.
  - apply Nat.leb_le in Hacc. lia.
  - destruct (Nat.leb (cfg_weak_accept_threshold cfg) score) eqn:Hweak.
    + reflexivity.
    + apply Nat.leb_gt in Hweak. lia.
Qed.

Theorem classify_reject_below_weak :
  forall cfg score,
    valid_config cfg ->
    score < cfg_weak_accept_threshold cfg ->
    classify_score cfg score = Reject.
Proof.
  intros cfg score Hcfg Hlt_weak.
  unfold classify_score.
  destruct (Nat.leb (cfg_accept_threshold cfg) score) eqn:Hacc.
  - apply Nat.leb_le in Hacc.
    destruct Hcfg as [_ [Hweak_le_accept _]].
    lia.
  - destruct (Nat.leb (cfg_weak_accept_threshold cfg) score) eqn:Hweak.
    + apply Nat.leb_le in Hweak. lia.
    + reflexivity.
Qed.

Theorem hard_failure_reject :
  forall cfg p,
    valid_config cfg ->
    classify_score cfg (score_from_penalties true p) = Reject.
Proof.
  intros cfg p Hcfg.
  rewrite hard_failure_score_zero.
  apply classify_reject_below_weak.
  - exact Hcfg.
  - destruct Hcfg as [Hweak_pos _]. lia.
Qed.

Record AnnotationQualityResult : Type := {
  result_score : nat;
  result_label : FilterLabel
}.

Record SentenceQualityAnnotation : Type := {
  annotation_input_sentence_index : nat;
  annotation_status : FilterLabel;
  annotation_included_in_output : bool;
  annotation_result : AnnotationQualityResult
}.

Definition build_quality_annotation
  (cfg : AnnotationQualityConfig)
  (sentence_index : nat)
  (label : FilterLabel) : SentenceQualityAnnotation :=
  {|
    annotation_input_sentence_index := sentence_index;
    annotation_status := label;
    annotation_included_in_output := label_allowed cfg label;
    annotation_result := {| result_score := 0; result_label := label |}
  |}.

Fixpoint filter_sentences
  (sentences : list Sentence)
  (annotations : list SentenceQualityAnnotation) : list Sentence :=
  match sentences, annotations with
  | sentence :: rest_sentences, annotation :: rest_annotations =>
      if annotation_included_in_output annotation then
        sentence :: filter_sentences rest_sentences rest_annotations
      else
        filter_sentences rest_sentences rest_annotations
  | _, _ => []
  end.

Theorem filter_sentences_length_le :
  forall sentences annotations,
    List.length (filter_sentences sentences annotations) <= List.length sentences.
Proof.
  intros sentences annotations.
  revert annotations.
  induction sentences as [| sentence rest IH]; intros annotations; simpl.
  - destruct annotations; simpl; lia.
  - destruct annotations as [| annotation rest_annotations]; simpl; try lia.
    destruct (annotation_included_in_output annotation); simpl;
      specialize (IH rest_annotations); lia.
Qed.

Theorem filter_sentences_valid :
  forall sentences annotations,
    Forall valid_sentence sentences ->
    Forall valid_sentence (filter_sentences sentences annotations).
Proof.
  intros sentences annotations Hvalid.
  revert annotations.
  induction Hvalid as [| sentence rest Hsentence Hrest IH]; intros annotations; simpl.
  - destruct annotations; constructor.
  - destruct annotations as [| annotation rest_annotations]; simpl.
    + constructor.
    + destruct (annotation_included_in_output annotation).
      * constructor; [exact Hsentence | apply IH].
      * apply IH.
Qed.

Parameter filter_entities_for_sentences : list Sentence -> list Entity -> list Entity.
Parameter filter_entities_preserves_validity :
  forall kept_sentences input_entities,
    Forall valid_entity input_entities ->
    Forall valid_entity
      (filter_entities_for_sentences kept_sentences input_entities).

Record AnnotationQualityDocumentStatus : Type := {
  status_annotations : list SentenceQualityAnnotation
}.

Record AnnotationQualityFilterOutput : Type := {
  output_document : AnnotatedDocument;
  output_status : AnnotationQualityDocumentStatus
}.

Definition filter_core
  (document : AnnotatedDocument)
  (annotations : list SentenceQualityAnnotation) : AnnotationQualityFilterOutput :=
  let kept_sentences := filter_sentences (doc_sentences document) annotations in
  let kept_entities := filter_entities_for_sentences kept_sentences (doc_entities document) in
  {|
    output_document := {|
      doc_sentences := kept_sentences;
      doc_entities := kept_entities
    |};
    output_status := {| status_annotations := annotations |}
  |}.

Definition valid_filter_output
  (input : AnnotatedDocument)
  (o : AnnotationQualityFilterOutput) : Prop :=
  valid_document (output_document o) /\
  List.length (doc_sentences (output_document o)) <= List.length (doc_sentences input).

Theorem filter_core_output_sentence_length_le :
  forall document annotations,
    List.length (doc_sentences (output_document (filter_core document annotations))) <=
    List.length (doc_sentences document).
Proof.
  intros document annotations.
  unfold filter_core; simpl.
  apply filter_sentences_length_le.
Qed.

Theorem filter_core_primary_output_schema :
  forall document annotations,
    valid_document document ->
    valid_document (output_document (filter_core document annotations)).
Proof.
  intros document annotations Hdoc.
  destruct Hdoc as [Hsentences Hentities].
  unfold filter_core; simpl.
  split.
  - apply filter_sentences_valid. exact Hsentences.
  - apply filter_entities_preserves_validity. exact Hentities.
Qed.

Theorem filter_core_valid :
  forall document annotations,
    valid_document document ->
    valid_filter_output document (filter_core document annotations).
Proof.
  intros document annotations Hdoc.
  unfold valid_filter_output.
  split.
  - apply filter_core_primary_output_schema. exact Hdoc.
  - apply filter_core_output_sentence_length_le.
Qed.

Definition DebugTrace : Type := list string.

Definition observe_debug
  (output : AnnotationQualityFilterOutput)
  (_trace : DebugTrace) : AnnotationQualityFilterOutput :=
  output.

Theorem debug_does_not_change_filter_output :
  forall output trace,
    observe_debug output trace = output.
Proof.
  reflexivity.
Qed.

Inductive CliStatus : Type :=
| CliOk (output : AnnotationQualityFilterOutput)
| CliExpectedDataError
| CliSystemFailure.

Definition cli_exit_code (status : CliStatus) : ExitCode :=
  match status with
  | CliOk _ => Success
  | CliExpectedDataError => ExpectedError
  | CliSystemFailure => SystemError
  end.

Definition cli_stdout (status : CliStatus) : option AnnotatedDocument :=
  match status with
  | CliOk output => Some (output_document output)
  | CliExpectedDataError => None
  | CliSystemFailure => None
  end.

Theorem cli_stdout_is_primary_document :
  forall output,
    cli_stdout (CliOk output) = Some (output_document output).
Proof.
  reflexivity.
Qed.

Theorem cli_exit_code_mapping :
  forall output,
    cli_exit_code (CliOk output) = Success /\
    cli_exit_code CliExpectedDataError = ExpectedError /\
    cli_exit_code CliSystemFailure = SystemError.
Proof.
  intro output.
  repeat split; reflexivity.
Qed.

Theorem non_success_has_no_stdout_payload :
  forall status,
    cli_exit_code status <> Success -> cli_stdout status = None.
Proof.
  intros status Hnot_success.
  destruct status as [output | |]; simpl in *.
  - contradiction.
  - reflexivity.
  - reflexivity.
Qed.

End AnnotationQualityFilterSpec.
