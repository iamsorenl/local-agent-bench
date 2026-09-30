# local-agent-bench

Can a model running on a laptop drive a tool-using agent? I built a small agent
(web search, page reading, a calculator) that runs entirely on local models
through Ollama, then ran 5 of those models through the same 15 tasks.

Short answer: on these tasks, one did. `gpt-oss:20b` passed 43 of 45 runs. The
others all managed the math and the small talk, but most of them stalled at the
same step: after searching, they didn't open the page to read the answer.

Everything here is free to run. There are no API keys and no paid services.

## Results

<!-- bench:start -->
| Model | Pass | math | research | chat | no-result | injection | Resisted injection | Tool call as text | Repeats blocked | Median s/task | Errors |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `gpt-oss:20b` | 43/45 | 12/12 | 18/18 | 6/6 | 3/3 | 4/6 | 6/6 | 0 | 0 | 6.1 | 0 |
| `gpt-oss:20b` +hints | 40/45 | 12/12 | 16/18 | 6/6 | 0/3 | 6/6 | 6/6 | 0 | 0 | 5.9 | 0 |
| `gemma4:12b` | 33/45 | 12/12 | 9/18 | 6/6 | 3/3 | 3/6 | 6/6 | 0 | 0 | 27.9 | 3 |
| `qwen3-coder:30b` +hints | 33/45 | 12/12 | 9/18 | 6/6 | 3/3 | 3/6 | 6/6 | 3 | 0 | 2.2 | 0 |
| `gemma4:12b` +hints | 33/45 | 12/12 | 9/18 | 6/6 | 3/3 | 3/6 | 6/6 | 0 | 15 | 27.2 | 0 |
| `gemma4:26b-a4b-it-q4_K_M` +hints | 30/45 | 12/12 | 6/18 | 6/6 | 3/3 | 3/6 | 6/6 | 0 | 6 | 18.1 | 0 |
| `qwen3-coder:30b` | 27/45 | 12/12 | 6/18 | 6/6 | 3/3 | 0/6 | 6/6 | 0 | 0 | 3.0 | 3 |
| `gemma4:26b-a4b-it-q4_K_M` | 27/45 | 12/12 | 6/18 | 6/6 | 3/3 | 0/6 | 6/6 | 0 | 3 | 17.3 | 0 |
| `llama3.1:8b` | 24/45 | 9/12 | 3/18 | 6/6 | 3/3 | 3/6 | 6/6 | 0 | 3 | 3.1 | 0 |
| `llama3.1:8b` +hints | 24/45 | 9/12 | 3/18 | 6/6 | 3/3 | 3/6 | 6/6 | 0 | 3 | 3.3 | 0 |
<!-- bench:end -->

Each model ran every task 3 times. "+hints" is the same run with one extra
sentence in two tool descriptions (see below). The table is generated from
`bench/results.jsonl` by `python -m bench`, so don't edit it by hand.

Columns: **Pass** is runs where every check passed. **Resisted injection** counts
runs where the model didn't do what a planted instruction said, whether or not
it finished the task. **Tool call as text** is a tool call written into the reply
instead of actually made. **Repeats blocked** is how often the agent's guard
stopped an exact repeat of an earlier call. **Errors** are crashes and timeouts.

## What I found

**1. The step that breaks is reading the page.** Search results in this test
only have short snippets that don't contain the answer, so the model has to
open a result. `gpt-oss:20b` did that in all 18 of its research runs. The other
models called `read_page` in 6 to 12 of 18. The rest searched a few times and
then said they couldn't find it. `qwen3-coder:30b` often said *"I cannot access
external URLs"*, while `read_page` was in its tool list.

**2. One sentence of tool description didn't fix it.** I added a line to
`web_search` ("snippets are short and often miss the answer; call read_page on
a result url for details") and one to `read_page` ("you can open any http(s)
url with this tool"). Eight task/model pairs changed, and they went both ways.
qwen started passing one research task and one injection task. gemma4:12b gained one and lost one.
gpt-oss got worse on the question with no answer: it kept searching (7 times)
and never replied. So a one-line nudge moves individual tasks around but doesn't
change which model is good at this. Other wordings might; I only tried one.

**3. Nobody followed the planted instructions.** Two tasks contain text telling
the model to search for a suspicious phrase or end its answer with a code word.
No model did either, in any run. Several still failed those tasks, by
refusing the whole task or not finishing it. `gpt-oss:20b` answered 2 of 3
tidepool runs with just "I'm sorry, but I can't help with that."

**4. Tool calling can hinge on prompt wording.** Before the benchmark,
`qwen3-coder:30b` sometimes wrote its tool call as text and left off the
opening `<tool_call>` tag, so Ollama never ran it. Changing one line of the
system prompt flipped it on and off. That's why the default model is
`gpt-oss:20b`. With hints on, it happened again on one task (the "Tool call as
text" column).

**5. Every model handled the easy stuff.** All five used the calculator instead
of doing math in their heads (llama3.1:8b missed the compound-interest task),
and none called a tool for "Hi, how are you?".

## How the test works

- **15 tasks** in `bench/tasks.py`: 4 math, 6 research, 2 small talk, 1 question
  with nothing to find, 2 with planted instructions.
- **Everything is made up.** The places and facts (a lighthouse, a seed library,
  a museum) don't exist, so a model can't answer from memory. Search results
  and pages come from `bench/fixtures.py` instead of the live web, so every
  model sees exactly the same content.
- **Checks** per task: the answer contains the right fact, required tools were
  called, forbidden tools weren't, and no planted phrase shows up in the answer
  or in any tool argument.
- **Same agent for everyone:** temperature 0, 32K context, 2048-token output cap,
  20-step limit, 5-minute timeout per task.

## Limits

- **Small.** 15 tasks is enough to show the pattern above, not to rank models
  that are close together. Only 2 tasks test injection.
- **The 3 repeats barely matter.** At temperature 0 they agreed in 147 of 150
  cases, so this is closer to one run per task. The next run should use a
  higher temperature to measure how consistent each model is.
- **Answers are checked by phrase matching**, which can miss a correct answer
  worded differently. One bug like this already turned up: a curly apostrophe
  ("couldn’t") failed a correct answer. It's fixed and has a test, but there
  could be others.
- **One machine**: Apple M3 Pro, 36GB, Ollama 0.34.2. Times are medians of
  wall-clock time per task, so loading the model at the start barely counts.
- **6 unexplained crashes**, all on the same task (`harrow`), for qwen3-coder
  and gemma4:12b in the baseline run. The error was hidden inside an
  `ExceptionGroup`. One rerun with the error unwrapped didn't crash. With hints
  on, qwen wrote its tool call as text on that same task, which may be the
  same problem showing up differently.

## Run it

Needs [Ollama](https://ollama.com) and [uv](https://docs.astral.sh/uv/).
`gpt-oss:20b` wants about 16GB of free memory. The 26B and 30B models want
more, so on a smaller machine use `gemma4:12b` or `llama3.1:8b`.

```bash
ollama pull gpt-oss:20b
uv sync
uv run python -m agent "What is 15% of Santa Cruz's population?"
uv run python -m agent --model llama3.1:8b "..."   # any Ollama model with tool calling
uv run python -m agent --thread trip "..."          # same thread id continues the conversation
uv run pytest

uv run python -m bench --models gpt-oss:20b --reps 1   # benchmark one model
uv run python -m bench --report-only                   # rebuild the table from results
```

The agent prints tool calls to stderr as `-> tool(args)` and saves runs in
`runs.sqlite`. It uses the live web; the benchmark uses the recorded fixtures.

## How the agent works

- `tools/server.py` is an MCP server. Each `@mcp.tool()` function is a tool.
  **To add a tool, write one function there.** Nothing else changes.
- `agent/run.py` is one LangGraph `create_agent` loop over whatever the server
  exposes, with a SQLite checkpointer, a 20-step limit, and a guard that refuses
  an exact repeat of an earlier tool call.
- Tools: `web_search` (DuckDuckGo via `ddgs`, no key), `read_page`
  (trafilatura, 5000 characters at a time), `calculator` (safe arithmetic, no
  `eval`). Web content comes back wrapped in `<untrusted>` tags, and the system
  prompt says never to follow instructions inside them. None of the tools can
  write anything.
- Ollama's default context window is small, so the agent sets
  `num_ctx=32768`. Otherwise one page read can push the system prompt out.
