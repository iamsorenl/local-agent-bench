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

Measuring these properly across models is the next step.
