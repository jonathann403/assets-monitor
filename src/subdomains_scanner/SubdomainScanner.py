import subprocess
import os


class SubdomainScanner:
    def __init__(self, domain, wordlist) -> None:
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
            # python3 recon.py -d google.com -l ./wordlists/subdomains/httparchive_subdomains_2024_04_28.txt > res.txt
            command = ['python3', './src/massdns_scripts/recon.py', '-d', self.domain, '-l', self.wordlist, '-w', self.output_file]

            subprocess.run(command)

        except FileNotFoundError:
            print("GoBuster tool not found. Make sure it's installed and in your PATH.")
