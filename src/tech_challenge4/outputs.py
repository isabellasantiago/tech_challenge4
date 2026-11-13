"""Saídas locais com falhas observáveis, sem interromper os analisadores."""
import json
import sys


class LocalAlertSink:
    def __init__(self, path):
        self.errors = []
        self.stream = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.stream = path.open("a", encoding="utf-8")
        except OSError as exc:
            self.errors.append({"path": str(path), "error": str(exc)})

    def __call__(self, alert):
        print(json.dumps(alert.to_dict(), ensure_ascii=False, allow_nan=False))
        if self.stream is not None:
            try:
                self.stream.write(json.dumps(alert.to_dict(), ensure_ascii=False, allow_nan=False) + "\n")
                self.stream.flush()
            except (OSError, ValueError, TypeError) as exc:
                self.errors.append({"output": "alerts", "error": str(exc)})

    def close(self):
        if self.stream is not None:
            try:
                self.stream.close()
            except OSError as exc:
                self.errors.append({"output": "alerts", "error": str(exc)})
        for error in self.errors:
            print(f"Erro ao gravar JSONL: {error['error']}", file=sys.stderr)
