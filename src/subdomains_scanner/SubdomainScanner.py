import sublist3r
import subprocess, os


class SubdomainScanner:
    def __init__(self, domain, wordlist, output_file) -> None:
        self.domain = domain
        self.wordlist = wordlist
        self.output_file = output_file + domain

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
            result = subprocess.run(command, capture_output=True, text=True)

            # Check if the command was successful
            if result.returncode == 0:
                # If output file is specified, return None
                if self.output_file:
                    return None
                # Parse the output to extract subdomains
                subdomains = self.parse_gobuster_output(result.stdout)

                # Return the list of subdomains
                return subdomains
            else:
                # If the command failed, print the error message
                print("Error:", result.stderr)
                return []
        except FileNotFoundError:
            print("GoBuster tool not found. Make sure it's installed and in your PATH.")
            return []

    @staticmethod
    def parse_gobuster_output(output):
        # Split the output into lines and extract subdomains
        lines = output.split('\n')
        subdomains = [line.strip() for line in lines if
                      line.strip() and not line.startswith('====================================================')]
        return subdomains
