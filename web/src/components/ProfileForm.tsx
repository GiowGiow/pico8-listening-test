import { useEffect, useState, type FormEvent } from "react";
import { ApiError, api, clearParticipant, getParticipant, type Status } from "../lib/api";
import { getLocale } from "../paraglide/runtime.js";
import * as m from "../paraglide/messages.js";

const LANGUAGES: [string, () => string][] = [
  ["portuguese", m.language_portuguese],
  ["english", m.language_english],
  ["spanish", m.language_spanish],
  ["french", m.language_french],
  ["german", m.language_german],
  ["italian", m.language_italian],
  ["mandarin", m.language_mandarin],
  ["japanese", m.language_japanese],
  ["korean", m.language_korean],
  ["hindi", m.language_hindi],
  ["arabic", m.language_arabic],
  ["russian", m.language_russian],
  ["other", m.language_other],
];
const LEVELS = [m.profile_level_0, m.profile_level_1, m.profile_level_2, m.profile_level_3];
const CHIPTUNE = [m.profile_chiptune_0, m.profile_chiptune_1, m.profile_chiptune_2, m.profile_chiptune_3];

type View = "loading" | "form" | "not_finished" | "no_participant";

export default function ProfileForm() {
  const [view, setView] = useState<View>("loading");
  const [participant, setParticipantId] = useState("");
  const [age, setAge] = useState("");
  const [language, setLanguage] = useState("");
  const [formal, setFormal] = useState("");
  const [practical, setPractical] = useState("");
  const [chiptune, setChiptune] = useState<number | null>(null);
  const [aiMusic, setAiMusic] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = getParticipant();
    if (!id) {
      setView("no_participant");
      return;
    }
    setParticipantId(id);
    api<{ status: Status }>("/session")
      .then((res) => {
        if (res.status === "completed") window.location.href = "/thank-you";
        else setView(res.status === "pending_profile" ? "form" : "not_finished");
      })
      .catch((err) => setView(err instanceof ApiError && err.status === 401 ? "no_participant" : "form"));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const ageNumber = Number(age);
    if (!Number.isInteger(ageNumber) || ageNumber < 1 || ageNumber > 120 || !language || !formal || !practical || chiptune === null) {
      setError(m.profile_error_fields());
      return;
    }
    setBusy(true);
    try {
      await api("/participants/me", {
        method: "PUT",
        json: {
          age: ageNumber,
          language,
          formal_experience: Number(formal),
          practical_experience: Number(practical),
          chiptune_familiarity: chiptune,
          knows_ai_music: aiMusic,
          locale: getLocale(),
        },
      });
    } catch (err) {
      if (!(err instanceof ApiError && err.code === "already_completed")) {
        setError(err instanceof ApiError && err.status === 400 ? m.profile_error_fields() : m.profile_error_send());
        setBusy(false);
        return;
      }
    }
    clearParticipant();
    window.location.href = "/thank-you";
  }

  if (view === "loading") return null;
  if (view === "no_participant" || view === "not_finished")
    return (
      <div className="screen">
        <p>{view === "no_participant" ? m.survey_need_registration_text() : m.profile_not_finished()}</p>
        <p className="question-gap">
          <a className="btn" href={view === "no_participant" ? "/" : "/survey"}>
            {view === "no_participant" ? m.survey_go_home() : m.profile_back_to_survey()}
          </a>
        </p>
      </div>
    );

  return (
    <form className="screen profile" onSubmit={submit} noValidate>
      <div className="profile-grid">
        <div>
          <label htmlFor="age" className="field-label">
            {m.profile_age()}
          </label>
          <input
            id="age"
            className="input"
            type="number"
            inputMode="numeric"
            min={1}
            max={120}
            placeholder={m.profile_age_placeholder()}
            value={age}
            onChange={(e) => setAge(e.target.value.replace(/\D/g, "").slice(0, 3))}
            required
          />
        </div>
        <div>
          <label htmlFor="language" className="field-label">
            {m.profile_language()}
          </label>
          <select id="language" className="input" value={language} onChange={(e) => setLanguage(e.target.value)} required>
            <option value="">{m.profile_choose()}</option>
            {LANGUAGES.map(([value, label]) => (
              <option key={value} value={value}>
                {label()}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="formal" className="field-label">
            {m.profile_formal()}
          </label>
          <span className="field-hint">{m.profile_formal_hint()}</span>
          <select id="formal" className="input" value={formal} onChange={(e) => setFormal(e.target.value)} required>
            <option value="">{m.profile_choose()}</option>
            {LEVELS.map((label, i) => (
              <option key={i} value={String(i)}>
                {label()}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="practical" className="field-label">
            {m.profile_practical()}
          </label>
          <span className="field-hint">{m.profile_practical_hint()}</span>
          <select id="practical" className="input" value={practical} onChange={(e) => setPractical(e.target.value)} required>
            <option value="">{m.profile_choose()}</option>
            {LEVELS.map((label, i) => (
              <option key={i} value={String(i)}>
                {label()}
              </option>
            ))}
          </select>
        </div>
      </div>

      <fieldset className="question question-gap">
        <legend>{m.profile_chiptune()}</legend>
        <div className="options">
          {CHIPTUNE.map((label, i) => (
            <label key={i} className="option">
              <input type="radio" name="chiptune" checked={chiptune === i} onChange={() => setChiptune(i)} />
              <span>{label()}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <label className="option question-gap">
        <input type="checkbox" checked={aiMusic} onChange={(e) => setAiMusic(e.target.checked)} />
        <span>{m.profile_ai_music()}</span>
      </label>

      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      <div className="survey-actions">
        <button type="submit" className="btn" disabled={busy}>
          {busy ? m.profile_sending() : m.profile_submit()}
        </button>
      </div>

      <div className="code-box">
        <p className="field-label">{m.profile_code()}</p>
        <code className="mono">{participant}</code>
        <p className="field-hint">{m.profile_code_hint()}</p>
      </div>
    </form>
  );
}
