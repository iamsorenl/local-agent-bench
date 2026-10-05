# Privacy

local-agent-bench runs on your machine. It has no accounts, no telemetry, and no server of its own.

What leaves your machine:

- `web_search` sends your query to DuckDuckGo (through the `ddgs` library).
- `read_page` fetches the URL the model asks for, from that site.
- With `BENCH_OFFLINE=1`, neither happens. Both tools serve recorded results.

The model runs locally through Ollama. Conversation history is kept in a local SQLite file and nowhere else.
