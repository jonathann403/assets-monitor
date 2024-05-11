from app import create_app
from src.subdomains_scanner import SubdomainScanner
from multiprocessing import Process, Queue, set_start_method

domain = "ynet.co.il"

def run_scanner(queue):
    try:
        scanner = SubdomainScanner(domain, "wordlists/subdomains/httparchive_subdomains_2024_04_28.txt")
        scanner.start_subdomain_scan()
    except Exception as e:
        queue.put(e)  # Put exception in the queue for main process to handle

def run_flask_app():
    app = create_app()
    app.run(debug=True)

if __name__ == '__main__':
    try:
        set_start_method('fork')
    except RuntimeError:
        pass  # 'fork' method is not available

    # Create a queue for communication between processes
    queue = Queue()

    # Start the scanner process
    scanner_process = Process(target=run_scanner, args=(queue,))
    scanner_process.start()

    # Wait for the scanner process to finish or throw an exception
    scanner_process.join()

    # Check if an exception occurred in the scanner process
    if not queue.empty():
        print("Scanner process encountered an exception:", queue.get())
    else:
        # If no exception, start the Flask app process
        flask_app_process = Process(target=run_flask_app)
        flask_app_process.start()
        flask_app_process.join()
