import subprocess
import os


class HttpxScanner:
    def __init__(self, input_file, domain) -> None:
        self.input_file = input_file
        self.output_file = "results/" + domain + "/httpx.json"
        self.domain = domain

        if not os.path.exists(self.output_file):
            os.system("touch " + self.output_file)
        else:
            raise ValueError("Condition not met, class creation aborted.")

    def start(self):
        try:
            # httpx -l list -title -status-code -tech-detect -follow-redirects
            command = ['cat', self.input_file, '|', 'httpx', '-title', '-status-code', '-tech-detect', '-server', '-lc', '-wc', '-silent', '-j', '-o', self.output_file]

            try:
                subprocess.run(" ".join(command), shell=True, check=True)
                with open(self.output_file, 'r') as f:
                    lines = f.readlines()

                try:
                    lines[0] = '[\n' + lines[0]
                    lines = [line.rstrip('\n') + ',' for line in lines]
                    lines[-1] = lines[-1][:-1] + '\n]'
                except Exception as e:
                    raise Exception("Httpx couldn't resolve those subdomains.")

                with open(self.output_file, 'w') as f:
                    f.writelines(lines)

            except subprocess.CalledProcessError as e:
                print(f"Error executing command: {e}")

        except FileNotFoundError:
            raise Exception("Httpx tool not found. Make sure it's installed and in your PATH.")
