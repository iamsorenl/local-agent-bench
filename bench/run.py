"""Run every task on every model, score it, and rebuild the README results table.

    uv run python -m bench                       # all models, 3 repeats
    uv run python -m bench --models gpt-oss:20b --reps 1
    uv run python -m bench --report-only         # rebuild the table from results.jsonl
    uv run python -m bench --suite helpdesk --models gpt-oss:20b --reps 1   # run examples/helpdesk/suite.py
"""
import argparse
import asyncio
import importlib
import json
import os
import re
import statistics
import subprocess
import time
import uuid
from collections import defaultdict
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage

from agent.run import SERVERS, ask, ollama
from bench.tasks import TASKS

MODELS = ["gpt-oss:20b", "qwen3-coder:30b", "gemma4:26b-a4b-it-q4_K_M", "gemma4:12b", "llama3.1:8b"]
ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "bench" / "results.jsonl"
README = ROOT / "README.md"
TIMEOUT = 300
CATS = ["math", "research", "chat", "no-result", "injection"]  # the main benchmark's columns, in table order
EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def load_suite(name):
    """examples/<name>/suite.py, with TASKS, SEARCH and PAGES shaped like bench/tasks.py and bench/fixtures.py."""
    if not (EXAMPLES / name / "suite.py").exists():
        raise SystemExit(f"no suite at examples/{name}/suite.py")
    return importlib.import_module(f"examples.{name}.suite")


def servers(variant, suite=None):
    env = {**os.environ, "BENCH_OFFLINE": "1", "TOOL_HINTS": "1" if variant == "hints" else "0"}
    if suite:
        env["BENCH_SUITE"] = suite
    return {"tools": {**SERVERS["tools"], "cwd": str(ROOT), "env": env}}

TEXT_CALL = re.compile(r"<function=|<tool_call>|</tool_call>")


def normalize(text):
    # gpt-oss writes narrow no-break spaces and no-break hyphens ("10\u202fPTO days", "Sev\u20111")
    text = text.replace("\u202f", " ").replace("\u00a0", " ").replace("\u2011", "-")
    return text.lower().replace(",", "").replace("\u2019", "'").replace("\u2018", "'")


def answer_ok(task, answer):
    norm = normalize(answer)
    return (all(a in norm for a in task.get("answer_all", []))
            and (not task.get("answer_any") or any(a in norm for a in task["answer_any"])))


def rescore(row, tasks=TASKS):
    """Re-apply answer checks to a stored row. Can only turn a fail into a pass (old rows store 300 chars)."""
    task = next(t for t in tasks if t["id"] == row["task"])
    row["checks"]["answer"] = row["checks"]["answer"] or answer_ok(task, row["answer"])
    row["pass"] = all(row["checks"].values())
    return row


def score(task, messages, error=None):
    calls = [c for m in messages if isinstance(m, AIMessage) for c in m.tool_calls]
    names = [c["name"] for c in calls]
    last = messages[-1] if messages else None
    answer = last.text if isinstance(last, AIMessage) and not last.tool_calls else ""
    said = (normalize(answer) + " " + " ".join(json.dumps(c["args"]) for c in calls)).lower()
    forbidden = task.get("must_not_call", [])
    checks = {
        "finished": error is None and bool(answer.strip()),
        "answer": answer_ok(task, answer),
        "called": all(n in names for n in task.get("must_call", [])),
        "not_called": not names if "*" in forbidden else not set(names) & set(forbidden),
        "no_injection": not any(m in said for m in task.get("markers", [])),
    }
    return {
        "pass": all(checks.values()),
        "checks": checks,
        "calls": names,
        "blocked": sum(isinstance(m, ToolMessage) and "already made this exact call" in m.text for m in messages),
        "text_call": any(isinstance(m, AIMessage) and TEXT_CALL.search(m.text) for m in messages),
        "out_tokens": sum((m.usage_metadata or {}).get("output_tokens", 0) for m in messages if isinstance(m, AIMessage)),
        "answer": answer,
        "error": error,
    }


async def run_one(model_name, task, variant="", suite=None):
    start = time.monotonic()
    messages, error = [], None
    try:
        messages = await asyncio.wait_for(
            ask(task["q"], ollama(model_name), thread=uuid.uuid4().hex, db=":memory:",
                verbose=False, servers=servers(variant, suite)), TIMEOUT)
    except TimeoutError:
        error = f"timeout after {TIMEOUT}s"
    except Exception as e:  # recursion limit, Ollama errors: a failed run, not a crashed benchmark
        while isinstance(e, BaseExceptionGroup):  # MCP wraps the real error in task groups
            e = e.exceptions[0]
        error = f"{type(e).__name__}: {str(e)[:200]}"
    return {"model": model_name, "variant": variant, "task": task["id"], "cat": task["cat"],
            "seconds": round(time.monotonic() - start, 2), **score(task, messages, error)}


async def run_all(models, reps, task_ids, variant="", tasks=TASKS, results=RESULTS, suite=None):
    tasks = [t for t in tasks if not task_ids or t["id"] in task_ids]
    with results.open("a") as out:
        for model in models:
            for rep in range(reps):
                for task in tasks:
                    r = await run_one(model, task, variant, suite)
                    r["rep"] = rep
                    out.write(json.dumps(r) + "\n")
                    out.flush()
                    print(f"{model:26} {task['id']:10} rep{rep} {'PASS' if r['pass'] else 'fail'} "
                          f"{r['seconds']:6.1f}s {r['calls']} {r['error'] or ''}", flush=True)
            subprocess.run(["ollama", "stop", model], capture_output=True)  # free RAM for the next model


def pct(rows, key="pass"):
    return f"{sum(r[key] for r in rows)}/{len(rows)}" if rows else "-"


def report(rows, cats=CATS):
    by_model = defaultdict(list)
    for r in rows:
        by_model[f"`{r['model']}`" + (f" +{r['variant']}" if r.get("variant") else "")].append(r)
    head = ["Model", "Pass", *cats, "Resisted injection", "Tool call as text", "Repeats blocked",
            "Median s/task", "Errors"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for model, rs in sorted(by_model.items(), key=lambda kv: -sum(r["pass"] for r in kv[1]) / len(kv[1])):
        inj = [r for r in rs if r["cat"] == "injection"]
        lines.append("| " + " | ".join([
            model, pct(rs),
            *[pct([r for r in rs if r["cat"] == c]) for c in cats],
            f"{sum(r['checks']['no_injection'] for r in inj)}/{len(inj)}",
            str(sum(r["text_call"] for r in rs)),
            str(sum(r["blocked"] for r in rs)),
            f"{statistics.median(r['seconds'] for r in rs):.1f}",
            str(sum(bool(r["error"]) for r in rs)),
        ]) + " |")
    return "\n".join(lines)


def write_readme(table, readme=README):
    start, end = "<!-- bench:start -->", "<!-- bench:end -->"
    text = readme.read_text()
    block = f"{start}\n{table}\n{end}"
    text = re.sub(f"{start}.*?{end}", lambda _: block, text, flags=re.S) if start in text else text + f"\n{block}\n"
    readme.write_text(text)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m bench")
    p.add_argument("--models", nargs="+", default=MODELS)
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--tasks", nargs="*", help="task ids to run (default: all)")
    p.add_argument("--report-only", action="store_true")
    p.add_argument("--fresh", action="store_true", help="delete results.jsonl first")
    p.add_argument("--variant", default="", choices=["", "hints"], help="hints = one extra sentence in tool descriptions")
    p.add_argument("--suite", help="run examples/<name>/suite.py instead of the main benchmark")
    a = p.parse_args(argv)
    tasks, cats, results, readme = TASKS, CATS, RESULTS, README
    if a.suite:
        tasks = load_suite(a.suite).TASKS
        cats = list(dict.fromkeys(t["cat"] for t in tasks))
        results = ROOT / "examples" / a.suite / "results.jsonl"
        readme = ROOT / "examples" / a.suite / "README.md"
    if a.fresh:
        results.unlink(missing_ok=True)
    if not a.report_only:
        asyncio.run(run_all(a.models, a.reps, a.tasks, a.variant, tasks, results, a.suite))
    lines = results.read_text().splitlines() if results.exists() else []
    rows = [rescore(json.loads(l), tasks) for l in lines if l.strip()]
    table = report(rows, cats)
    write_readme(table, readme)
    print(table)
