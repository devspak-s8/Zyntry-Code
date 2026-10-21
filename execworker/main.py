"""CLI entrypoint for the Zyntry Code execworker.

    python -m execworker.main --backend http://localhost:8787 --once
"""

import argparse
import asyncio
import logging
import os
import uuid

from execworker.runner import Runner


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def main() -> None:
    parser = argparse.ArgumentParser(description="Zyntry Code execution worker")
    parser.add_argument("--backend", default=_env("ZYNTRY_BACKEND_URL", "http://localhost:8787"))
    parser.add_argument("--token", default=_env("ZYNTRY_RUNNER_TOKEN") or _env("ZYNTRY_TOKEN"))
    parser.add_argument("--api-token", default=_env("ZYNTRY_TOKEN"))
    parser.add_argument("--id", dest="worker_id", default=_env("ZYNTRY_WORKER_ID") or f"worker-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--name", default=_env("ZYNTRY_WORKER_NAME", "default"))
    parser.add_argument("--dir", dest="workspaces_dir",
                        default=_env("ZYNTRY_WORKSPACES_DIR", os.path.join(os.getcwd(), "workspaces")))
    parser.add_argument("--heartbeat", type=int, default=int(_env("WORKER_HEARTBEAT_SECONDS", "30")))
    parser.add_argument("--poll", type=int, default=int(_env("WORKER_POLL_SECONDS", "5")))
    parser.add_argument("--cpu-limit", type=float,
                        default=float(_env("ZYNTRY_CPU_LIMIT_SECONDS", "120")),
                        help="kernel CPU-time cap per command, seconds (0 disables; POSIX only)")
    parser.add_argument("--mem-limit-mb", type=int,
                        default=int(_env("ZYNTRY_MEM_LIMIT_MB", "1024")),
                        help="kernel address-space cap per command, MB (0 disables; POSIX only)")
    parser.add_argument("--once", action="store_true", help="process available requests and exit")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    runner = Runner(
        backend_url=args.backend, token=args.token, worker_id=args.worker_id,
        name=args.name, workspaces_dir=args.workspaces_dir,
        heartbeat_seconds=args.heartbeat, poll_seconds=args.poll,
        cpu_limit=args.cpu_limit, mem_limit_mb=args.mem_limit_mb,
        api_token=args.api_token)

    async def run() -> None:
        if args.once:
            await runner.register()
            total = 0
            for _ in range(50):  # drain all pending workspaces, then exit
                processed = await runner.run_once()
                total += processed
                if processed == 0:
                    break
            print(f"processed {total} tool request(s)")
            return
        await runner.serve()

    asyncio.run(run())


if __name__ == "__main__":
    main()
