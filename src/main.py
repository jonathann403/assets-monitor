import subdomains_scanner.SubdomainScanner

def main():
    scanner = subdomains_scanner.SubdomainScanner("example.com", wordlist="../wordlists/data/automated/httparchive_subdomains_2024_04_28.txt", output_file="../results/")
    subdomains = scanner.start_subdomain_scan()
    print(subdomains)

if __name__ == "__main__":
    main()
