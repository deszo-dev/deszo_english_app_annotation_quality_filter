# Stanza input alignment note

This package was updated to consume the current `stanza_annotator.v2.0` output shape.

Key migration points:

- Chapter body annotations are read from `document.book.chapters[].text_annotation`.
- `document.book.chapters[].paragraphs` is forbidden in production Stanza input and output.
- Front/back matter `section.paragraphs[]` are structural pass-through only and are not annotation targets.
- Quality refs now use Stanza text-unit kinds: `chapter_text`, `section_text`, `chapter_title`, `section_title`, and `footnote`.
- Legacy quality refs such as `chapter_paragraph` and `front_matter_paragraph` are invalid.
