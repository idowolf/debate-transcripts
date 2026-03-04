# debate-transcripts

Transcribes British Parliamentary (BP) debate recordings from YouTube into structured Hebrew transcripts using dual ASR and Claude subagent merging.

## What This Does

Given a YouTube URL for a BP debate recorded in Hebrew, the pipeline produces a clean, timestamped `output/transcript_unified.md` with all 8 speeches, speaker attribution, and Point of Information (POI) annotations.

## Pipeline Overview

```
YouTube URL
    │
    ├── parse_description.py   → debate metadata (motion, teams, speakers, panel)
    ├── yt-dlp                 → WAV audio
    │
    ├── transcribe_ivrit.py    → ivrit.ai faster-whisper-v2-d4 (GPU, ~14 min)
    ├── transcribe_elevenlabs.py → ElevenLabs Scribe v1 with speaker diarization
    │
    ├── prepare_speech_data.py → 8 per-speech JSON files in tmp/speeches/
    │
    ├── 8× speech-merger agent → merged Hebrew text per speech (tmp/speeches/)
    ├── 1× poi-detector agent  → detected POIs (tmp/speeches/detected_pois.json)
    │
    └── assemble               → output/transcript_unified.md
```

Both ASR engines produce imperfect transcripts. `speech-merger` subagents combine them using word-level confidence scores and Hebrew language understanding to produce the most accurate text possible.

## Prerequisites

- Python 3.10+
- `yt-dlp` on PATH
- Python packages: `faster-whisper`, `elevenlabs`, `python-dotenv`
- CUDA GPU for ivrit.ai transcription
- ElevenLabs API key

## Setup

1. Copy the environment template and fill in your API key:
   ```bash
   cp .claude/skills/transcribe-debate/references/.env.example \
      .claude/skills/transcribe-debate/references/.env
   # Edit .env and set ELEVENLABS_API_KEY=your_key_here
   ```

2. Install Python dependencies:
   ```bash
   pip install faster-whisper elevenlabs python-dotenv
   ```

3. Install yt-dlp:
   ```bash
   pip install yt-dlp
   # or: brew install yt-dlp
   ```

## Usage

Run the full pipeline with the Claude Code skill:

```
/transcribe-debate <youtube_url>
```

Claude will orchestrate each step, skipping stages whose output already exists in `tmp/`. To re-run a specific stage, delete its output file from `tmp/`.

### Running Stages Manually

```bash
SCRIPTS=.claude/skills/transcribe-debate/references/scripts

# 1. Parse metadata
python $SCRIPTS/parse_description.py <url> --json > tmp/debate_metadata.json

# 2. Download audio
yt-dlp -x --audio-format wav -o tmp/debate_audio.wav <url>

# 3. Transcribe (requires GPU for ivrit.ai)
python $SCRIPTS/transcribe_ivrit.py
python $SCRIPTS/transcribe_elevenlabs.py

# 4. Prepare per-speech data
python $SCRIPTS/prepare_speech_data.py
```

Steps 5–6 (subagent merge + assembly) are run by Claude via `/transcribe-debate`.

## Output

`output/transcript_unified.md` — full debate transcript with:
- Debate header (motion, speakers table, panel, results)
- 8 speech sections with timestamps and speaker attribution
- POI annotations inserted at their timestamps

## Project Structure

```
debate-transcripts/
├── .claude/
│   ├── agents/
│   │   ├── speech-merger.md        # Merges two ASR sources for one speech
│   │   └── poi-detector.md         # Detects POIs from diarization data
│   └── skills/
│       ├── bp-debate-transcription/SKILL.md  # Shared BP format knowledge
│       └── transcribe-debate/
│           ├── SKILL.md            # Main pipeline skill
│           └── references/
│               ├── .env            # API keys (gitignored)
│               ├── .env.example    # Template
│               └── scripts/        # Python pipeline scripts
├── output/                         # Final transcripts (gitignored)
├── tmp/                            # Intermediate artifacts (gitignored)
├── .gitignore
└── README.md
```

## Credits

Hebrew ASR provided by [ivrit.ai](https://ivrit.ai). If you use this project in academic work, please cite:

```bibtex
@inproceedings{marmor2025building,
  title={Building an Accurate Open-Source Hebrew ASR System through Crowdsourcing},
  author={Marmor, Yanir and Lifshitz, Yair and Snapir, Yoad and Misgav, Kinneret},
  booktitle={Proc. Interspeech 2025},
  pages={723--727},
  year={2025}
}
```
