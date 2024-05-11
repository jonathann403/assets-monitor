import subprocess
import os


class SubdomainScanner:
    def __init__(self, domain, wordlist) -> None:
        self.command = None
        self.domain = domain
        self.wordlist = wordlist
        self.output_file = "results/" + domain

        if not os.path.exists(self.output_file):
            os.system("mkdir " + self.output_file)
        else:
            raise ValueError("Condition not met, class creation aborted.")
        self.output_file += "/subdomains.txt"

    def start_subdomain_scan(self):
        try:
            # Build the GoBuster command for DNS subdomain enumeration
            self.command = ['gobuster', 'dns', '-d', self.domain, '-t', '50',  '-q', '-r', '8.8.8.8', '-c']
            if self.wordlist:
                self.command.extend(['-w', self.wordlist])
            if self.output_file:
                self.command.extend(['-o', self.output_file])

            subprocess.run(self.command, capture_output=True, text=True)

        except FileNotFoundError:
            print("GoBuster tool not found. Make sure it's installed and in your PATH.")
