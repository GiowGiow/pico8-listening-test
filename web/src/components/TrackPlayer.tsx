import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import * as m from "../paraglide/messages.js";

export const HEARD_SECONDS = 10;
const PLAY_EVENT = "p8percept:play";

interface Props {
  /** The player's letter, the only name the participant sees. */
  track: string;
  src: string;
  onListened: (seconds: number) => void;
  /** The question about this clip, shown under the player. */
  children?: ReactNode;
}

function clock(seconds: number) {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/**
 * One clip with a play button and a seek bar. Only one clip plays at a
 * time: starting one pauses the others through a window event. Listening time
 * is accumulated from actual playback, so seeking forward does not count.
 */
export default function TrackPlayer({ track, src, onListened, children }: Props) {
  const audio = useRef<HTMLAudioElement>(null);
  const strip = useRef<HTMLDivElement>(null);
  const last = useRef<number | null>(null);
  const listened = useRef(0);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(30);
  const [heard, setHeard] = useState(false);

  useEffect(() => {
    listened.current = 0;
    last.current = null;
    setHeard(false);
    setTime(0);
    setPlaying(false);
  }, [src]);

  useEffect(() => {
    const other = (e: Event) => {
      if ((e as CustomEvent<string>).detail !== track) audio.current?.pause();
    };
    window.addEventListener(PLAY_EVENT, other);
    return () => window.removeEventListener(PLAY_EVENT, other);
  }, [track]);

  function onTimeUpdate() {
    const el = audio.current;
    if (!el) return;
    const now = el.currentTime;
    if (last.current !== null && !el.paused) {
      const delta = now - last.current;
      if (delta > 0 && delta < 1) listened.current += delta;
    }
    last.current = now;
    setTime(now);
    onListened(listened.current);
    if (listened.current >= HEARD_SECONDS) setHeard(true);
  }

  function toggle() {
    const el = audio.current;
    if (!el) return;
    if (el.paused) {
      window.dispatchEvent(new CustomEvent(PLAY_EVENT, { detail: track }));
      void el.play();
    } else {
      el.pause();
    }
  }

  function seekTo(fraction: number) {
    const el = audio.current;
    if (!el || !Number.isFinite(el.duration)) return;
    el.currentTime = Math.min(Math.max(fraction, 0), 0.999) * el.duration;
    last.current = el.currentTime;
    setTime(el.currentTime);
  }

  function onPointer(e: PointerEvent<HTMLDivElement>) {
    if (e.type === "pointermove" && e.buttons !== 1) return;
    const r = strip.current?.getBoundingClientRect();
    if (!r || r.width === 0) return;
    seekTo((e.clientX - r.left) / r.width);
  }

  function onKey(e: KeyboardEvent<HTMLDivElement>) {
    const el = audio.current;
    if (!el) return;
    const step = el.duration / 20;
    if (e.key === "ArrowRight" || e.key === "ArrowUp") seekTo((el.currentTime + step) / el.duration);
    else if (e.key === "ArrowLeft" || e.key === "ArrowDown") seekTo((el.currentTime - step) / el.duration);
    else if (e.key === "Home") seekTo(0);
    else if (e.key === "End") seekTo(0.999);
    else if (e.key === " " || e.key === "Enter") toggle();
    else return;
    e.preventDefault();
  }

  const progress = duration > 0 ? time / duration : 0;
  const label = playing ? m.survey_pause({ n: track }) : m.survey_play({ n: track });

  return (
    <section className="screen track" aria-label={m.survey_track({ n: track })}>
      <div className="track-head">
        <span className="track-name" aria-hidden="true">{track}</span>
        <span className="track-heard" data-heard={heard ? "true" : "false"}>
          {heard ? `✓ ${m.survey_heard()}` : m.survey_listen_left({ s: Math.ceil(HEARD_SECONDS - Math.min(listened.current, HEARD_SECONDS)) })}
        </span>
      </div>
      <div className="track-body">
        <button type="button" className="play" onClick={toggle} aria-label={label} title={label}>
          {playing ? (
            <svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
              <rect x="6" y="5" width="4" height="14" rx="1" />
              <rect x="14" y="5" width="4" height="14" rx="1" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
              <path d="M8 5.5v13a1 1 0 001.5.86l10.5-6.5a1 1 0 000-1.72L9.5 4.64A1 1 0 008 5.5z" />
            </svg>
          )}
        </button>
        <div
          ref={strip}
          className="seek"
          role="slider"
          tabIndex={0}
          aria-label={m.survey_seek_label({ n: track })}
          aria-valuemin={0}
          aria-valuemax={Math.round(duration)}
          aria-valuenow={Math.round(time)}
          aria-valuetext={`${clock(time)} / ${clock(duration)}`}
          onPointerDown={onPointer}
          onPointerMove={onPointer}
          onKeyDown={onKey}
        >
          <div className="seek-rail">
            <div className="seek-fill" style={{ width: `${Math.min(100, progress * 100)}%` }} />
          </div>
        </div>
        <span className="track-time">
          {clock(time)} / {clock(Math.round(duration))}
        </span>
      </div>
      <audio
        ref={audio}
        src={src}
        preload="metadata"
        onPlay={() => {
          last.current = audio.current?.currentTime ?? 0;
          setPlaying(true);
        }}
        onPause={() => setPlaying(false)}
        onEnded={() => {
          setPlaying(false);
          last.current = null;
        }}
        onTimeUpdate={onTimeUpdate}
        onLoadedMetadata={() => setDuration(audio.current?.duration || 30)}
      />
      {children}
    </section>
  );
}
