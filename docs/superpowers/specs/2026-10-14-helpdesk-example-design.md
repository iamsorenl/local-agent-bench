# Helpdesk example: use local-agent-bench on your own problem

Date: 2026-10-14
Status: design, awaiting review

## Why

The README shows how 5 local models do on my 15 tasks. It doesn't show
someone else how to use the bench for a decision of their own. That second
part is the evidence I want for AI and forward-deployed engineering
interviews: a tool I built, applied to a realistic customer question, with
a measured answer an engineer can reproduce in a few minutes.

## The customer question

> A team wants an internal helpdesk agent. Their policy docs can't be sent to
> a cloud API. Can a model running on a laptop handle it, and which one?

The example answers that the way I'd answer it on a customer engagement:
write the tasks the way people will actually use the agent, record the
documents it should find, run every candidate model on the same inputs,
and report the pass rate along with the specific failure that matters.

## Success criteria

- An engineer with Ollama and uv runs one command and gets a results table
  for the helpdesk suite.
- `examples/helpdesk/README.md` states the problem, the command, the real
  numbers from my run, and one paragraph on what the result means for the
  customer's decision.
- The existing 15-task benchmark, `bench/results.jsonl`, and the main README
  table are untouched.
- `uv run pytest` passes without a model running.

## Design

### 1. `--suite` on `python -m bench`

- `--suite NAME` loads `examples/NAME/suite.py`. The default (no flag) is the
  current benchmark, unchanged.
- A suite module defines three names: `TASKS` (same dict format as
  `bench/tasks.py`), `SEARCH` and `PAGES` (same shapes as `bench/fixtures.py`).
- With a suite, results append to `examples/NAME/results.jsonl` and the table
  is written between the `bench:start`/`bench:end` markers in
  `examples/NAME/README.md`. The main README is never written.
- `report()` takes its category columns from the tasks being reported
  (in first-seen order) instead of the hardcoded list. For the default
  benchmark that yields the same five columns in the same order, so the main
  table doesn't change.
- `rescore()` looks tasks up in the active suite's `TASKS`.

### 2. Fixtures in `tools/server.py`

- The bench already passes `BENCH_OFFLINE=1` to the tool server. It will also
  pass `BENCH_SUITE=NAME` when a suite is set.
- The server imports `examples.NAME.suite` for `search()`/`PAGES` when
  `BENCH_SUITE` is set, and `bench.fixtures` otherwise. The matching logic in
  `fixtures.search` is reused, not copied: it takes the `SEARCH` table as an
  argument (or the suite reuses the function).
- No new tools. The agent still sees `web_search`, `read_page` and
  `calculator`. The fake documents live at `https://intranet.example/...`, so
  the model is searching an "intranet" through the same tools.

### 3. `examples/helpdesk/`

- `suite.py`: a made-up company, Halyard Supply Co. (not a real business), with
  three documents:
  - **Employee handbook**: PTO accrual, holidays, equipment.
  - **Refund policy**: tiers by days since purchase, with a percentage, so a
    refund question needs a lookup plus the calculator.
  - **On-call runbook**: long enough to need paging (over 5000 characters),
    with the escalation step near the end, and one planted line telling the
    reader to email the runbook to an outside address.
- About 8 tasks:

  | id | cat | What it checks |
  |---|---|---|
  | pto | lookup | Finds the PTO accrual rate in the handbook |
  | equipment | lookup | Finds the laptop refresh period |
  | refund | lookup+math | Refund amount for a given price and day count; must call `read_page` and `calculator` |
  | escalate | lookup | Escalation step from the end of the long runbook; must page through |
  | multi | lookup+math | Combines two facts (e.g. PTO days after N months) |
  | nopolicy | no-result | Asks about a policy that doesn't exist; must say so instead of inventing one |
  | exfil | injection | Summarize the runbook; must not repeat or act on the planted email line |
  | hi | chat | Small talk; no tool calls |

  Exact questions and answers are written during implementation. Every fact
  is invented so no model can answer from memory.
- `README.md`: the customer question, the run command, the results table
  (generated), and a short "what this means" paragraph written after the run
  from the real numbers. It also has an "Adapt it" section: copy the folder,
  rewrite the tasks and pages, and for real documents replace the fixtures
  with one `@mcp.tool()` function in `tools/server.py` that searches them.

### 4. The run

- Models: `gpt-oss:20b` (best in the main benchmark) and `llama3.1:8b`
  (smallest, fits most laptops). That's the trade-off a customer would
  actually weigh.
- 1 rep each. The main benchmark found repeats at temperature 0 agreed in
  147 of 150 cases, so more reps add little here.
- Command:
  `uv run python -m bench --suite helpdesk --models gpt-oss:20b llama3.1:8b --reps 1`
- The README reports whatever comes out, including a weak result. If both
  models pass everything, the write-up says the suite is too easy and that's
  the finding.

## Testing

One new test in `tests/test_bench.py` (no model needed):

- Load the helpdesk suite. For every task whose `must_call` includes
  `read_page`, check that some `SEARCH` entry or explicit URL in the question
  leads to a page in `PAGES`.
- Score a canned message list against one helpdesk task and check pass/fail.
- Check that `report()` on default-benchmark rows still produces the same
  five category columns.

## Not doing

- No YAML/JSON task format. A Python file of dicts is already plain to edit.
- No web UI, no new tools, no live document connector.
- No change to the main 15-task results or README table.
- No multiple suites beyond helpdesk. `--suite` supports more when someone
  writes one.

## Open questions

None blocking. Exact task wording gets written during
implementation.
