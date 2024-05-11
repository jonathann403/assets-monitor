import os
from app import create_app
from src.subdomains_scanner import SubdomainScanner
from multiprocessing import Process, Pipe, set_start_method

domain = "ynet.co.il"

def run_scanner(pipe_handle):
    try:
        scanner = SubdomainScanner(domain, "wordlists/subdomains/httparchive_subdomains_2024_04_28.txt")
        scanner.start_subdomain_scan()
    except Exception as e:
        print(e)
    finally:
        pipe_handle.close()  # Close the pipe handle after finishing

def run_flask_app():
    app = create_app()
    app.run(debug=True)

if __name__ == '__main__':

    parent_conn, child_conn = Pipe()

    scanner_process = Process(target=run_scanner, args=(child_conn,))
    flask_app_process = Process(target=run_flask_app)

    scanner_process.start()
    flask_app_process.start()

    scanner_process.join()
    flask_app_process.join()

    # Close the parent connection after both processes are done
    parent_conn.close()
