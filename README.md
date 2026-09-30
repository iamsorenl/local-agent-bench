# local-agent-bench

A free, local tool-using agent, and (soon) a benchmark of which local models
can actually drive it. Built from the public LangGraph, MCP and Ollama docs.

## Run it

Needs [Ollama](https://ollama.com) and [uv](https://docs.astral.sh/uv/).
The default model, `gpt-oss:20b`, wants about 16GB of free RAM.

```bash
ollama pull gpt-oss:20b
uv sync
uv run python -m agent "What is 15% of Santa Cruz's population?"
uv run python -m agent --model llama3.1:8b "..."        # any Ollama model with tool calling
uv run python -m agent --thread trip "..."               # same thread id = continues the conversation
uv run pytest
```

Tool calls print to stderr as `-> tool(args)`. Runs are saved in `runs.sqlite`.

## How it works

- `tools/server.py`: an MCP server. Each `@mcp.tool()` function is a tool.
  **To add a tool, write one function there.** Nothing else changes.
- `agent/run.py`: one LangGraph `create_agent` loop over whatever the server
  exposes, with a SQLite checkpointer, a 20-step limit, and a guard that
  refuses an exact repeat of an earlier tool call.

Tools: `web_search` (DuckDuckGo via `ddgs`, no key), `read_page` (trafilatura,
5000 characters at a time), `calculator` (safe arithmetic, no `eval`).
Web content comes back wrapped in `<untrusted>` tags, and the system prompt
says never to follow instructions inside them. There are no tools that write
anything.

## Things already noticed

- `qwen3-coder:30b` sometimes writes its tool call as plain text and drops the
  opening `<tool_call>` tag, so Ollama never runs it. Whether it happens
  depends on the system prompt wording and on how many tools it has. At
  temperature 0 the same inputs fail the same way every time.
  `gpt-oss:20b` made real tool calls on every test prompt, so it's the default.
- Told to read a specific URL, `gpt-oss:20b` sometimes searches instead.
- Ollama's default context window is small. The agent sets `num_ctx=32768`,
  otherwise a single page read can push out the system prompt.

## Results

`uv run python -m bench` runs 15 tasks (math, research, small talk, a question
with no answer, and two prompt-injection pages) against recorded search results
and pages about made-up places, so no model can answer from memory. The table
below is generated from `bench/results.jsonl`. Don't edit it by hand.

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
