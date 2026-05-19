"""
analyzer.py v2 — ignora os primeiros N segundos no heatmap (evitar intro)
"""
import yt_dlp
import random


def time_str_to_seconds(time_str: str) -> int:
    parts = time_str.strip().split(":")
    if len(parts) == 3:
        return int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0])*60 + int(parts[1])
    return int(parts[0])


def seconds_to_str(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def find_most_watched_segments(
    url: str,
    num_clips: int = 3,
    clip_duration: int = 45,
    skip_intro_seconds: int = 60,   # ← ignora os primeiros N segundos
) -> list[dict]:
    heatmap_data = _fetch_youtube_heatmap(url)

    if heatmap_data:
        print(f"[analyzer] Heatmap com {len(heatmap_data)} pontos. Ignorando primeiros {skip_intro_seconds}s.")
        segments = _segments_from_heatmap(heatmap_data, num_clips, clip_duration, skip_intro_seconds)
    else:
        print("[analyzer] Heatmap indisponível. Usando heurística.")
        duration = _get_duration(url)
        segments = _segments_heuristic(duration, num_clips, clip_duration, skip_intro_seconds)

    return segments


def _fetch_youtube_heatmap(url: str) -> list | None:
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            heatmap = info.get("heatmap")
            if heatmap and len(heatmap) > 0:
                return heatmap
    except Exception as e:
        print(f"[analyzer] Erro heatmap: {e}")
    return None


def _get_duration(url: str) -> int:
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
            return ydl.extract_info(url, download=False).get("duration", 300)
    except:
        return 300


def _segments_from_heatmap(heatmap, num_clips, clip_duration, skip_intro_seconds):
    total_duration = int(heatmap[-1]["end_time"])
    timeline = [0.0] * (total_duration + 1)

    for entry in heatmap:
        start = int(entry.get("start_time", 0))
        end   = int(entry.get("end_time", start + 1))
        value = float(entry.get("value", 0))
        for t in range(start, min(end + 1, len(timeline))):
            timeline[t] = value

    # Janela deslizante — começa em skip_intro_seconds
    window_scores = []
    search_start = min(skip_intro_seconds, total_duration // 4)  # no máximo 25% do vídeo
    for i in range(search_start, len(timeline) - clip_duration):
        score = sum(timeline[i:i + clip_duration])
        window_scores.append((i, score))

    window_scores.sort(key=lambda x: x[1], reverse=True)

    MIN_GAP = max(clip_duration * 2, 120)  # mínimo 2x duração do clipe ou 2min entre cortes

    selected = []
    for start, score in window_scores:
        end = start + clip_duration
        # Verificar sobreposição E distância mínima
        too_close = any(
            abs(start - s["start"]) < MIN_GAP
            for s in selected
        )
        if not too_close:
            norm_score = min(100.0, (score / clip_duration) * 100)
            selected.append({
                "start": start, "end": end,
                "start_str": seconds_to_str(start),
                "end_str": seconds_to_str(end),
                "score": norm_score,
            })
        if len(selected) >= num_clips:
            break

    selected.sort(key=lambda x: x["start"])
    return selected


def _segments_heuristic(duration, num_clips, clip_duration, skip_intro_seconds):
    if duration <= clip_duration:
        return [{"start": 0, "end": duration, "start_str": "00:00:00",
                 "end_str": seconds_to_str(duration), "score": 80.0}]

    usable_start = min(skip_intro_seconds, duration // 4)
    positions_pct = [0.25, 0.40, 0.55, 0.70, 0.82]
    random.shuffle(positions_pct)
    positions_pct = sorted(positions_pct[:num_clips])

    segments = []
    for i, pct in enumerate(positions_pct):
        start = max(usable_start, int(duration * pct))
        end   = min(start + clip_duration, duration)
        score = max(40.0, 80.0 - i * 8 + random.uniform(-5, 5))
        segments.append({
            "start": start, "end": end,
            "start_str": seconds_to_str(start),
            "end_str": seconds_to_str(end),
            "score": round(score, 1),
        })
    return segments
