# PICO-8 listening test

Web app and API of the subjective evaluation of the DCC831 (Generative AI for
Music, UFMG, 2026/2) final project, which trains autoregressive models that
compose music for [PICO-8](https://www.lexaloffle.com/pico-8.php).

A participant answers six multiple-choice questions and then rates two
scenarios. Each scenario shows the picture and a description of a PICO-8 game
with four 30-second players, A to D, and asks of each one how well the song
fits that context, from "Não combina nada" to "Combina muito bem".

Adapted from the Humanness Percept study apps by Henrique Sousa
([web](https://github.com/HenriqueDSousa/humanness-percept-web),
[server](https://github.com/HenriqueDSousa/humanness-percept-server)), used in
"Echoes of Humanity: Exploring the Perceived Humanness of AI Music"
([arXiv:2509.25601](https://arxiv.org/abs/2509.25601)). The first commit is the import of those two apps; every later commit is
a change made for this study.

## Protocol

- **Scenarios.** 240, prepared by the research team: a game picture, a
  description of the game in Portuguese and four clips named only A, B, C and D.
  The team balanced what goes in each position; the app never shuffles them and
  does not know which clip is which.
- **Per participant.** Two scenarios, eight ratings. Each rating is one of five
  labelled options (1 to 5) and can be given after 10 s of the clip were heard.
- **Queue.** Scenarios go out in the team's collection order. A scenario is
  held by one participant at a time, an idle reservation is passed on after 45
  minutes, and a rated scenario is never used again.
- **Questionnaire.** Before the test, all multiple choice: age range, musical
  experience, how often the participant plays video games, familiarity with
  retro and 8-bit games, region of Brazil (or abroad) and whether they are
  wearing headphones.
- **Analysis.** Done by the research team from the CSV export, joining
  `external_id` and player with its own key. `/admin` shows only the progress of
  the collection, the queue, checks of the package and the raw ratings.

An earlier version of this app compared pairs of songs (a game's own song
against a generated one); it is in the history up to commit `909c2b7`.

## Layout

| Path | What |
|------|------|
| [`web/`](web/) | Astro + React front end, Portuguese and English |
| [`server/`](server/) | Flask API, SQLite, scenario queue, researcher panel |

Each folder has its own README with setup, endpoints and what changed from the
original apps (the date bug, same-origin API, no e-mail stored, rate limits).

## The scenario package is not in this repository

`server/study/` (2.4 GB of audio, the pictures and the two JSON files) is
delivered by the research team and baked into the server image. Its layout is
in [`server/README.md`](server/README.md).

## Running it

```bash
cd server && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/flask --app app.wsgi run --port 5000     # needs server/study
cd ../web && npm ci && npm run dev                 # proxies /api to port 5000
```

In production the two containers sit behind one host: the ingress sends `/api/`
to the server and everything else to the web app. `/admin` only answers on the
hosts listed in `ADMIN_HOSTS`; route it on an internal host or behind single
sign-on.

PICO-8 is a trademark of Lexaloffle Games. This study is not affiliated with
Lexaloffle. Cartridge images belong to their authors.
