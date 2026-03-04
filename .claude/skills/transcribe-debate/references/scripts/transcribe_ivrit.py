#!/usr/bin/env python3
"""Transcribe debate audio using ivrit.ai faster-whisper model."""

from faster_whisper import WhisperModel
import json
import os
import time

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
OUTPUT_PATH = os.path.join(BASE_DIR, "tmp", "transcript_ivrit_ai_v2.json")
OUTPUT_TXT = os.path.join(BASE_DIR, "tmp", "transcript_ivrit_ai_v2.txt")

print("Loading ivrit-ai/faster-whisper-v2-d4 model...")
start = time.time()
model = WhisperModel("ivrit-ai/faster-whisper-v2-d4", device="cuda", compute_type="float16")
print(f"Model loaded in {time.time() - start:.1f}s")

print("Transcribing (this may take a while for ~58 min audio)...")
start = time.time()
segments, info = model.transcribe(AUDIO_PATH, language="he", beam_size=5, word_timestamps=True)

results = []
full_text_parts = []

for segment in segments:
    words_data = []
    if segment.words:
        for w in segment.words:
            words_data.append({
                "word": w.word.strip(),
                "start": round(w.start, 3),
                "end": round(w.end, 3),
                "probability": round(w.probability, 4),
            })
    seg_data = {
        "start": round(segment.start, 2),
        "end": round(segment.end, 2),
        "text": segment.text.strip(),
        "avg_logprob": round(segment.avg_logprob, 4),
        "no_speech_prob": round(segment.no_speech_prob, 4),
        "words": words_data,
    }
    results.append(seg_data)
    timestamp = f"[{int(segment.start//60):02d}:{int(segment.start%60):02d}]"
    full_text_parts.append(f"{timestamp} {segment.text.strip()}")
    # Print progress every ~5 minutes of audio
    if int(segment.end) % 300 < 5:
        print(f"  ...at {int(segment.end//60)}:{int(segment.end%60):02d}")

elapsed = time.time() - start
print(f"\nTranscription complete in {elapsed:.1f}s ({elapsed/60:.1f} min)")
print(f"Detected language: {info.language} (prob: {info.language_probability:.2f})")
print(f"Total segments: {len(results)}")

# Save JSON with segments
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump({"segments": results, "language": info.language, "duration": info.duration}, f, ensure_ascii=False, indent=2)

# Save plain text
with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
    f.write("\n".join(full_text_parts))

print(f"Saved JSON: {OUTPUT_PATH}")
print(f"Saved TXT:  {OUTPUT_TXT}")
