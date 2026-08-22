# Impress seed ↔ OSWorld coverage map

Seed filenames are content-based by design (no OSWorld UUID or hash in the
filename). This file is the only place that ties a seed back to the OSWorld
task it mirrors. Canvas is always `1.pptx` (24 slides) — tasks are redesigned
to fit its content rather than replaying the original OSWorld PPTX, to avoid
benchmark contamination. See the design rationale in the SH-Wiki vault:
`20_Atlas/Projects/OSWorld/Notes/Task/Impress/Impress 능력 확장 설계.md`.

## 가능 8 — direct structural mirror (계단 0)

| seed | OSWorld id | mirrored pattern |
|---|---|---|
| `stacked_boxes_color_order.json` | `04578141` | N boxes, top-to-bottom distinct named colors |
| `alignment_lab_reassign.json` | `05dd4c1d` | N targets, each gets a distinct paragraph alignment |
| `focus_phrase_size_pass.json` | `3161d64e` | two boxes on one slide, two distinct font sizes |
| `font_lab_unify_family.json` | `358aa0a7` | unify font across many boxes without per-box selection |
| `title_black_underline_three_slides.json` | `4ed5abd0` | same two-property change applied to titles across several slides |
| `color_palette_all_yellow.json` | `57667013` | every labeled box on one slide gets the same exact color |
| `cover_slide_bold_and_title_emphasis.json` | `5c1a6c3d` | bold every box on a slide, then size+underline the title |
| `closing_slide_font_unify.json` | `edb61b14` | unify font across one slide (last slide in the original) |

## 계단 1 capability mirrors (background / layout region / strikethrough / exact color)

`impress_evaluate.py` now supports `("background","color")` (slide-level, 3-step
write + master-page fallback read), `("layout","verticalRegion"/"horizontalRegion"/"heightCm")`
(discrete position/size on a text-bearing shape), `("style","strikethrough")`,
and exact (non-nearest-match) color observation. A `["placeholder", kind]`
query selector (`title`/`body`/`subtitle`/`slideNumber` via `supportsService`)
was also built, but **`1.pptx` declares zero OOXML placeholders anywhere — no
slide, the one layout, or the one master** (verified by scanning every
`ppt/slides/slideN.xml` for `<p:ph>`). The selector is correct UNO but has
nothing to match on this canvas, so it is unused by any seed below.

| seed | mirrors | OSWorld id | notes |
|---|---|---|---|
| `cover_slide_green_background.json` | single-slide background | `9cf05d24` | 1 state, atomic like the original |
| `multi_slide_blue_background.json` | background across several slides | `3b27600c` | 4 of 24 slides, not literally "all" |
| `palette_notes_background_matches_title.json` | background matches a chosen title's color | `70bca0cc` | values pinned by us, not read-back-and-matched |
| `photo_slide_yellow_and_title_bold.json` | background on the photo slide + separate title formatting | `0a211154` | title **bold**, not text replacement — see below |
| `background_contrast_intro_and_bg_red.json` | textbox size+color + slide background | `a434992a` | full mirror |
| `moveable_title_to_bottom.json` | move a heading to the bottom region | `15aece23` | uses `layout.verticalRegion`, not EMU coordinates |
| `checklist_strike_two_items.json` | strike-through two list items | `550ce7e7` | was 불가, now full via A |
| `body_underline_all_text_dark_red_two.json` | body-only underline plus title/body/table Dark Red 2 | `986fc832` | one terminal seed: text-body underline is isolated with `textboxIndex`, slide text and native table cells both read `darkred2` |

## Ladder 2 capability mirrors (speaker notes / bullets / indentation)

`impress_evaluate.py` supports the presentation's `NotesShape` through the
slide-only `("notes", "text")` path. Paragraph operations are resolved against
the selected text shape: `("paragraph", "bullet")` creates a standard bullet
numbering rule, and `("paragraph", "indentCm")` reads/writes the first paragraph's
left margin in centimetres.

| seed | mirrors | OSWorld id | notes |
|---|---|---|---|
| `notes_copy_cover_title.json` | copy title text into speaker notes | `7dbc52a6` | title boldness is already present on the shared canvas |
| `notes_app_with_purple_background.json` | APP notes + purple background | `841b50aa` | combined notes/background state |
| `notes_title_with_purple_background.json` | title notes + purple background | `8979838c` | combined notes/background state |
| `cover_title_bullet.json` | apply bullet paragraph formatting | `f23acfd2` | standard UNO bullet rule |
| `planning_paragraph_indent.json` | apply 1.5 cm paragraph indent | `a669ef01` | stores centimetres, not raw UNO units |

## Ladder 3 capability mirrors (transition / configuration / object deletion)

`impress_evaluate.py` now reads and writes a slide's `TransitionType`, the
LibreOffice `PresenterScreen` and `Recovery` configuration nodes, and stable
slide-local UNO shape names. Object deletion is evaluated as the resilient
negative predicate `("object", "exists") == false`: missing targets resolve
cleanly instead of aborting evaluation.

| seed | mirrors | OSWorld id | notes |
|---|---|---|---|
| `cover_slide_dissolve_transition.json` | slide-1 Dissolve transition | `21760ecb` | `TransitionType.DISSOLVE` |
| `title_style_and_personal_image_remove.json` | black/bold titles plus real pre-seeded image deletion | `a53f80cd` | `setup_operations` inserts the evaluator-owned image before UI entry; final seed evaluates both title styles and its absence |
| `presenter_console_disable.json` | disable Presenter Console | `0f84bef9` | `Presenter/StartAlways=false` |
| `autosave_three_minutes.json` | enable AutoSave at 3 minutes | `2cd43775` | `Recovery/AutoSave/TimeIntervall=3` |

## Ladder 4 capability mirrors (native tables)

Native tables are identified by `ShapeType == "com.sun.star.drawing.TableShape"`.
Their rows, columns, and cells are accessed through `shape.Model` (`XTable`),
not through the shape object itself. The shared canvas has no initial table, so
each mirror creates the table as its first terminal operation.

| seed | mirrors | OSWorld id | notes |
|---|---|---|---|
| `features_table_five_by_two.json` | create a 5×2 native table | `39be0d19` | table creation is terminally observable |
| `table_header_t1_t4.json` | set four first-row cell texts | `5cfb9197` | redesigned on slide 1 |
| `table_move_bottom.json` | move native table to bottom region | `ac1b39ff` | uses existing discrete layout evaluator |

## Ladder 5 capability mirrors (slide collection)

The evaluator supports one-page duplication through `XDrawPageDuplicator`,
portrait orientation by swapping each page's dimensions, and native summary
slides as an appended `DrawPage` with two named `TextShape` objects.  The
summary command is not exposed in this LibreOffice build's Slide menu, so the
writer produces the same observable native slide structure directly.

| seed | mirrors | OSWorld id | notes |
|---|---|---|---|
| `summary_slide_titles.json` | create one summary slide with ordered titles | `af23762e` | exact title-list readback |
| `portrait_orientation.json` | set every slide to portrait | `ce88f674` | page Width < Height |
| `duplicate_last_two_alternating.json` | duplicate two pages in A/B/A'/B' order | `9ec204e4` | appends native copies of the final A/B pair, producing A/B/A'/B'; live E2E passed |

## Text-edit mirrors — stable selector completion

`08aced46`, `af2d657a`, `b8adbc24`, `73c99fb9` all require **changing a
textbox's text and then also asserting something about that same shape**. They
now use the stable 1-based `textboxIndex` selector and have live E2E seeds.
`("style","text")` read/write works (see `test_32_impress_capability_extensions.py`),
The following records the superseded selector limitation:

- The `placeholder` selector can't be used — no placeholders exist on this canvas (see above).
- The `textbox` selector matches by exact current text. Once the agent edits
  the text, a criterion still keyed to the *original* text can no longer find
  the shape (`select_textbox_record` → `fail("textbox not found")`), which
  aborts the whole UNO evaluate call rather than cleanly scoring 0.
- A criterion keyed to the *new* text (self-referential existence check) works
  for the success case, but on the failure case ("agent did nothing") it hits
  the same hard failure instead of a clean 0 — worse failure semantics than
  every other capability in this file.

The historical fix required either: promoting some canvas shapes to real Title/Content
placeholders (fixture asset edit, still zero code), or a stable non-text
selector (`["shape", {"index": n}]` or similar — new capability, out of scope
for this pass). Tracked as a follow-up in `Impress 능력 확장 설계.md`.

`ac9bb6cb` (slide-number color) is handled without relying on an OOXML
placeholder: `("slideNumber", "color")` creates a native `SlideNumberShape`
when missing. Its live setup/reference/evaluate/release cycle returned `red`
for slide 3.

## Headed-CUA contract repair status (2026-08-17)

The remaining task-local CUA contract defects were repaired without changing
shared evaluator semantics. Seed selectors now target the native object the GUI
actually edits, missing images and the native slide number are created during
setup, false imported-image identity leaves were removed, and the shared PPTX
Notes master has matching non-zero placeholders.

The 46 reviewed non-excluded original tasks now classify as 44 full headed-CUA
passes, one expected infeasible (`af23762e`), and one CUA-only path failure
(`ac1b39ff`). `ef9d12bd` remains explicitly excluded. `a434992a` was
reclassified as a pass after complete-sentence selection produced 12 pt; it did
not require an implementation change.

Detailed current evidence is in
`surfgym-docker-served-fixture/output/playwright/cua-contract-repair/CUA_CONTRACT_REPAIR_RESULT.md`.

## Ladder 6 capability mirrors (exact media assets)

The fixture stages evaluator-owned source assets under
`/data/fixtures/impress/media/`. Images are identified from native
`GraphicStream` SHA-256 bytes rather than the misleading `GraphicURL`
property, which LibreOffice exposes as an `XGraphic`. Audio accepts both
reference-created file URLs and UI-created embedded package URLs.

| seed | mirrors | OSWorld id | notes |
|---|---|---|---|
| `insert_none_image_one_cm.json` | insert the original `none.png` at 1 cm by 1 cm | `c82632a4` | image bytes plus exact independent width/height checks |
| `embed_baseball_audio.json` | embed original `Baseball.mp3` | `c59742c0` | accepts `MediaShape` file or embedded package representation; browser CUA insertion read back `Baseball.mp3` |
| `photo_album_six_blank_slides.json` | create six blank picture slides, `pic1.png` through `pic6.png` in order | `bf4e9888` | native `GraphicObjectShape` on each slide; ordered hash-backed readback |

Live E2E for the slide collection verifier observed the canonical album sequence
`["pic1.png", "pic2.png", "pic3.png", "pic4.png", "pic5.png", "pic6.png"]`
after `setup -> reference -> evaluate -> release`. The browser CUA path also
created a new presentation, added the six staged files through Insert > Media
> Photo Album, removed the initial blank slide, and returned the same evaluator
observation. Evidence: `surfgym-docker-served-fixture/.playwright-cli/page-2026-08-09T20-09-37-802Z.png`.

## Ladder 7 capability mirrors (file artifacts)

| seed | mirrors | OSWorld id | rule-based observation |
|---|---|---|---|
| `export_current_slide_png.json` | export the current presentation as Desktop `res.png` using default PNG settings | `455d3c66` | valid PNG signature and CRCs, RGBA 8-bit, non-interlaced 1280×720 default UI output |
| `save_presentation_as_pre_pptx.json` | save the current presentation as Desktop `pre.pptx` | `a097acff` | valid PPTX package and the same slide count as the open presentation |

Each Impress setup removes only these two evaluator-owned Desktop names before
opening a task, preventing a previous run's output from satisfying a later
evaluation. `scripts/verify_impress_artifacts.py` passed two live
`setup -> reference -> evaluate -> release` cycles with observations
`["res.png"]` and `["pre.pptx"]`. Browser CUA separately passed real File →
Export → PNG (default options) and File → Save As flows; the evaluator returned
`["res.png"]` and `["pre.pptx"]` in those same sessions. Evidence:
`surfgym-docker-served-fixture/.playwright-cli/page-2026-08-09T21-00-12-844Z.png`
and `page-2026-08-09T20-45-40-167Z.png`.

## Image-layout selector completion (remaining direct mirrors)

The slide-local `image` selector addresses visible
`com.sun.star.drawing.GraphicObjectShape` objects in document order. It is
deliberately separate from `shapeName`: a real user-created image has no
evaluator-owned name. `layout.cover` preserves the image aspect ratio, scales
to cover both slide dimensions, and centers the result; its read rule checks
those observable geometry conditions.

| seed | mirrors | OSWorld id | rule-based observation |
|---|---|---|---|
| `move_slide_two_image_right.json` | move Slide 2 image to right region | `2b94c692` | `image:1` horizontal region is `right` |
| `cover_slide_one_image.json` | centered proportional cover image | `5d901039` | `image:1` covers the page and is centered |
| `resize_images_heights.json` | image heights on slides 3, 4, 6 | `7ae48c60` | 20.0, 30.0, 25.0 cm |

`scripts/verify_impress_image_layouts.py` passed all three live
`setup -> reference -> evaluate -> release` cycles. Observations were
`["none.png", "right"]`, `["none.png", true]`, and
`["none.png", "none.png", "none.png", 20.0, 30.0, 25.0]`.
Browser CUA separately used the native Insert > Image file chooser to add
`pic1.png`, then dragged the selected image into the right third of the
actual Impress canvas. Evidence:
`surfgym-docker-served-fixture/.playwright-cli/page-2026-08-09T21-19-37-532Z.png`.

## Pre-existing 16 seeds (schema-fixed, not UUID-mapped)

These predate this coverage effort. They share a *skill* with one or more of
the 8 above (color/bold/underline/alignment/font-family on named textboxes)
but were not built as literal structural mirrors of a specific OSWorld task,
so they are kept as additional training seeds rather than back-mapped here.

`agenda_cards_right_align`, `audience_cards_bold_size12`,
`bottom_note_italic_red`, `checklist_cards_liberation_sans_narrow`,
`compare_contrast_title_size44_purple`, `concept_map_title_underline_green`,
`dark_red_2_swatch_underline_size22`, `draft_labels_label_bold_size14`,
`focus_phrase_underline_green`, `quote_paraphrase_headings_underline_black`,
`revision_check_size_center`, `similarity_difference_center_align`,
`step_cards_color_green_red_blue`, `title_bold_and_change`,
`transition_checks_heading_times_underline`, `workspace_cue_orange_bold`

## Original-task completion audit (2026-08-10)

`ORIGINAL_TASK_AUDIT.md` maps every original UUID to its seed and live Docker
evidence. All 46 non-panel tasks have a passing seed in bounded
setup-reference-evaluate-release audit batches. The left-panel task
`ef9d12bd` remains the explicit spike exclusion.
