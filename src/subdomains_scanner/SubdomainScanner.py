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
            command = ['gobuster', 'dns', '-d', self.domain]
            if self.wordlist:
                command.extend(['-w', self.wordlist])
            if self.output_file:
                command.extend(['-o', self.output_file])

            # Run GoBuster command to scan subdomains
            before = datetime.datetime.now()
            result = subprocess.run(command, capture_output=True, text=True)
            after = datetime.datetime.now()

            # Check if the command was successful
            if result.returncode == 0:
                return after - before
            else:
                # If the command failed, print the error message
                print("Error:", result.stderr)
                return []
        except FileNotFoundError:
            print("GoBuster tool not found. Make sure it's installed and in your PATH.")
            return []
