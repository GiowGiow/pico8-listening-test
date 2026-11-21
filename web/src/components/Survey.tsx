import { useEffect, useRef, useState } from "react";
import { ApiError, api, getParticipant, type Pair, type Status } from "../lib/api";
import * as m from "../paraglide/messages.js";
import TrackPlayer, { HEARD_SECONDS } from "./TrackPlayer";

type Load = "loading" | "ready" | "no_participant" | "error";

interface Answer {
  human_perception: number | null;
  song_recognition: number | null;
  comments: string;
}

const EMPTY: Answer = { human_perception: null, song_recognition: null, comments: "" };

export default function Survey() {
  const [load, setLoad] = useState<Load>("loading");
  const [pairs, setPairs] = useState<Pair[]>([]);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState<Answer>(EMPTY);
  const [listened, setListened] = useState<[number, number]>([0, 0]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const started = useRef(Date.now());
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (!getParticipant()) {
      setLoad("no_participant");
      return;
    }
    api<{ status: Status; pairs: Pair[] }>("/session")
      .then((res) => {
        if (res.status === "completed") {
          window.location.href = "/thank-you";
          return;
        }
        if (res.status === "pending_profile") {
          window.location.href = "/register";
          return;
        }
        const first = res.pairs.findIndex((p) => !p.answered);
        setPairs(res.pairs);
        setIndex(first < 0 ? 0 : first);
        started.current = Date.now();
        setLoad("ready");
      })
      .catch((err) => setLoad(err instanceof ApiError && err.status === 401 ? "no_participant" : "error"));
  }, []);

  if (load === "loading") return <p className="muted">{m.survey_loading()}</p>;
  if (load === "error")
    return (
      <p className="alert" role="alert">
        {m.survey_error_load()}
      </p>
    );
  if (load === "no_participant")
    return (
      <div className="screen">
        <h1>{m.survey_need_registration_title()}</h1>
        <p className="muted">{m.survey_need_registration_text()}</p>
        <p className="question-gap">
          <a className="btn" href="/">
            {m.survey_go_home()}
          </a>
        </p>
      </div>
    );

  const pair = pairs[index];
  const isLast = index === pairs.length - 1;
  const heardBoth = listened[0] >= HEARD_SECONDS && listened[1] >= HEARD_SECONDS;
  const complete = answer.human_perception !== null && answer.song_recognition !== null;

  async function next() {
    if (!complete || !heardBoth || saving) return;
    setSaving(true);
    setSaveError(false);
    try {
      await api(`/responses/${pair.response_id}`, {
        method: "POST",
        json: {
          human_perception: answer.human_perception,
          song_recognition: answer.song_recognition,
          comments: answer.comments.slice(0, 2000),
          time_spent_ms: Date.now() - started.current,
          listened_a_s: Math.round(listened[0] * 10) / 10,
          listened_b_s: Math.round(listened[1] * 10) / 10,
        },
      });
    } catch (err) {
      // 409: already saved (a retry after a lost reply), so move on
      if (!(err instanceof ApiError && err.status === 409)) {
        setSaveError(true);
        setSaving(false);
        return;
      }
    }
    if (isLast) {
      window.location.href = "/register";
      return;
    }
    setIndex(index + 1);
    setAnswer(EMPTY);
    setListened([0, 0]);
    started.current = Date.now();
    setSaving(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
    heading.current?.focus();
  }

  const aiOptions: [number, string, 1 | 2 | undefined][] = [
    [1, m.survey_q_ai_track1(), 1],
    [2, m.survey_q_ai_track2(), 2],
    [3, m.survey_q_ai_both(), undefined],
    [0, m.survey_q_ai_none(), undefined],
    [4, m.survey_q_ai_unsure(), undefined],
  ];
  const knownOptions: [number, string, 1 | 2 | undefined][] = [
    [0, m.survey_q_known_none(), undefined],
    [1, m.survey_q_known_track1(), 1],
    [2, m.survey_q_known_track2(), 2],
    [3, m.survey_q_known_both(), undefined],
  ];

  return (
    <div className="survey">
      <div className="survey-head">
        <h1 ref={heading} tabIndex={-1} className="display survey-title">
          {m.survey_pair_of({ current: index + 1, total: pairs.length })}
        </h1>
        <div className="pair-progress" aria-hidden="true">
          {pairs.map((p, i) => (
            <span key={p.response_id} data-state={i < index ? "done" : i === index ? "current" : "todo"} />
          ))}
        </div>
      </div>

      <TrackPlayer
        key={pair.track_a}
        track={1}
        src={pair.track_a}
        onListened={(s) => setListened((l) => (s > l[0] ? [s, l[1]] : l))}
      />
      <TrackPlayer
        key={pair.track_b}
        track={2}
        src={pair.track_b}
        onListened={(s) => setListened((l) => (s > l[1] ? [l[0], s] : l))}
      />

      <form className="screen survey-form" onSubmit={(e) => (e.preventDefault(), void next())}>
        <fieldset className="question">
          <legend>{m.survey_q_ai()}</legend>
          <div className="options">
            {aiOptions.map(([value, label, track]) => (
              <label key={value} className="option" data-track={track}>
                <input
                  type="radio"
                  name="human_perception"
                  value={value}
                  checked={answer.human_perception === value}
                  onChange={() => setAnswer({ ...answer, human_perception: value })}
                />
                <span>{label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="question">
          <legend>{m.survey_q_known()}</legend>
          <div className="options">
            {knownOptions.map(([value, label, track]) => (
              <label key={value} className="option" data-track={track}>
                <input
                  type="radio"
                  name="song_recognition"
                  value={value}
                  checked={answer.song_recognition === value}
                  onChange={() => setAnswer({ ...answer, song_recognition: value })}
                />
                <span>{label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="question-gap">
          <label htmlFor="comments" className="field-label">
            {m.survey_q_comments()}
          </label>
          <textarea
            id="comments"
            className="input"
            rows={3}
            maxLength={2000}
            placeholder={m.survey_q_comments_placeholder()}
            value={answer.comments}
            onChange={(e) => setAnswer({ ...answer, comments: e.target.value })}
          />
        </div>

        <div className="survey-actions">
          {!heardBoth && (
            <p className="muted gate" role="status">
              {m.survey_listen_gate()}
            </p>
          )}
          <button type="submit" className="btn" disabled={!complete || !heardBoth || saving}>
            {saving ? m.survey_saving() : isLast ? m.survey_finish() : m.survey_next()}
          </button>
        </div>
        {saveError && (
          <p className="alert" role="alert">
            {m.survey_error_save()}
          </p>
        )}
      </form>
    </div>
  );
}
