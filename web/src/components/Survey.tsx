import { useEffect, useRef, useState } from "react";
import { ApiError, api, clearParticipant, getParticipant, SLOTS, type Scenario, type Slot, type Status, type Study } from "../lib/api";
import * as m from "../paraglide/messages.js";
import TrackPlayer, { HEARD_SECONDS } from "./TrackPlayer";

type Load = "loading" | "ready" | "no_participant" | "full" | "error";
type PerSlot<T> = Record<Slot, T>;
interface Session {
  status: Status;
  scenarios: Scenario[];
}

const NO_RATINGS: PerSlot<number | null> = { A: null, B: null, C: null, D: null };
const NOT_HEARD: PerSlot<number> = { A: 0, B: 0, C: 0, D: 0 };
// Asking for the session again tells the server this participant is still
// here, so the scenarios they hold are not handed to someone else.
const KEEP_ALIVE_MS = 5 * 60 * 1000;

/**
 * One scenario at a time: the game's picture and description, then the four
 * players A to D in the order of the research package, each with the same
 * question and the same five answers.
 */
export default function Survey() {
  const [load, setLoad] = useState<Load>("loading");
  const [study, setStudy] = useState<Study | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [index, setIndex] = useState(0);
  const [ratings, setRatings] = useState(NO_RATINGS);
  const [listened, setListened] = useState(NOT_HEARD);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const [replaced, setReplaced] = useState(false);
  const started = useRef(Date.now());
  const heading = useRef<HTMLHeadingElement>(null);

  function show(session: Session) {
    if (session.status === "completed") {
      clearParticipant();
      window.location.href = "/thank-you";
      return;
    }
    if (session.status === "pending_profile") {
      window.location.href = "/register";
      return;
    }
    if (session.status === "study_full") {
      setLoad("full");
      return;
    }
    const first = session.scenarios.findIndex((s) => !s.answered);
    setScenarios(session.scenarios);
    setIndex(first < 0 ? 0 : first);
    setRatings(NO_RATINGS);
    setListened(NOT_HEARD);
    started.current = Date.now();
    setLoad("ready");
  }

  useEffect(() => {
    if (!getParticipant()) {
      setLoad("no_participant");
      return;
    }
    Promise.all([api<Study>("/study"), api<Session>("/session")])
      .then(([texts, session]) => {
        setStudy(texts);
        show(session);
      })
      .catch((err) => setLoad(err instanceof ApiError && err.status === 401 ? "no_participant" : "error"));
    const keepAlive = window.setInterval(() => void api<Session>("/session").catch(() => undefined), KEEP_ALIVE_MS);
    return () => window.clearInterval(keepAlive);
  }, []);

  if (load === "loading") return <p className="muted">{m.survey_loading()}</p>;
  if (load === "error")
    return (
      <p className="alert" role="alert">
        {m.survey_error_load()}
      </p>
    );
  if (load === "full")
    return (
      <div className="screen">
        <h1>{m.survey_full_title()}</h1>
        <p className="muted">{m.survey_full_text()}</p>
      </div>
    );
  if (load === "no_participant" || !study)
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

  const scenario = scenarios[index];
  const isLast = index === scenarios.length - 1;
  const heardAll = SLOTS.every((slot) => listened[slot] >= HEARD_SECONDS);
  const complete = SLOTS.every((slot) => ratings[slot] !== null);

  async function next() {
    if (!complete || !heardAll || saving) return;
    setSaving(true);
    setSaveError(false);
    setReplaced(false);
    let status: Status;
    try {
      const res = await api<{ status: Status }>(`/ratings/${scenario.reservation_id}`, {
        method: "POST",
        json: {
          ratings,
          time_spent_ms: Date.now() - started.current,
          listened: Object.fromEntries(SLOTS.map((slot) => [slot, Math.round(listened[slot] * 10) / 10])),
        },
      });
      status = res.status;
    } catch (err) {
      if (err instanceof ApiError && err.code === "reservation_lost") {
        // The scenario went to someone else: load whatever this participant holds now.
        try {
          show(await api<Session>("/session"));
          setReplaced(true);
        } catch {
          setSaveError(true);
        }
      } else {
        setSaveError(true);
      }
      setSaving(false);
      return;
    }
    setSaving(false);
    if (status !== "in_progress") {
      clearParticipant();
      window.location.href = "/thank-you";
      return;
    }
    if (isLast) {
      // More scenarios were expected than this page knows of: ask again.
      show(await api<Session>("/session"));
    } else {
      setIndex(index + 1);
      setRatings(NO_RATINGS);
      setListened(NOT_HEARD);
      started.current = Date.now();
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
    heading.current?.focus();
  }

  return (
    <div className="survey">
      <div className="survey-head">
        <h1 ref={heading} tabIndex={-1} className="survey-title">
          {m.survey_pair_of({ current: index + 1, total: scenarios.length })}
        </h1>
        <div className="pair-progress" aria-hidden="true">
          {scenarios.map((s, i) => (
            <span key={s.reservation_id} data-state={i < index ? "done" : i === index ? "current" : "todo"} />
          ))}
        </div>
      </div>
      {replaced && (
        <p className="alert" role="status">
          {m.survey_lost()}
        </p>
      )}

      <section className="screen game" aria-labelledby="context-heading">
        <img className="game-image" src={scenario.image} alt={m.survey_image_alt()} width={160} height={205} />
        <div>
          <h2 id="context-heading" className="game-heading">
            {scenario.heading}
          </h2>
          <p className="game-description">{scenario.description}</p>
        </div>
      </section>

      <form onSubmit={(e) => (e.preventDefault(), void next())}>
        <div className="tracks">
          {SLOTS.map((slot) => {
            const heard = listened[slot] >= HEARD_SECONDS;
            return (
              <TrackPlayer
                key={scenario.audios[slot]}
                track={slot}
                src={scenario.audios[slot]}
                onListened={(s) => setListened((l) => (s > l[slot] ? { ...l, [slot]: s } : l))}
              >
                <fieldset className="rating" disabled={!heard}>
                  <legend>{study.question}</legend>
                  <div className="scale">
                    {study.scale.map((option) => (
                      <label key={option.value} className="option">
                        <input
                          type="radio"
                          name={`rating-${slot}`}
                          value={option.value}
                          checked={ratings[slot] === option.value}
                          onChange={() => setRatings({ ...ratings, [slot]: option.value })}
                        />
                        <span>{option.label}</span>
                      </label>
                    ))}
                  </div>
                  {!heard && <p className="rating-hint">{m.survey_listen_first()}</p>}
                </fieldset>
              </TrackPlayer>
            );
          })}
        </div>

        <div className="survey-actions">
          {!(heardAll && complete) && (
            <p className="muted gate" role="status">
              {m.survey_listen_gate()}
            </p>
          )}
          <button type="submit" className="btn" disabled={!complete || !heardAll || saving}>
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
