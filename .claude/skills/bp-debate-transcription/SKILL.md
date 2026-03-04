---
name: bp-debate-transcription
description: Transcribes British Parliamentary (BP) debate recordings into structured text. Triggers when processing debate audio/video, identifying speakers, or formatting debate transcripts.
user-invocable: false
---

# BP Debate Transcription

Provides project-specific conventions for transcribing British Parliamentary debate recordings into structured text.

## When to Apply

- Transcribing debate audio/video recordings
- Identifying and attributing speakers from debate recordings
- Formatting debate transcripts with POIs and speech boundaries

## Teams, Speakers, and Speech Order

| # | Speaker | Team |
|---|---|---|
| 1 | Prime Minister (PM) | Opening Government (OG) |
| 2 | Leader of Opposition (LO) | Opening Opposition (OO) |
| 3 | Deputy Prime Minister (DPM) | Opening Government (OG) |
| 4 | Deputy Leader of Opposition (DLO) | Opening Opposition (OO) |
| 5 | Member of Government (MG) | Closing Government (CG) |
| 6 | Member of Opposition (MO) | Closing Opposition (CO) |
| 7 | Government Whip (GW) | Closing Government (CG) |
| 8 | Opposition Whip (OW) | Closing Opposition (CO) |

Speeches alternate Gov/Opp. Speeches 1-4 are the opening half, 5-8 the closing half. Each speech is 7 minutes.

## Transcription Conventions

### Missing Speeches

Some speakers decline recording. When a speech is absent:
- Note explicitly: "Speech 3 — Deputy Prime Minister: not included in recording"
- Do **not** assume the speech didn't happen — it was delivered but not recorded
- Maintain correct numbering using the fixed order above, even when speeches are skipped

### Points of Information (POIs)

POIs are short interjections from the **opposing bench** during a speech.

- **Protected time** (no POIs): 0:00–1:00 and 6:00–7:00
- **Open time**: 1:00–6:00
- Only the opposite bench offers POIs — same-bench teams never POI each other
- **Clarifications**: brief POIs during the PM's speech only, about definitions/model/scope
- Mark POIs distinctly from the main speech. Identify the POI speaker if possible.

## Speaker Identification Heuristics

Use expected content patterns to verify speaker attribution:

- **PM (1)**: definitions, model (if policy), framing, initial arguments
- **LO (2)**: opposition framing, rebuttal to PM, counter-arguments
- **DPM (3)**: rebuttal to LO, rebuild PM's case, further analysis
- **DLO (4)**: rebuttal to DPM, rebuild LO's case, further analysis
- **MG (5)**: rebuttal to DLO, **extension** (new material distinct from OG)
- **MO (6)**: engagement with CG extension, **opposition extension** (new material distinct from OO)
- **GW (7)**: engagement with CO extension, rebuild CG extension, clash analysis. **No new arguments.**
- **OW (8)**: engagement with GW, rebuild CO extension, clash analysis. **No new arguments.**
