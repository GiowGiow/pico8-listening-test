import { useEffect, useState, type FormEvent } from "react";
import { ApiError, api, getParticipant, type Status, type Study } from "../lib/api";
import { getLocale } from "../paraglide/runtime.js";
import * as m from "../paraglide/messages.js";

type View = "loading" | "form" | "no_participant" | "ineligible" | "error";

/** The opening questionnaire: every question is answered by picking an option. */
export default function ProfileForm() {
  const [view, setView] = useState<View>("loading");
  const [fields, setFields] = useState<Study["questionnaire"]["fields"]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [participant, setParticipantId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = getParticipant();
    if (!id) {
      setView("no_participant");
      return;
    }
    setParticipantId(id);
    Promise.all([api<Study>("/study"), api<{ status: Status }>("/session")])
      .then(([study, session]) => {
        if (session.status === "completed") window.location.href = "/thank-you";
        else if (session.status !== "pending_profile") window.location.href = "/survey";
        else {
          setFields(study.questionnaire.fields);
          setView("form");
        }
      })
      .catch((err) => setView(err instanceof ApiError && err.status === 401 ? "no_participant" : "error"));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (fields.some((f) => !answers[f.name])) {
      setError(m.profile_error_fields());
      return;
    }
    setBusy(true);
    try {
      await api("/participants/me", { method: "PUT", json: { ...answers, locale: getLocale() } });
    } catch (err) {
      // 403: the study only takes adults; the server stored nothing
      if (err instanceof ApiError && err.status === 403) {
        setView("ineligible");
        return;
      }
      // 409: already stored (a retry after a lost reply), so move on
      if (!(err instanceof ApiError && err.status === 409)) {
        setError(err instanceof ApiError && err.status === 400 ? m.profile_error_fields() : m.profile_error_send());
        setBusy(false);
        return;
      }
    }
    window.location.href = "/instructions";
  }

  if (view === "loading") return null;
  if (view === "error")
    return (
      <p className="alert" role="alert">
        {m.profile_error_load()}
      </p>
    );
  if (view === "ineligible")
    return (
      <div className="screen" role="status">
        <h2>{m.profile_ineligible_title()}</h2>
        <p>{m.profile_ineligible_text()}</p>
      </div>
    );
  if (view === "no_participant")
    return (
      <div className="screen">
        <p>{m.survey_need_registration_text()}</p>
        <p className="question-gap">
          <a className="btn" href="/">
            {m.survey_go_home()}
          </a>
        </p>
      </div>
    );

  return (
    <form className="screen profile" onSubmit={submit} noValidate>
      {fields.map((field, i) => (
        <fieldset key={field.name} className={i === 0 ? "question" : "question question-gap"}>
          <legend>{field.label}</legend>
          <div className="options choices">
            {field.options.map((option) => (
              <label key={option.value} className="option">
                <input
                  type="radio"
                  name={field.name}
                  value={option.value}
                  checked={answers[field.name] === option.value}
                  onChange={() => setAnswers({ ...answers, [field.name]: option.value })}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
        </fieldset>
      ))}

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
