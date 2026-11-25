# PICO-8 Percept: server

API of the PICO-8 listening test, adapted from
[humanness-percept-server](https://github.com/HenriqueDSousa/humanness-percept-server).
Each participant answers six multiple-choice questions and then rates two
scenarios. A scenario is the picture and a description of a PICO-8 game with
four 30-second players, A to D, and each player gets an answer from 1 (Não
combina nada) to 5 (Combina muito bem) to the question "Considerando a imagem e
a descrição do jogo, quanto esta música combina com esse contexto?".

The scenarios, their texts and their audio come from a package prepared by the
research team (`study/`, not in the repository). The server hands them out in
the package's order and stores the ratings; which clip of a scenario is which
is known only to the research team.

What changed from the original:

- **Dates.** `default=datetime.now()` was evaluated once at import, so every
  answer carried the time the server started. Defaults are now functions
  (`default=utcnow`), and each answer also records `answered_at`.
- **No S3, no AWS credentials.** Clips are served by the API from the package
  baked into the image; SQLite on a volume replaces the hard-coded RDS password.
- **Security.** Same-origin API under `/api` (no CORS), participant id derived
  server-side with an HMAC of the e-mail (the address is never stored or sent
  back), ownership check on every answer, write-once answers, input validation,
  16 KB body limit, per-IP rate limits, registration cap, generic error bodies,
  gunicorn instead of the Flask dev server, non-root image. The researcher panel
  at `/admin` only answers on the host names in `ADMIN_HOSTS`; route it on an
  internal host or behind single sign-on, never on the open public route.
- **The app has no answer key.** The package names the clips of a scenario
  only A, B, C and D, and they are served byte for byte in that order.

## Layout

| Path | What |
|------|------|
| `app/api.py` | Endpoints under `/api` |
| `app/scenarios.py` | Loads the package and runs the queue: reserve, renew, pass on, complete |
| `app/questionnaire.py` | The six opening questions, their options and their version |
| `app/export.py` | CSV export of the ratings |
| `app/admin.py` | Researcher panel: collection, queue, package checks, scenarios |

## Endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/study` | question, scale and questionnaire, as the package words them |
| POST | `/api/participants` | `{email, locale}` → `{participant_id, status}` |
| PUT | `/api/participants/me` | the six questionnaire answers, once, before any scenario |
| GET | `/api/session` | header `X-Participant-Id`; reserves the next two scenarios, renews them on later calls |
| POST | `/api/ratings/<reservation_id>` | `{ratings: {A, B, C, D}}`, integers 1 to 5; repeating it changes nothing |
| GET | `/api/scenarios/<external_id>/<file>` | `context.png` or `A.wav` to `D.wav`, with HTTP range support |
| GET | `/admin/` | researcher panel |
| GET | `/admin/ratings.csv` | every rated scenario |

## The package

`STUDY_DIR` (default `study/`) holds what the research team delivers:

```
study/study.json        heading, question, five-point scale, scenarios per participant
study/scenarios.json    240 records in collection order: external_id, description, file paths
study/scenarios/<external_id>/{context.png,A.wav,B.wav,C.wav,D.wav}
```

The files are used as they are: no conversion, normalization or reordering.

## The queue

- Scenarios go out in `collection_order_v2`, the next free ones first, two per
  participant.
- A scenario held by one participant is not given to another.
- Every request of the holder renews the reservation. After
  `RESERVATION_MINUTES` (45) of silence the scenario may go to the next
  participant, and the old holder can then no longer rate it (HTTP 409); they
  get the next free scenario instead. A late holder whose scenario nobody took
  can still rate it.
- A rated scenario leaves the pool for good. Sending the same ratings again is
  accepted and changes nothing.
- The server refuses to start with a package that changes the position of a
  scenario already in the database.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/flask --app app.wsgi run --port 5000
```

## Exporting the ratings

```bash
kubectl -n pico8-percept exec deploy/server -- python -m app.export > ratings.csv
```

One row per rated scenario: participant id, `external_id`,
`collection_order_v2`, `rating_A` to `rating_D`, listening time per player,
timestamps (UTC) and the questionnaire answers as the option codes of
`app/questionnaire.py`, with `questionnaire_version`.
