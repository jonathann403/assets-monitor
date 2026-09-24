"""HTTP probing step.

Runs `httpx <https://github.com/projectdiscovery/httpx>`_ over the enumerated
subdomains to discover which respond over HTTP(S) and to collect metadata
(title, status code, technologies, server, ...).

Security note: the previous implementation built a ``cat file | httpx ...``
string and ran it with ``shell=True``, which allowed shell metacharacters in
the domain-derived path to be executed. This version passes the input file to
httpx with ``-l`` and invokes it as an argument list, so no shell is involved.
"""
import json
import os
import subprocess

from src.common import ScannerError


class HttpxScanner:
    def __init__(self, input_file, domain, results_dir="results", httpx_bin="httpx"):
        self.input_file = input_file
        self.domain = domain
        self.results_dir = results_dir
        self.httpx_bin = httpx_bin

        self.domain_dir = os.path.join(results_dir, domain)
        self.output_file = os.path.join(self.domain_dir, "httpx.json")
        self.raw_file = os.path.join(self.domain_dir, "httpx.jsonl")

    def run(self):
        """Probe the hosts and return the number of live results.

        Writes a well-formed JSON array to ``httpx.json`` (consumed by the web
        app) and keeps the raw JSONL httpx emitted in ``httpx.jsonl``.
        """
        os.makedirs(self.domain_dir, exist_ok=True)

        if not os.path.exists(self.input_file) or os.path.getsize(self.input_file) == 0:
            # Nothing was enumerated; write an empty result set rather than
            # failing so the domain still shows up with zero live hosts.
            self._write_results([])
            return 0

        command = [
            self.httpx_bin,
            "-l", self.input_file,
            "-json",
            "-silent",
            "-no-color",
            "-status-code",
            "-title",
            "-tech-detect",
            "-web-server",
            "-content-length",
            "-timeout", "10",
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ScannerError(
                "httpx not found. Install it from "
                "https://github.com/projectdiscovery/httpx and make sure it is "
                "on your PATH."
            ) from exc

        if result.returncode != 0 and not result.stdout.strip():
            detail = (result.stderr or "").strip().splitlines()
            hint = detail[-1] if detail else "unknown error"
            raise ScannerError("httpx probing failed: %s" % hint)

        results = self._parse_jsonl(result.stdout)

        # Persist the raw JSONL for auditing/debugging.
        with open(self.raw_file, "w", encoding="utf-8") as fh:
            fh.write(result.stdout)

        self._write_results(results)
        return len(results)

    @staticmethod
    def _parse_jsonl(text):
        """Parse httpx's JSON-lines output, skipping any non-JSON noise."""
        results = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                # httpx occasionally emits a non-JSON status line; ignore it.
                continue
        return results

    def _write_results(self, results):
        with open(self.output_file, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2)
