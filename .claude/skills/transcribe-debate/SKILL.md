---
name: transcribe-debate
description: End-to-end pipeline that transcribes a BP debate from YouTube — downloads audio, runs dual ASR (ivrit.ai + ElevenLabs), merges with subagents, and assembles a unified Hebrew transcript.
user-invocable: true
---

# Transcribe Debate

Runs the full pipeline from YouTube URL to unified Hebrew transcript.

**Invocation:** `/transcribe-debate <youtube_url>`

## Overview

The pipeline produces `output/transcript_unified.md` from a YouTube URL by:
1. Parsing debate metadata from the video description
2. Downloading audio
3. Transcribing with two ASR engines (ivrit.ai + ElevenLabs)
4. Preparing per-speech data from the combined transcripts
5. Merging the two sources in parallel with subagents
6. Assembling the final unified transcript

All intermediate files go to `tmp/` (gitignored). Final output goes to `output/`.

---

## Prerequisites

- `yt-dlp` installed and on PATH
- `python3` with packages: `faster-whisper`, `elevenlabs`, `python-dotenv`
- CUDA GPU available for ivrit.ai transcription (~14 min for 58 min audio)
- `.claude/skills/transcribe-debate/references/.env` with `ELEVENLABS_API_KEY=...`

---

## Variables

```
SCRIPTS=.claude/skills/transcribe-debate/references/scripts
URL=<youtube_url>
```

---

## Pipeline Steps

### Step 1: Parse debate metadata

```bash
python $SCRIPTS/parse_description.py $URL --json > tmp/debate_metadata.json
```

Verify: `tmp/debate_metadata.json` contains `motion`, `teams` (OG/OO/CG/CO), `speakers` (8 entries), `panel`.

**Skip if:** `tmp/debate_metadata.json` already exists.

---

### Step 2: Download audio

```bash
yt-dlp -x --audio-format wav -o tmp/debate_audio.wav $URL
```

Note: yt-dlp may append `.wav` or not depending on the source format. Check that `tmp/debate_audio.wav` exists after the command.

**Skip if:** `tmp/debate_audio.wav` already exists.

---

### Step 3a: Transcribe with ivrit.ai

> **Requires CUDA GPU.** This step takes ~14 minutes for a 58-minute debate. Do not run in Claude's environment — run on a GPU machine.

```bash
python $SCRIPTS/transcribe_ivrit.py
```

Output: `tmp/transcript_ivrit_ai_v2.json`, `tmp/transcript_ivrit_ai_v2.txt`

**Skip if:** `tmp/transcript_ivrit_ai_v2.json` already exists.

---

### Step 3b: Transcribe with ElevenLabs

```bash
python $SCRIPTS/transcribe_elevenlabs.py
```

Requires `ELEVENLABS_API_KEY` in `references/.env`. Uploads the WAV to ElevenLabs Scribe v1 with speaker diarization.

Output: `tmp/transcript_elevenlabs.json`, `tmp/transcript_elevenlabs.txt`

**Skip if:** `tmp/transcript_elevenlabs.json` already exists.

---

### Step 4: Prepare per-speech data

```bash
python $SCRIPTS/prepare_speech_data.py
```

Reads `tmp/transcript_ivrit_ai_v2.json`, `tmp/transcript_elevenlabs.json`, and optionally `tmp/debate_metadata.json`. Auto-detects speech boundaries from ElevenLabs speaker diarization.

Output:
- `tmp/speeches/speech_1.json` … `tmp/speeches/speech_8.json`
- `tmp/speeches/speaker_changes.json`
- `tmp/speeches/debate_metadata.json`

**Skip if:** `tmp/speeches/speech_1.json` through `tmp/speeches/speech_8.json` all exist.

---

### Step 5: Launch subagents in parallel

Launch **9 subagents in parallel** using the Agent tool:

**8 speech-merger agents** (one per speech):
- Agent type: `speech-merger`
- Prompt: `Process speech N. Read tmp/speeches/speech_N.json and merge the two transcript sources. Write the result to tmp/speeches/speech_N_merged.md.`

**1 poi-detector agent**:
- Agent type: `poi-detector`
- Prompt: `Detect POIs in this debate. Read tmp/speeches/speaker_changes.json and tmp/speeches/debate_metadata.json. Write results to tmp/speeches/detected_pois.json.`

Wait for all 9 agents to complete before proceeding.

**Skip individual speeches** where `tmp/speeches/speech_N_merged.md` already exists. **Skip poi-detector** if `tmp/speeches/detected_pois.json` already exists.

---

### Step 6: Assemble final transcript

Read:
- `tmp/speeches/debate_metadata.json` — for header metadata
- `tmp/speeches/detected_pois.json` — for POI insertions
- All 8 `tmp/speeches/speech_N_merged.md` files

Write `output/transcript_unified.md` with this structure:

```markdown
# תמלול דיבייט: [motion from metadata]

> מקור: [YouTube URL]
>
> תמלול בסיס: ivrit.ai faster-whisper-v2-d4
> תיקונים: ElevenLabs Scribe v1
> מיזוג: Claude subagent pipeline

| # | תפקיד | צוות | דובר/ת |
|---|--------|------|---------|
| 1 | ראש ממשלה (PM) | פתיחת ממשלה (OG) | [name] |
| ... | ... | ... | ... |

**פאנל:** [panel names]
**תוצאות:** [results]

---

## נאום 1 — ראש ממשלה (PM)
**פתיחת ממשלה (OG)** — [speaker name]

[content from speech_1_merged.md]

[POIs inserted at correct positions, formatted as:]
> **[POI MM:SS]** [POI text if available]

---

## נאום 2 — ...
```

Insert POIs from `detected_pois.json` at the correct positions within each speech's merged text, using the `time` field to place them in the right paragraph.

---

### Step 7: Verify output

1. Check all 8 speeches are present in `output/transcript_unified.md`
2. Verify POIs appear at the expected timestamps
3. Report total line count and any issues

---

## Notes

- **Re-runs are safe**: Each step checks for existing output before running. To re-run a specific step, delete its output file(s) from `tmp/`.
- **ivrit.ai GPU requirement**: Step 3a cannot run in Claude's environment. If the GPU transcript is missing, prompt the user to run `transcribe_ivrit.py` manually on a GPU machine.
- **Partial failures**: If a speech-merger subagent fails, re-run it individually. The assembler in Step 6 can proceed with available speeches.
- **Audio format**: yt-dlp downloads as WAV. Some videos may produce a `.wav.wav` double extension — check and rename if needed.
