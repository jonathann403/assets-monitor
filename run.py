from app import create_app
from src.subdomains_scanner import SubdomainScanner
from multiprocessing import Process, set_start_method

domain = ""

def run_scanner():
    try:
        scanner = SubdomainScanner(domain, "./wordlists/subdomains/httparchive_subdomains_2024_04_28.txt")
        scanner.start_subdomain_scan()

    except Exception as e:
        print(e)


def run_flask_app():
    app = create_app()
    app.run(debug=True)


def main():
    try:
        set_start_method('fork')
    except RuntimeError:
        pass  # 'fork' method is not available

    scanner_process = Process(target=run_scanner)
    flask_app_process = Process(target=run_flask_app)

    flask_app_process.start()
    scanner_process.start()

    scanner_process.join()
    flask_app_process.join()


if __name__ == '__main__':
    main()
