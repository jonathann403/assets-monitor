import subdomains_scanner.SubdomainScanner

def main():
    scanner = subdomains_scanner.SubdomainScanner("example.com", wordlist="wordlist.txt", output_file="../results/")
    subdomains = scanner.start_subdomain_scan()
    print(subdomains)

if __name__ == "__main__":
    main()
