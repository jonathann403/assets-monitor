import sublist3r
import datetime
import subprocess, os


class SubdomainScanner:
    def __init__(self, domain, wordlist) -> None:
        self.domain = domain
        self.wordlist = wordlist
        self.output_file = "results/" + domain

        os.system("mkdir " + self.output_file)
        self.output_file += "/subdomains.txt"

    def start_subdomain_scan(self):
        try:
            # Build the GoBuster command for DNS subdomain enumeration
            command = ['gobuster', 'dns', '-d', self.domain, '-t', '50']
            if self.wordlist:
                command.extend(['-w', self.wordlist])
            if self.output_file:
                command.extend(['-o', self.output_file])

            result = subprocess.run(command, capture_output=True, text=True)

        except FileNotFoundError:
            print("GoBuster tool not found. Make sure it's installed and in your PATH.")
