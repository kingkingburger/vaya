import numpy as np

from config import HighlightConfig


def compute_highlights(
    audio_scores: np.ndarray,
    video_scores: np.ndarray,
    duration: float,
    config: HighlightConfig,
) -> list[dict]:
    """Compute highlight segments from audio and video analysis scores.

    Returns list of {start, end, score} dicts sorted by start time.
    """
    if len(audio_scores) == 0 and len(video_scores) == 0:
        return []

    # Resample to common length (use the longer array as reference)
    target_len = max(len(audio_scores), len(video_scores), 1)

    if len(audio_scores) == 0:
        audio_resampled = np.zeros(target_len)
    else:
        audio_resampled = np.interp(
            np.linspace(0, 1, target_len),
            np.linspace(0, 1, len(audio_scores)),
            audio_scores,
        )

    if len(video_scores) == 0:
        video_resampled = np.zeros(target_len)
    else:
        video_resampled = np.interp(
            np.linspace(0, 1, target_len),
            np.linspace(0, 1, len(video_scores)),
            video_scores,
        )

    # Composite score
    total_weight = config.audio_weight + config.video_weight
    composite = (
        config.audio_weight * audio_resampled + config.video_weight * video_resampled
    ) / total_weight

    # Time resolution
    time_per_sample = duration / target_len if target_len > 0 else 0

    # Threshold: top N% of scores
    threshold = np.percentile(composite, 100 - config.top_percent)

    # Find segments above threshold
    above = composite >= threshold
    raw_segments = []
    in_segment = False
    start_idx = 0

    for i, val in enumerate(above):
        if val and not in_segment:
            start_idx = i
            in_segment = True
        elif not val and in_segment:
            raw_segments.append((start_idx, i))
            in_segment = False

    if in_segment:
        raw_segments.append((start_idx, len(above)))

    # Convert to time and apply duration filters
    segments = []
    for s_idx, e_idx in raw_segments:
        start = s_idx * time_per_sample
        end = e_idx * time_per_sample
        seg_duration = end - start

        if seg_duration < config.min_clip_duration:
            continue
        if seg_duration > config.max_clip_duration:
            end = start + config.max_clip_duration

        # Average score for this segment
        score = float(np.mean(composite[s_idx:e_idx]))
        segments.append({"start": round(start, 2), "end": round(end, 2), "score": round(score, 3)})

    # Merge segments within merge_gap
    if len(segments) > 1:
        merged = [segments[0]]
        for seg in segments[1:]:
            prev = merged[-1]
            if seg["start"] - prev["end"] <= config.merge_gap:
                # Merge: extend end, average scores
                new_end = min(seg["end"], prev["start"] + config.max_clip_duration)
                prev["end"] = round(new_end, 2)
                prev["score"] = round((prev["score"] + seg["score"]) / 2, 3)
            else:
                merged.append(seg)
        segments = merged

    return segments
