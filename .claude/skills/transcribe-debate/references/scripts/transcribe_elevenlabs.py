#!/usr/bin/env python3
"""Transcribe debate audio using ElevenLabs Scribe API."""

import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

api_key = os.environ.get("ELEVENLABS_API_KEY")
if not api_key:
    print("ERROR: ELEVENLABS_API_KEY not found. Create a .env file with your key.")
    exit(1)

from elevenlabs import ElevenLabs

BASE_DIR = os.path.dirname(  # debate-transcripts/
    os.path.dirname(          # .claude/
        os.path.dirname(      # skills/
            os.path.dirname(  # transcribe-debate/
                os.path.dirname(  # references/
                    os.path.abspath(__file__)  # scripts/
                )
            )
        )
    )
)

AUDIO_PATH = os.path.join(BASE_DIR, "tmp", "debate_audio.wav")
OUTPUT_PATH = os.path.join(BASE_DIR, "tmp", "transcript_elevenlabs.json")
OUTPUT_TXT = os.path.join(BASE_DIR, "tmp", "transcript_elevenlabs.txt")

client = ElevenLabs(api_key=api_key)

print("Uploading and transcribing with ElevenLabs Scribe v1...")
print(f"Audio file: {AUDIO_PATH}")
start = time.time()

with open(AUDIO_PATH, "rb") as audio_file:
    result = client.speech_to_text.convert(
        file=audio_file,
        model_id="scribe_v1",
        language_code="he",
        diarize=True,
        timestamps_granularity="word",
        tag_audio_events=True,
    )

elapsed = time.time() - start
print(f"Transcription complete in {elapsed:.1f}s ({elapsed/60:.1f} min)")

# Convert to serializable dict
result_dict = json.loads(result.json()) if hasattr(result, 'json') else result.__dict__

# Save full JSON response
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(result_dict, f, ensure_ascii=False, indent=2)

# Build plain text with timestamps and speaker labels
text_parts = []
if hasattr(result, 'words') and result.words:
    current_speaker = None
    current_line = []
    current_start = None

    for word in result.words:
        speaker = getattr(word, 'speaker_id', None)
        if speaker != current_speaker and current_line:
            timestamp = f"[{int(current_start//60):02d}:{int(current_start%60):02d}]"
            speaker_label = f"Speaker {current_speaker}" if current_speaker is not None else ""
            text_parts.append(f"{timestamp} {speaker_label}: {' '.join(current_line)}")
            current_line = []

        if not current_line:
            current_start = getattr(word, 'start', 0)
            current_speaker = speaker

        text = getattr(word, 'text', str(word))
        current_line.append(text)

    # Flush last line
    if current_line:
        timestamp = f"[{int(current_start//60):02d}:{int(current_start%60):02d}]"
        speaker_label = f"Speaker {current_speaker}" if current_speaker is not None else ""
        text_parts.append(f"{timestamp} {speaker_label}: {' '.join(current_line)}")
elif hasattr(result, 'text'):
    text_parts.append(result.text)

with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
    f.write("\n".join(text_parts))

print(f"Saved JSON: {OUTPUT_PATH}")
print(f"Saved TXT:  {OUTPUT_TXT}")
print(f"Text preview (first 500 chars): {result.text[:500] if hasattr(result, 'text') else 'N/A'}")
