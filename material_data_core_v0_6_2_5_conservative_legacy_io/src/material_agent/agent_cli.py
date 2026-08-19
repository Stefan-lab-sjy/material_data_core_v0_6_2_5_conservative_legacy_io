from __future__ import annotations

import argparse

from .agent_runtime import MaterialAgentRuntime
from .agent_tools import MaterialAgentTools
from .app import build_services


def build_runtime(data_root=None) -> tuple[MaterialAgentRuntime, object]:
    settings, repo, _, _, calcs = build_services(data_root)
    tools = MaterialAgentTools(repo, calcs)
    return MaterialAgentRuntime(tools), settings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Material Agent Runtime v0.6.2")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--once", help="Run one request and exit")
    args = parser.parse_args(argv)

    runtime, settings = build_runtime(args.data_root)
    if args.once is not None:
        print(runtime.ask(args.once).text)
        return 0

    print("=" * 72)
    print("MATERIAL AGENT v0.6.2 - LOCAL TOOL RUNTIME")
    print("=" * 72)
    print(f"Data root : {settings.data_root}")
    print(f"Catalog   : {settings.db_path}")
    print()
    print("This is the first Agent runtime. It uses deterministic tool routing; no LLM API is required yet.")
    print("Type help for commands, exit to quit.")
    print()

    while True:
        try:
            message = input("material-agent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if message.lower() in {"exit", "quit", "q", "退出"}:
            break
        reply = runtime.ask(message)
        print(reply.text)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
