"""End to end through the real MCP server, with a scripted model instead of Ollama."""
import asyncio

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from agent import run


class Scripted(BaseChatModel):
    replies: list

    @property
    def _llm_type(self):
        return "scripted"

    def bind_tools(self, tools, **kw):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kw):
        return ChatResult(generations=[ChatGeneration(message=self.replies.pop(0))])


def calc(expr, id):
    return {"name": "calculator", "args": {"expression": expr}, "id": id, "type": "tool_call"}


def run_scripted(replies, tmp_path):
    return asyncio.run(run.ask("q", Scripted(replies=replies), db=str(tmp_path / "t.sqlite"), verbose=False))[-1].text


def tool_results(tmp_path):
    async def read():
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        async with AsyncSqliteSaver.from_conn_string(str(tmp_path / "t.sqlite")) as s:
            state = await run.build_agent(Scripted(replies=[]), [], s).aget_state(
                {"configurable": {"thread_id": "default"}})
            return [m.text for m in state.values["messages"] if isinstance(m, ToolMessage)]
    return asyncio.run(read())


def test_calls_mcp_tool_and_answers(tmp_path):
    assert run_scripted([AIMessage("", tool_calls=[calc("6 * 7", "a")]), AIMessage("42")], tmp_path) == "42"
    assert tool_results(tmp_path) == ["42"]


def test_loop_guard_blocks_repeat_call(tmp_path):
    run_scripted([
        AIMessage("", tool_calls=[calc("1 + 1", "a")]),
        AIMessage("", tool_calls=[calc("1 + 1", "b")]),
        AIMessage("2"),
    ], tmp_path)
    first, second = tool_results(tmp_path)
    assert first == "2"
    assert "already made this exact call" in second
