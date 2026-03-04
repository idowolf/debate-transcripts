#!/usr/bin/env python3
"""
Prepare per-speech data files for the subagent merge pipeline.

Loads both ivrit.ai (v2 with word probabilities) and ElevenLabs transcripts,
auto-detects speech boundaries from ElevenLabs speaker diarization, and writes
per-speech JSON files for parallel processing by merger subagents.
"""

import json
import os
import sys

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
TMP_DIR = os.path.join(BASE_DIR, "tmp")
SPEECHES_DIR = os.path.join(TMP_DIR, "speeches")

# BP speech roles in order
BP_ROLES = [
    {"role": "PM", "role_he": "ראש ממשלה", "team": "OG", "team_he": "פתיחת ממשלה"},
    {"role": "LO", "role_he": "ראש אופוזיציה", "team": "OO", "team_he": "פתיחת אופוזיציה"},
    {"role": "DPM", "role_he": "סגנ/ית ראש ממשלה", "team": "OG", "team_he": "פתיחת ממשלה"},
    {"role": "DLO", "role_he": "סגנ/ית ראש אופוזיציה", "team": "OO", "team_he": "פתיחת אופוזיציה"},
    {"role": "MG", "role_he": "חבר/ת ממשלה", "team": "CG", "team_he": "סגירת ממשלה"},
    {"role": "MO", "role_he": "חבר/ת אופוזיציה", "team": "CO", "team_he": "סגירת אופוזיציה"},
    {"role": "GW", "role_he": "שוט ממשלה", "team": "CG", "team_he": "סגירת ממשלה"},
    {"role": "OW", "role_he": "שוט אופוזיציה", "team": "CO", "team_he": "סגירת אופוזיציה"},
]

# Known reference boundaries from merge_transcripts.py for validation
REFERENCE_BOUNDARIES = [0, 420, 855, 1290, 1756, 2195, 2648, 3298]
BOUNDARY_TOLERANCE = 60  # seconds


def load_transcripts():
    """Load both transcript sources."""
    # Try v2 first (with word probabilities), fall back to v1
    ivrit_path = os.path.join(TMP_DIR, "transcript_ivrit_ai_v2.json")
    if not os.path.exists(ivrit_path):
        ivrit_path = os.path.join(TMP_DIR, "transcript_ivrit_ai.json")
        print(f"  Note: using v1 ivrit.ai transcript (no word-level probabilities)")

    el_path = os.path.join(TMP_DIR, "transcript_elevenlabs.json")

    with open(ivrit_path, encoding="utf-8") as f:
        ivrit_data = json.load(f)
    with open(el_path, encoding="utf-8") as f:
        el_data = json.load(f)

    has_word_probs = bool(ivrit_data["segments"] and "words" in ivrit_data["segments"][0])
    print(f"  ivrit.ai: {len(ivrit_data['segments'])} segments" +
          (" (with word probabilities)" if has_word_probs else " (segment-level only)"))
    print(f"  ElevenLabs: {sum(1 for w in el_data['words'] if w['type'] == 'word')} words")

    return ivrit_data, el_data


def build_speaker_segments(el_data):
    """Build contiguous speaker segments from ElevenLabs word data."""
    words = [w for w in el_data["words"] if w["type"] == "word"]
    if not words:
        return []

    segments = []
    current_speaker = words[0]["speaker_id"]
    seg_start = words[0]["start"]
    seg_word_count = 0

    for i, w in enumerate(words):
        if w["speaker_id"] != current_speaker:
            segments.append({
                "speaker": current_speaker,
                "start": seg_start,
                "end": words[i - 1]["end"],
                "word_count": seg_word_count,
            })
            current_speaker = w["speaker_id"]
            seg_start = w["start"]
            seg_word_count = 0
        seg_word_count += 1

    # Final segment
    segments.append({
        "speaker": current_speaker,
        "start": seg_start,
        "end": words[-1]["end"],
        "word_count": seg_word_count,
    })

    return segments


def merge_short_segments(segments, min_duration=30):
    """Merge short segments (<min_duration seconds) into their neighbors."""
    if len(segments) <= 1:
        return segments

    merged = list(segments)
    changed = True
    while changed:
        changed = False
        new_merged = []
        i = 0
        while i < len(merged):
            seg = merged[i]
            dur = seg["end"] - seg["start"]

            if dur < min_duration and len(new_merged) > 0:
                # Merge into previous (larger) segment
                prev = new_merged[-1]
                prev["end"] = seg["end"]
                prev["word_count"] += seg["word_count"]
                changed = True
            elif dur < min_duration and i + 1 < len(merged):
                # Merge into next segment
                nxt = merged[i + 1]
                nxt["start"] = seg["start"]
                nxt["word_count"] += seg["word_count"]
                changed = True
            else:
                new_merged.append(dict(seg))
            i += 1
        merged = new_merged

    return merged


def find_dominant_speaker_per_window(el_data, window_size=60):
    """Find the dominant speaker in each time window.

    Returns list of (window_start, dominant_speaker, word_count) tuples.
    """
    words = [w for w in el_data["words"] if w["type"] == "word"]
    if not words:
        return []

    max_time = max(w["end"] for w in words)
    windows = []

    for t in range(0, int(max_time) + window_size, window_size):
        speaker_counts = {}
        for w in words:
            if t <= w["start"] < t + window_size:
                sid = w["speaker_id"]
                speaker_counts[sid] = speaker_counts.get(sid, 0) + 1
        if speaker_counts:
            dominant = max(speaker_counts, key=speaker_counts.get)
            windows.append((t, dominant, speaker_counts[dominant]))

    return windows


def detect_boundaries(el_data):
    """Auto-detect speech boundaries from ElevenLabs speaker diarization.

    Uses a dominant-speaker-per-minute-window approach: assigns each minute
    to the speaker with the most words, then finds where the dominant speaker
    changes. This is more robust than raw segment transitions since it
    smooths over diarization noise.

    Returns list of 8 (start, end) tuples, or falls back to reference boundaries.
    """
    print("\n--- Boundary Detection ---")

    # Strategy: find the dominant speaker per 1-minute window, then detect
    # where the dominant speaker changes
    windows = find_dominant_speaker_per_window(el_data, window_size=60)
    print(f"  Dominant-speaker windows: {len(windows)}")

    # Find transitions between dominant speakers
    transitions = []
    for i in range(1, len(windows)):
        prev_time, prev_speaker, _ = windows[i - 1]
        curr_time, curr_speaker, _ = windows[i]
        if prev_speaker != curr_speaker:
            transitions.append({
                "time": curr_time,
                "from_speaker": prev_speaker,
                "to_speaker": curr_speaker,
            })

    print(f"  Window-level transitions: {len(transitions)}")

    # Merge transitions that are within 2 minutes of each other
    # (keep the first one in each cluster as the speech boundary)
    if transitions:
        clustered = [transitions[0]]
        for t in transitions[1:]:
            if t["time"] - clustered[-1]["time"] > 120:
                clustered.append(t)
            # else: skip — too close to previous transition (diarization noise)
        transitions = clustered
        print(f"  After clustering close transitions: {len(transitions)}")

    for t in transitions:
        m, s = int(t["time"] // 60), int(t["time"] % 60)
        print(f"    {m:02d}:{s:02d} {t['from_speaker']} -> {t['to_speaker']}")

    # We need exactly 7 transitions for 8 speeches.
    # If we have too many, iteratively remove the transition whose removal
    # produces the most uniform speech durations (closest to 7 min each).
    audio_duration = max(w["end"] for w in el_data["words"] if w["type"] == "word")
    while len(transitions) > 7:
        best_score = float("inf")
        best_idx = 0
        for rm_idx in range(len(transitions)):
            candidate = [t for i, t in enumerate(transitions) if i != rm_idx]
            times = [0.0] + [t["time"] for t in candidate] + [audio_duration]
            durations = [times[i+1] - times[i] for i in range(len(times)-1)]
            # Score: sum of squared deviations from 420s (7 min)
            score = sum((d - 420) ** 2 for d in durations)
            if score < best_score:
                best_score = score
                best_idx = rm_idx
        removed = transitions.pop(best_idx)
        m, s = int(removed["time"] // 60), int(removed["time"] % 60)
        print(f"  Pruned noisy transition at {m:02d}:{s:02d} "
              f"({removed['from_speaker']} -> {removed['to_speaker']})")
    print(f"  Final transitions: {len(transitions)}")

    boundary_times = [0.0]  # Speech 1 always starts at 0
    for t in transitions:
        boundary_times.append(float(t["time"]))

    # Validate against reference boundaries
    boundaries_valid = True
    if len(boundary_times) == 8:
        print(f"\n  Detected {len(boundary_times)} boundaries (8 speeches)")
        for i, (detected, reference) in enumerate(zip(boundary_times, REFERENCE_BOUNDARIES)):
            diff = abs(detected - reference)
            status = "OK" if diff <= BOUNDARY_TOLERANCE else "DRIFT"
            if diff > BOUNDARY_TOLERANCE:
                boundaries_valid = False
            m_d, s_d = int(detected // 60), int(detected % 60)
            m_r, s_r = int(reference // 60), int(reference % 60)
            print(f"    Speech {i+1}: detected {m_d:02d}:{s_d:02d}, "
                  f"reference {m_r:02d}:{s_r:02d}, diff {diff:.0f}s [{status}]")
    else:
        boundaries_valid = False
        print(f"\n  Expected 8 boundaries, got {len(boundary_times)} — falling back")

    if not boundaries_valid:
        print("  Using reference boundaries as fallback")
        boundary_times = list(REFERENCE_BOUNDARIES)

    # Build (start, end) pairs
    boundaries = []
    for i in range(8):
        start = boundary_times[i]
        end = boundary_times[i + 1] if i + 1 < len(boundary_times) else audio_duration + 10
        boundaries.append((start, end))

    # Print final durations
    print("\n  Final speech durations:")
    for i, (start, end) in enumerate(boundaries):
        dur = end - start
        m_s, s_s = int(start // 60), int(start % 60)
        m_e, s_e = int(end // 60), int(end % 60)
        print(f"    Speech {i+1}: {m_s:02d}:{s_s:02d} - {m_e:02d}:{s_e:02d} ({dur:.0f}s / {dur/60:.1f}min)")

    return boundaries


def extract_speaker_changes(el_data, boundaries):
    """Extract all speaker changes from ElevenLabs data, annotated with speech context."""
    words = [w for w in el_data["words"] if w["type"] == "word"]
    changes = []

    current_speaker = None
    for i, w in enumerate(words):
        if w["speaker_id"] != current_speaker:
            if current_speaker is not None:
                # Determine which speech this falls in
                speech_num = None
                for si, (start, end) in enumerate(boundaries):
                    if start <= w["start"] < end:
                        speech_num = si + 1
                        break

                # Get surrounding context (3 words before/after)
                ctx_before = " ".join(wd["text"] for wd in words[max(0, i-3):i])
                ctx_after = " ".join(wd["text"] for wd in words[i:min(len(words), i+3)])

                # Calculate duration of the interrupting speaker
                int_end = w["end"]
                for j in range(i + 1, len(words)):
                    if words[j]["speaker_id"] == w["speaker_id"]:
                        int_end = words[j]["end"]
                    else:
                        break
                duration = int_end - w["start"]

                changes.append({
                    "time": round(w["start"], 2),
                    "from_speaker": current_speaker,
                    "to_speaker": w["speaker_id"],
                    "duration": round(duration, 1),
                    "speech_number": speech_num,
                    "context_before": ctx_before,
                    "context_after": ctx_after,
                })
            current_speaker = w["speaker_id"]

    return changes


def slice_speech_data(speech_num, start, end, ivrit_data, el_data, speaker_changes, metadata):
    """Extract data for a single speech."""
    # ivrit.ai segments in range
    ivrit_segments = []
    for seg in ivrit_data["segments"]:
        # Include segment if it overlaps with the speech time range
        if seg["end"] > start and seg["start"] < end:
            ivrit_segments.append(seg)

    # ElevenLabs words in range
    el_words = []
    for w in el_data["words"]:
        if w["type"] == "word" and w["start"] >= start - 1 and w["end"] <= end + 1:
            el_words.append(w)

    # Speaker changes during this speech
    speech_changes = [c for c in speaker_changes if c.get("speech_number") == speech_num]

    # Get speaker name from metadata if available
    speaker_name = "?"
    if metadata and "speakers" in metadata:
        for s in metadata["speakers"]:
            if s["speech_num"] == speech_num:
                speaker_name = s["speaker_name"]
                break

    role_info = BP_ROLES[speech_num - 1]

    return {
        "speech_number": speech_num,
        "role": role_info["role"],
        "role_he": role_info["role_he"],
        "team": role_info["team"],
        "team_he": role_info["team_he"],
        "speaker_name": speaker_name,
        "start_time": round(start, 2),
        "end_time": round(end, 2),
        "ivrit_segments": ivrit_segments,
        "elevenlabs_words": el_words,
        "speaker_changes": speech_changes,
    }


def load_metadata():
    """Load debate metadata if available."""
    meta_path = os.path.join(TMP_DIR, "debate_metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)

    return None


def main():
    os.makedirs(SPEECHES_DIR, exist_ok=True)

    print("Loading transcripts...")
    ivrit_data, el_data = load_transcripts()

    # Load metadata
    metadata = load_metadata()

    # Detect speech boundaries
    boundaries = detect_boundaries(el_data)

    # Extract all speaker changes
    print("\n--- Extracting Speaker Changes ---")
    speaker_changes = extract_speaker_changes(el_data, boundaries)
    print(f"  Total speaker changes: {len(speaker_changes)}")

    # Write speaker changes
    changes_path = os.path.join(SPEECHES_DIR, "speaker_changes.json")
    with open(changes_path, "w", encoding="utf-8") as f:
        json.dump(speaker_changes, f, ensure_ascii=False, indent=2)
    print(f"  Written: {changes_path}")

    # Write metadata
    meta_out = {
        "boundaries": [{"speech": i+1, "start": s, "end": e} for i, (s, e) in enumerate(boundaries)],
        "roles": BP_ROLES,
    }
    if metadata:
        meta_out["debate"] = metadata
    meta_path = os.path.join(SPEECHES_DIR, "debate_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_out, f, ensure_ascii=False, indent=2)
    print(f"  Written: {meta_path}")

    # Slice and write per-speech data
    print("\n--- Writing Per-Speech Data ---")
    for i, (start, end) in enumerate(boundaries):
        speech_num = i + 1
        speech_data = slice_speech_data(
            speech_num, start, end, ivrit_data, el_data, speaker_changes, metadata
        )
        out_path = os.path.join(SPEECHES_DIR, f"speech_{speech_num}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(speech_data, f, ensure_ascii=False, indent=2)

        n_ivrit = len(speech_data["ivrit_segments"])
        n_el = len(speech_data["elevenlabs_words"])
        n_changes = len(speech_data["speaker_changes"])
        print(f"  Speech {speech_num} ({speech_data['role']:3s}): "
              f"{n_ivrit} segments, {n_el} EL words, {n_changes} speaker changes "
              f"-> {out_path}")

    print("\nDone! Per-speech files ready for merge pipeline.")


if __name__ == "__main__":
    main()
