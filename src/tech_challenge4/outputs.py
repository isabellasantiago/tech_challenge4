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
        payload = json.dumps(alert.to_dict(), ensure_ascii=False, allow_nan=False)
        try:
            print(payload, flush=True)
        except (OSError, UnicodeError) as exc:
            self.errors.append({"output": "console", "error": str(exc)})
        if self.stream is not None:
            try:
                self.stream.write(payload + "\n")
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
            try:
                print(f"Erro na saída {error.get('output', 'alerts')}: {error['error']}",
                      file=sys.stderr, flush=True)
            except (OSError, UnicodeError):
                # Preserva os erros para o relatório mesmo se stderr também falhar.
                pass
