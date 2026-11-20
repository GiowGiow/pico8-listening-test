"""Build the listening-test catalog: pick clips, render them, write catalog.json.

Real songs come from the frozen test split; generated songs come from the
sample files of each system. Every clip goes through the same path, so the
only difference a listener can hear is the music itself:

* rendered by the project synth (src/synth.py of TPfinal-music-rn), with no SFX
  filters, because generated songs have none;
* cut to the same length (--clip-seconds, whole patterns, last one shortened),
  and only songs at least that long are eligible, in every pool;
* checked for silence (a clip must have sound in --min-active of its windows);
* loudness-normalized to -16 LUFS (two-pass ffmpeg loudnorm), faded out over
  the last 1.5 s, encoded as constant-bitrate MP3 so file size says nothing;
* named with a random opaque id, so the URL says nothing either.

At most one clip per cartridge is taken from the real songs. The selection is
random with a fixed seed. Rerunning keeps the ids of clips already in an
existing catalog.json.

Usage (with the TPfinal-music-rn virtualenv, which has numpy and scipy):

    ../TPfinal-music-rn/.venv/bin/python tools/prepare_songs.py \
        --tp-repo ../TPfinal-music-rn --out catalog
"""

import argparse
import json
import os
import random
import secrets
import subprocess
import sys
import tempfile
import wave
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np

SYSTEMS = {
    # catalog system name: sample file inside the TPfinal-music-rn repo
    "lstm-grid_block": "pico8_data/samples/lstm-grid_block-p095/samples.jsonl.gz",
    "lstm-nlm": "pico8_data/samples/lstm-nlm-drop05-p095/samples.jsonl.gz",
    "markov": "pico8_data/samples/markov-grupo/samples.jsonl.gz",
}
REAL = "pico8_data/splits/test.jsonl.gz"

_synth = {}


def load_tp(tp_repo):
    sys.path.insert(0, str(tp_repo))
    from src.render import cut_song, read_jsonl  # noqa: E402
    from src.synth import SAMPLE_RATE, SAMPLES_PER_TICK, synthesize_song  # noqa: E402

    return cut_song, read_jsonl, synthesize_song, SAMPLE_RATE, SAMPLES_PER_TICK


def song_seconds(song, sample_rate, samples_per_tick):
    ticks = sum(int(p.get("pattern_ticks", 512)) for p in song.get("patterns", []))
    return ticks * samples_per_tick / sample_rate


def _init(tp_repo):
    _synth["fns"] = load_tp(tp_repo)


def _render(job):
    song, clip_seconds, wav_path = job
    cut_song, _, synthesize_song, sample_rate, _ = _synth["fns"]
    cut, ok = cut_song(song, clip_seconds)
    if not ok:
        return None
    audio = synthesize_song(cut, loop_extra_repeats=0, seed=0)
    if audio.size == 0:
        return None
    window = int(0.5 * sample_rate)
    n = audio.size // window
    rms = np.sqrt(np.mean(audio[: n * window].reshape(n, window) ** 2, axis=1)) if n else np.zeros(1)
    pcm = np.clip(np.round(audio * 32767.0), -32767, 32767).astype("<i2")
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return {"seconds": audio.size / sample_rate, "active": float(np.mean(rms > 0.01))}


def ffmpeg_mp3(wav, mp3, clip_seconds, bitrate):
    fade = f"afade=t=in:d=0.02,afade=t=out:st={clip_seconds - 1.5}:d=1.5"
    probe = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", wav, "-af",
         f"{fade},loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    ).stderr
    m = json.loads(probe[probe.rindex("{"): probe.rindex("}") + 1])
    norm = (f"loudnorm=I=-16:TP=-1.5:LRA=11:linear=true:measured_I={m['input_i']}:"
            f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
            f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", wav,
         "-af", f"{fade},{norm},aresample=44100", "-t", str(clip_seconds), "-ac", "1",
         "-map_metadata", "-1", "-codec:a", "libmp3lame", "-b:a", bitrate, mp3],
        check=True,
    )
    return float(m["input_i"])


def pick(pool, n, clip_seconds, min_active, tmp, workers, tp_repo, one_per_tid):
    """Render candidates in batches until n clips pass the silence check."""
    chosen, seen_tid, i = [], set(), 0
    with Pool(workers, initializer=_init, initargs=(str(tp_repo),)) as procs:
        while len(chosen) < n and i < len(pool):
            batch = []
            while len(batch) < workers * 2 and i < len(pool):
                song = pool[i]
                i += 1
                if one_per_tid and song.get("tid") in seen_tid:
                    continue
                seen_tid.add(song.get("tid"))
                batch.append(song)
            jobs = [(s, clip_seconds, str(tmp / f"cand_{id(s)}.wav")) for s in batch]
            for song, job, res in zip(batch, jobs, procs.map(_render, jobs)):
                if res and res["active"] >= min_active and res["seconds"] >= clip_seconds - 0.05 and len(chosen) < n:
                    chosen.append((song, job[2], res))
    if len(chosen) < n:
        raise SystemExit(f"only {len(chosen)} usable clips, wanted {n}")
    return chosen


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tp-repo", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("catalog"))
    ap.add_argument("--clip-seconds", type=float, default=20.0)
    ap.add_argument("--per-system", type=int, default=24)
    ap.add_argument("--min-active", type=float, default=0.8)
    ap.add_argument("--bitrate", default="128k")
    ap.add_argument("--seed", type=int, default=831)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    args = ap.parse_args()

    tp = args.tp_repo.resolve()
    _, read_jsonl, _, sample_rate, samples_per_tick = load_tp(tp)
    rng = random.Random(args.seed)
    audio_dir = args.out / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = args.out / "catalog.json"
    old_ids = {}
    if catalog_path.exists():
        old_ids = {s["source_id"]: s["id"] for s in json.loads(catalog_path.read_text())["songs"]}

    def eligible(path):
        songs = read_jsonl(tp / path)
        ok = [s for s in songs if song_seconds(s, sample_rate, samples_per_tick) >= args.clip_seconds]
        rng.shuffle(ok)
        return ok

    git = subprocess.run(["git", "-C", str(tp), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(tp), "status", "--porcelain", "src/synth.py", "src/render.py"],
                           capture_output=True, text=True).stdout.strip()

    plan = []  # (system, kind, role, source_file, n, one_per_tid)
    n_real = args.per_system * len(SYSTEMS)
    plan.append(("real", "human", REAL, n_real + 1, True))
    for system, path in SYSTEMS.items():
        plan.append((system, "genai", path, args.per_system + (1 if system == "markov" else 0), False))

    songs = []
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for system, kind, path, n, one_per_tid in plan:
            pool = eligible(path)
            print(f"{system}: {len(pool)} eligible songs >= {args.clip_seconds:g} s", flush=True)
            chosen = pick(pool, n, args.clip_seconds, args.min_active, tmp, args.workers, tp, one_per_tid)
            for k, (song, wav, res) in enumerate(chosen):
                if kind == "human":
                    source_id = f"test:{song['tid']}:{song['song_id']}"
                else:
                    source_id = f"{Path(path).parent.name}:{song['song_id']}"
                sid = old_ids.get(source_id) or secrets.token_hex(8)
                lufs = ffmpeg_mp3(wav, str(audio_dir / f"{sid}.mp3"), args.clip_seconds, args.bitrate)
                # the last real clip and the last markov clip form the anchor pair
                role = "anchor" if (k == n - 1 and (kind == "human" or system == "markov")) else "pool"
                songs.append({
                    "id": sid, "system": system, "kind": kind, "role": role,
                    "source_id": source_id, "source_file": path,
                    "seconds": round(res["seconds"], 2), "active": round(res["active"], 3),
                    "input_lufs": round(lufs, 1),
                })
            print(f"{system}: {len(chosen)} clips written", flush=True)

    keep = {s["id"] for s in songs}
    for f in audio_dir.glob("*.mp3"):
        if f.stem not in keep:
            f.unlink()
    catalog = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "clip_seconds": args.clip_seconds,
        "seed": args.seed,
        "synth": {"tp_commit": git, "synth_or_render_modified": bool(dirty), "sfx_filters": False},
        "systems": list(SYSTEMS),
        "sources": {"real": REAL, **SYSTEMS},
        "songs": songs,
    }
    catalog_path.write_text(json.dumps(catalog, indent=1) + "\n")
    print(f"catalog: {len(songs)} clips -> {catalog_path}")


if __name__ == "__main__":
    main()
