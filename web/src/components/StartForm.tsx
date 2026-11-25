import { useState, type FormEvent } from "react";
import { ApiError, api, setParticipant, type Status } from "../lib/api";
import { getLocale } from "../paraglide/runtime.js";
import * as m from "../paraglide/messages.js";

const EMAIL_RE = /^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$/;

export default function StartForm() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const value = email.trim();
    if (!EMAIL_RE.test(value) || value.length > 254) {
      setError(m.home_error_email());
      return;
    }
    setBusy(true);
    try {
      const res = await api<{ participant_id: string; status: Status }>("/participants", {
        method: "POST",
        json: { email: value, locale: getLocale() },
      });
      if (res.status === "completed") {
        setDone(true);
        return;
      }
      setParticipant(res.participant_id);
      window.location.href = res.status === "pending_profile" ? "/register" : "/survey";
    } catch (err) {
      const code = err instanceof ApiError ? err : null;
      if (code?.status === 400) setError(m.home_error_email());
      else if (code?.status === 429) setError(m.home_error_rate());
      else if (code?.status === 503) setError(m.home_error_full());
      else setError(m.home_error_network());
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <p className="alert alert-ok" role="status">
        {m.home_already_done()}
      </p>
    );
  }

  return (
    <form onSubmit={submit} noValidate className="start-form">
      <label htmlFor="email" className="field-label">
        {m.home_email_label()}
      </label>
      <div className="start-row">
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          inputMode="email"
          maxLength={254}
          required
          className="input"
          placeholder={m.home_email_placeholder()}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? "email-error" : "email-hint"}
          disabled={busy}
        />
        <button type="submit" className="btn" disabled={busy}>
          {busy ? m.home_starting() : m.home_start_button()}
        </button>
      </div>
      {error ? (
        <p id="email-error" className="alert" role="alert">
          {error}
        </p>
      ) : (
        <p id="email-hint" className="muted start-hint">
          {m.home_resume_hint()}
        </p>
      )}
    </form>
  );
}
