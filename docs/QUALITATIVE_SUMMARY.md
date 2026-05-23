# Qualitative Findings Summary

> **Template.** This file is a structured placeholder to be filled in
> from the thesis qualitative chapter. The headings reflect the
> structure a Karolinska reviewer will expect; each section has a
> prompt for what to write.

## Who was consulted

*Write: number of participants, their roles (e.g. compliance officer,
in-house lawyer, RegTech engineer), their organisations (anonymised if
needed), and recruitment method. If interviews were conducted under
the University of Bradford ethics approval, cite the approval number.*

Example:
> Six semi-structured interviews were conducted between [month] and
> [month] 2025. Participants were two compliance officers at UK
> retail banks, two in-house lawyers at fintech startups, and two
> RegTech engineers at consultancy firms. Recruitment was by direct
> outreach via LinkedIn. Ethics approval: UoB-CS-MSc-2025-XX.

## What questions were asked

*Write: the semi-structured interview guide. Include the seed
questions; the actual interviews diverged from these based on
participant responses.*

Example seed questions:
1. Walk me through the last time you used an LLM-based tool in your
   work. What worked? What didn't?
2. When you read a regulatory citation in an AI-generated answer, what
   do you do with it? Do you verify it, and if so, how?
3. If a tool flagged some citations as "verified" and others as "needs
   review", how would that change how you use the tool?
4. Which sourcebooks / Acts do you reach for most often? Which would
   you never use a third-party tool for?
5. How important is local-only processing for the documents you handle?

## What themes emerged

*Write: 3-6 themes from the thematic analysis. Each theme should have
a one-line statement and 1-2 illustrative quotes (anonymised).*

Example theme structure:

### Theme 1 — Citation accuracy beats fluency
*Participants consistently rated correct, specific citations as more
valuable than fluent or polished prose. A tool that produced a terse
correct answer with `FSMA 2000 s.19` was preferred to a tool that
produced a polished answer citing "the FCA Handbook".*

> "I'd rather the tool says 'I don't know' than make something up.
> The wrong citation is worse than no citation." — P3, compliance
> officer

### Theme 2 — Verification UI must be visible, not hidden
*Participants distrusted tools that did verification "behind the
scenes". They wanted explicit, per-claim provenance — every load-
bearing sentence visibly linked to its source.*

### Theme 3 — Local-only is a hard constraint for some workflows
*Two participants (the in-house lawyers) could not use any tool that
sent client documents to a cloud API. The other four could, conditional
on enterprise contracts.*

### Theme 4 — Sourcebook coverage priorities
*Participants prioritised, in order: FSMA 2000, FCA Handbook (COBS /
SYSC / PRIN), MLR 2017, PSR 2017, UK MAR, DTR. PRA-only sourcebooks
came up less often (only the compliance officers).*

### Theme 5 — Trust calibration over time
*Participants described needing to "calibrate trust" with a new tool
over the first few weeks of use — watching it succeed and fail on
known questions before relying on its output for novel ones. A clear
audit trail of past answers (with their verification status) would
support this calibration.*

### Theme 6 — Friction with mode switching
*The four-mode UI (general / finance / traffic-light / auto) was
appreciated, but participants asked for an explicit "finance Q&A" vs
"document review" distinction rather than relying on `auto` to pick.*

## How findings informed the system

| Finding | Design response |
|---|---|
| Citation accuracy beats fluency (Theme 1) | Strict citation post-processing (`find_invalid_citations`) + graph-grounded verification (`verify_answer`); warning footer for any unverified cite |
| Visible verification (Theme 2) | SSE `event:meta` envelope ships the full audit to the frontend; the warning footer is appended to the visible response body, not hidden |
| Local-only (Theme 3) | Ollama as the default generator; FAISS in-process for dense; Neo4j as a local Docker container; no cloud API in the chat path |
| Sourcebook priorities (Theme 4) | XML ingestion targets the five highest-priority documents; PDFs cover FCA Handbook coverage gaps; PRA included supplementarily |
| Trust calibration (Theme 5) | Per-answer audit metadata is structured (JSON) so a future feature could persist it for retrospective review |
| Mode switching (Theme 6) | Four explicit modes preserved; `auto` is the default but the dropdown lets users override |

## What did NOT make it into the system

*Be honest about features that came up in interviews but weren't built.*

Example:
- **Citation hover-cards.** Participants wanted to hover on `FSMA 2000
  s.19` in an answer and see the provision text inline. This is an
  obvious frontend feature that would consume the existing
  `verification.verified` list; the React frontend was kept minimal in
  the MSc scope but this is a top item for any next iteration.
- **Export-to-Word.** Compliance officers asked for the ability to
  paste the answer (with audit trail) into a Word document for review
  by senior colleagues. Not implemented; trivially possible with the
  current SSE audit envelope.
- **Per-domain authority weighting.** Participants suggested
  weighting FCA Handbook hits higher than retained EU MAR for some
  questions. The graph supports this via Regulator nodes; not wired
  into the retrieval ranking yet.

## Reliability of the findings

*Write: how thematic analysis was conducted (open coding, axial
coding, inter-rater agreement if any), the limitations of N=6, and
what would be needed for a follow-up study.*

Example:
> Thematic analysis followed Braun and Clarke (2006). All transcripts
> were openly coded once by the candidate; codes were grouped into the
> six themes above via axial coding. No second coder was available
> (single-developer MSc), which is a limitation; inter-rater agreement
> would be needed for a paper-quality study. The N=6 sample skews
> toward UK retail-bank compliance and fintech; insights about
> wholesale or insurance compliance are extrapolated, not directly
> evidenced.
