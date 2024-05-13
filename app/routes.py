from flask import Blueprint, render_template, request
from threading import Thread
import json
import os

from src.subdomains_scanner import SubdomainScanner
from src.httpx_scanner import HttpxScanner

bp = Blueprint('main', __name__)

def run_scanner(domain):
    try:
        subdomain_scanner = SubdomainScanner(domain, "./wordlists/subdomains/httparchive_subdomains_2024_04_28.txt")
        subdomain_scanner.start()

        httpx_scanner = HttpxScanner(subdomain_scanner.output_file, domain)
        httpx_scanner.start()
    except Exception as e:
        print(e)

@bp.route('/', methods=['GET'])
def index():
    domain = request.args.get('domain')  # Get the value of 'domain' from the query string
    domains = [f.path.split("./results/")[1] for f in os.scandir("./results/") if f.is_dir()]

    if domain:
        httpx_json_path = f"results/{domain}/httpx.json"

        if os.path.exists(httpx_json_path):
            with open(httpx_json_path, 'r') as file:
                try:
                    data = json.load(file)
                except Exception as e:
                    return render_template('index.html', data=False, domains=domains)

            return render_template('index.html', data=data, domains=domains)

        else:
            # Handle the case when neither file exists for the specified domain
            return render_template('index.html', data=False, domains=domains)

    else:
        return render_template('index.html', data=False, domains=domains)


@bp.route('/scan/', methods=['POST'])
def scan():
    domain = request.form.get('domain')

    # Define a function to run the scanner process
    def start_scanner():
        try:
            run_scanner(domain)
        except Exception as e:
            return render_template('scan.html', message=f"a scan for: {domain} already exist")

    # Create a new thread to run the scanner process
    scanner_thread = Thread(target=start_scanner)
    scanner_thread.start()

    # Return a response to the client immediately
    return render_template('scan.html', message=f"Scan started for domain: {domain}")