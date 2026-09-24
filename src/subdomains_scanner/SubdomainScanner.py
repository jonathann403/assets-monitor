"""Subdomain enumeration step.

Wraps ``src/massdns_scripts/recon.py`` (which drives MassDNS) to enumerate the
subdomains of a domain against a wordlist. The domain is always validated
upstream, and the tool is invoked as an argument list (never through a shell),
so no user input can influence anything but the values of these flags.
"""
import os
import subprocess

from src.common import ScannerError


class SubdomainScanner:
    def __init__(
        self,
        domain,
        wordlist,
        results_dir="results",
        recon_script=None,
        python_bin="python3",
    ):
        self.domain = domain
        self.wordlist = wordlist
        self.results_dir = results_dir
        self.python_bin = python_bin
        if recon_script is None:
            recon_script = os.path.join(
                os.path.dirname(__file__), "..", "massdns_scripts", "recon.py"
            )
        self.recon_script = os.path.abspath(recon_script)

        self.domain_dir = os.path.join(results_dir, domain)
        self.output_file = os.path.join(self.domain_dir, "subdomains.txt")

    def run(self):
        """Enumerate subdomains and return the number found.

        Raises :class:`ScannerError` if the wordlist is missing or the tool
        exits with an error.
        """
        os.makedirs(self.domain_dir, exist_ok=True)

        if not os.path.exists(self.wordlist):
            raise ScannerError(
                "Wordlist not found at %s" % self.wordlist
            )

        command = [
            self.python_bin,
            self.recon_script,
            "-d", self.domain,
            "-l", self.wordlist,
            "-w", self.output_file,
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
                "Could not run the enumeration tool (%s). Is Python and "
                "MassDNS installed and on your PATH?" % self.python_bin
            ) from exc

        if result.returncode != 0:
            detail = (result.stderr or "").strip().splitlines()
            hint = detail[-1] if detail else "unknown error"
            raise ScannerError("Subdomain enumeration failed: %s" % hint)

        return self.count_results()

    def count_results(self):
        """Number of non-empty subdomain lines written to the output file."""
        if not os.path.exists(self.output_file):
            return 0
        with open(self.output_file, "r", encoding="utf-8", errors="replace") as fh:
            return sum(1 for line in fh if line.strip())
