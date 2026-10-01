# CCAR-F-Trainer

Practice mock exam for the Anthropic Claude certification, built with Streamlit.
Questions live in `questions.json`, each with an explanation of the correct answer.

## Run locally

```bash
uv run --with streamlit --with streamlit-js-eval streamlit run exam_web.py
```

Or with a regular Python environment:

```bash
pip install -r requirements.txt
streamlit run exam_web.py
```

## Tests

- **Test 1** (65 questions) and **Test 2** (66 questions): fixed tests with no overlap.
  Each covers all 6 exam scenarios with balanced domains, and questions are grouped by
  scenario like the real exam. Picking the same test always gives the same questions in
  the same order.
- **Practice (all questions)**: all 131 questions, with the sidebar's limit, shuffle and
  syllabus filters.

The split is stored in the `test` field (1 or 2) of each question in `questions.json`.

## `questions.json` format

A list of objects with `id`, `question`, `options`, `answer_index` (list of correct indices),
`explanation`, `test` (1 or 2), and the syllabus tags `scenario`, `domain` and `topic`.
Optional: `code` (a block shown below the question) and `code_language`
(syntax highlighting for that block, e.g. `bash`, `json`, `yaml`).

## Saved progress

Progress is saved in the URL and in the browser's `localStorage`. When you come back
without the URL, the app offers **Resume** or **Start over**.

## Theme

`.streamlit/config.toml` forces the light theme so the app reads the same on phones in
dark mode (Safari on iPhone was showing white text on a white background).

## Deploy

Streamlit Community Cloud:

- repository: `pgarateguy-endava/CCAR-F-Trainer`
- branch: `main`
- main file: `exam_web.py`
