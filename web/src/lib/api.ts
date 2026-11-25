// Thin client for the survey API, served on the same origin under /api.

const PARTICIPANT_KEY = "p8percept.participant";

export class ApiError extends Error {
  constructor(public status: number, public code: string) {
    super(code);
  }
}

export function getParticipant(): string | null {
  try {
    return localStorage.getItem(PARTICIPANT_KEY);
  } catch {
    return null;
  }
}

export function setParticipant(id: string) {
  try {
    localStorage.setItem(PARTICIPANT_KEY, id);
  } catch {
    /* private mode: the id only lives for this page */
  }
}

export function clearParticipant() {
  try {
    localStorage.removeItem(PARTICIPANT_KEY);
  } catch {
    /* nothing to clear */
  }
}

export async function api<T>(path: string, options: { method?: string; json?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const participant = getParticipant();
  if (participant) headers["X-Participant-Id"] = participant;
  if (options.json !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.json !== undefined ? JSON.stringify(options.json) : undefined,
      credentials: "omit",
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "network");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(response.status, (data as { error?: string }).error ?? "http_error");
  return data as T;
}

export type Status = "pending_profile" | "in_progress" | "completed" | "study_full";

export const SLOTS = ["A", "B", "C", "D"] as const;
export type Slot = (typeof SLOTS)[number];

export interface Scenario {
  reservation_id: string;
  heading: string;
  description: string;
  image: string;
  audios: Record<Slot, string>;
  answered: boolean;
}

export interface Option {
  value: string;
  label: string;
}

/** Texts of the study, served by the API exactly as the research package gives them. */
export interface Study {
  heading: string;
  question: string;
  scale: { value: number; label: string }[];
  scenarios_per_participant: number;
  questionnaire: { version: string; fields: { name: string; label: string; options: Option[] }[] };
}

export const SCENARIOS_PER_PARTICIPANT = 2;
