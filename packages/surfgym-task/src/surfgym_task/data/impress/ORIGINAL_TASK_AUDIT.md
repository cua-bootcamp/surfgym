# Original Impress task audit

This is the completion ledger for the 47 original OSWorld Impress tasks. One
task, `ef9d12bd`, is intentionally excluded as the left-panel spike; the
remaining target is 46. A seed marked **passed** completed a real local
SurfGym `setup -> reference -> evaluate -> release` cycle on 2026-08-10.

## Current result

- All current criteria seeds passed bounded Docker E2E. The original eight
  batches produced 63/64; the revised deletion seed and the two changed
  semantic seeds were then rerun successfully, and the newly added combined
  underline/table-color seed also passed. Current coverage: **65/65 passed**.
- The deletion seed supplies a real `none.png` target through its encoded
  `setup_operations` before the browser session opens; its terminal evaluator
  now observes only the five requested final properties.
- The 46 non-panel original tasks are all represented by a passing seed.

## Mapping

| Original id | Seed / evidence | Status |
| --- | --- | --- |
| `04578141` | `stacked_boxes_color_order.json` | passed |
| `05dd4c1d` | `alignment_lab_reassign.json` | passed |
| `08aced46` | `slide_two_note_title.json` | passed |
| `0a211154` | `photo_slide_yellow_and_title_bold.json` | passed |
| `0f84bef9` | `presenter_console_disable.json` | passed |
| `15aece23` | `moveable_title_to_bottom.json` | passed |
| `21760ecb` | `cover_slide_dissolve_transition.json` | passed |
| `2b94c692` | `move_slide_two_image_right.json` | passed |
| `2cd43775` | `autosave_three_minutes.json` | passed |
| `3161d64e` | `focus_phrase_size_pass.json` | passed |
| `358aa0a7` | `font_lab_unify_family.json` | passed |
| `39be0d19` | `features_table_five_by_two.json` | passed |
| `3b27600c` | `multi_slide_blue_background.json` | passed |
| `455d3c66` | `export_current_slide_png.json` | passed |
| `4ed5abd0` | `title_black_underline_three_slides.json` | passed |
| `550ce7e7` | `checklist_strike_two_items.json` | passed |
| `57667013` | `color_palette_all_yellow.json` | passed |
| `5c1a6c3d` | `cover_slide_bold_and_title_emphasis.json` | passed |
| `5cfb9197` | `table_header_t1_t4.json` | passed |
| `5d901039` | `cover_slide_one_image.json` | passed |
| `70bca0cc` | `palette_notes_background_matches_title.json` | passed |
| `73c99fb9` | `slide_two_content_page_one.json` | passed |
| `7ae48c60` | `resize_images_heights.json` | passed |
| `7dbc52a6` | `notes_copy_cover_title.json` | passed |
| `841b50aa` | `notes_app_with_purple_background.json` | passed |
| `8979838c` | `notes_title_with_purple_background.json` | passed |
| `986fc832` | `body_underline_all_text_dark_red_two.json` | passed |
| `9cf05d24` | `cover_slide_green_background.json` | passed |
| `9ec204e4` | `duplicate_last_two_alternating.json` | passed |
| `a097acff` | `save_presentation_as_pre_pptx.json` | passed |
| `a434992a` | `background_contrast_intro_and_bg_red.json` | passed |
| `a53f80cd` | `title_style_and_personal_image_remove.json` | passed |
| `a669ef01` | `planning_paragraph_indent.json` | passed |
| `ac1b39ff` | `table_move_bottom.json` | passed |
| `ac9bb6cb` | `slide_three_page_number_red.json` | passed |
| `af23762e` | `summary_slide_titles.json` | passed |
| `af2d657a` | `happy_family_title_font.json` | passed |
| `b8adbc24` | `online_shopping_title.json` | passed |
| `bf4e9888` | `photo_album_six_blank_slides.json` | passed |
| `c59742c0` | `embed_baseball_audio.json` | passed |
| `c82632a4` | `insert_none_image_one_cm.json` | passed |
| `ce88f674` | `portrait_orientation.json` | passed |
| `e4ef0baf` | `picture_height_and_all_text_size.json` | passed |
| `ed43c15f` | `picture_top_and_all_text_underline.json` | passed |
| `edb61b14` | `closing_slide_font_unify.json` | passed |
| `f23acfd2` | `cover_title_bullet.json` | passed |
| `ef9d12bd` | left-panel spike | excluded |

## Reproducible audit command

Run bounded seed batches with:

```powershell
.\.venv\Scripts\python.exe .\scripts\audit_impress_seed_e2e.py <seed names>
```

The runner fails a seed if any final observed criterion differs from the
seed's expected value and always releases the allocated SurfGym slot.
