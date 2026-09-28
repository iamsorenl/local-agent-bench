"""MCP tool server. Every @mcp.tool() function here is picked up by the agent automatically."""
import ast
import operator
import os
import time
from urllib.parse import urlparse

import trafilatura
from ddgs import DDGS
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("tools", log_level="WARNING")

PAGE_CHARS = 5000
OFFLINE = os.environ.get("BENCH_OFFLINE") == "1"  # serve recorded results instead of the live web
if OFFLINE:
    from bench import fixtures


def untrusted(text: str) -> str:
    # Web content is data, not instructions. The system prompt tells the model so.
    return f"<untrusted>\n{text}\n</untrusted>"


@mcp.tool()
def web_search(query: str) -> str:
    """Search the web. Returns up to 5 results with title, url and snippet."""
    for attempt in range(3):
        try:
            hits = fixtures.search(query) if OFFLINE else DDGS().text(query, max_results=5)
            break
        except Exception as e:  # ddgs rate-limits under load
            if attempt == 2:
                return f"search failed: {e}"
            time.sleep(2 ** attempt)
    lines = [f"- {h['title']}\n  {h['href']}\n  {h['body']}" for h in hits]
    return untrusted("\n".join(lines) or "no results")


@mcp.tool()
def read_page(url: str, offset: int = 0) -> str:
    """Read a web page as plain text, 5000 characters at a time. Use offset to read further."""
    if urlparse(url).scheme not in ("http", "https"):
        return "only http(s) urls are allowed"
    if OFFLINE:
        text = fixtures.PAGES.get(url)
    else:
        html = trafilatura.fetch_url(url)
        text = trafilatura.extract(html) if html else None
    if not text:
        return f"could not read {url}"
    return untrusted(clip(text, offset))


def clip(text: str, offset: int) -> str:
    offset = max(0, offset)
    chunk = text[offset:offset + PAGE_CHARS]
    if not chunk:
        return "[end of page]"
    end = offset + len(chunk)
    if end < len(text):
        chunk += f"\n[{len(text) - end} more characters, call again with offset={end}]"
    return chunk


OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _eval(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("exponent too large")
        return OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.operand))
    raise ValueError("only numbers and + - * / // % ** are allowed")


@mcp.tool()
def calculator(expression: str) -> str:
    """Evaluate arithmetic, e.g. '0.175 * 2340'. Numbers and + - * / // % ** only."""
    try:
        return str(_eval(ast.parse(expression, mode="eval").body))
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError) as e:
        return f"error: {e}"


if __name__ == "__main__":
    mcp.run()
