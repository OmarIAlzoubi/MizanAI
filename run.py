from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import webbrowser

from pathlib import Path


ROOT = Path(
    __file__
).resolve().parent

CONFIG_PATH = (
    ROOT
    / "config"
    / "mizanai.json"
)


def main() -> None:

    if not CONFIG_PATH.exists():

        print(
            "MizanAI has not been "
            "configured yet."
        )

        print(
            "\nRun:\n"
            "    python setup.py"
        )

        raise SystemExit(
            1
        )

    config = json.loads(
        CONFIG_PATH.read_text(
            encoding="utf-8"
        )
    )

    mode = config.get(
        "mode",
        "local",
    )

    worker = None

    try:

        if mode == "aws_whatsapp":

            print(
                "Starting WhatsApp worker..."
            )

            worker = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    (
                        "app.infrastructure."
                        "messaging.sqs_worker"
                    ),
                ],
                cwd=ROOT,
            )

        print(
            "\nStarting MizanAI..."
        )

        print(
            "Dashboard: "
            "http://127.0.0.1:8000"
        )

        print(
            "Press Ctrl+C to stop.\n"
        )

        threading.Thread(
            target=_open_browser,
            daemon=True,
        ).start()

        web = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=ROOT,
        )

        return_code = web.wait()

        raise SystemExit(
            return_code
        )

    except KeyboardInterrupt:

        print(
            "\nStopping MizanAI..."
        )

    finally:

        if worker is not None:

            worker.terminate()

            try:
                worker.wait(
                    timeout=5
                )
            except subprocess.TimeoutExpired:
                worker.kill()


def _open_browser() -> None:

    time.sleep(
        1.5
    )

    webbrowser.open(
        "http://127.0.0.1:8000"
    )


if __name__ == "__main__":
    main()
