# CUA-Gym cohort 42 historical replay archive

This directory preserves the accepted historical reference states required to
replay the 42 published Web seed projections after the donor worktree is
removed. It is evidence and provenance only; it is not runtime configuration
and does not define a separate Web application category.

## Archived run

- Original run: `cua-state-reference-cohort42-20260901-002`
- Original source: `surfgym-cua-webapp-onboarding/output/`
- Archive root passed to verifiers: `archive-root/`
- Reference state files: 126 files, 2,579,303 bytes
- Replay map SHA-256:
  `ee0e64c2548a4bcf789c10a60016640336fdedd93c478b335a7aea696aef801a`
- Replay report SHA-256:
  `64e12b5b1b95965e4df96101ce37a8537e5484df2ecdada80279d0d95848faa8`
- Reference-tree aggregate SHA-256:
  `ab68c28ae64e15cb29ab67ba76b7daaa87d705c0949f3485b5424b0ee8320294`

The reference-tree aggregate is SHA-256 over the lowercase SHA-256 of each
file, joined by LF with no trailing LF, in ascending slash-normalized relative
path order.

## Verification boundary

The canonical replay verifier passes 42/42 tasks and 157/157 terminal
criteria from these stored states. The binary Web task-DB verifier passes 81
unique Web tasks and all 42 archived projections. These are historical replay
and static binary checks, not fresh headed-CUA acceptance, runtime capacity, or
worker end-to-end evidence.
