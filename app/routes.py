from flask import Blueprint, render_template, request
import threading
import json
import os

from src.subdomains_scanner import SubdomainScanner
from src.httpx_scanner import HttpxScanner

bp = Blueprint('main', __name__)

running_scans = []

def run_scanner(domain):
    try:
        subdomain_scanner = SubdomainScanner(domain, "./wordlists/subdomains/httparchive_subdomains_2024_04_28.txt")
        subdomain_scanner.start()

        httpx_scanner = HttpxScanner(subdomain_scanner.output_file, domain)
        httpx_scanner.start()
    except Exception as e:
        raise Exception("scan canceled")

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
                    return render_template('index.html', data=False, domains=domains, running_scans=running_scans)

            return render_template('index.html', data=data, domains=domains, running_scans=running_scans)
        return render_template('index.html', data=False, domains=domains, running_scans=running_scans)

    else:
        return render_template('index.html', data=False, domains=domains, running_scans=running_scans)


@bp.route('/scan/', methods=['POST'])
def scan():
    domain = request.form.get('domain')
    domains = [f.path.split("./results/")[1] for f in os.scandir("./results/") if f.is_dir()]

    # Check if a scan is already running for the domain
    if domain in running_scans and domain in domains or domain in domains:
        return render_template('scan.html', message=f"Scan for domain {domain} already exists")

    def start_scanner():
        running_scans.append(domain)
        run_scanner(domain)
        running_scans.remove(domain)

    # Create a new thread to run the scanner process
    scanner_thread = threading.Thread(target=start_scanner)
    scanner_thread.start()

    # Return a response to the client immediately
    return render_template('scan.html', message=f"Scan started for domain: {domain}")