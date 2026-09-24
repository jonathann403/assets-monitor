"""Persistence and reads for scan results.

Every scanned domain gets a directory under ``RESULTS_DIR`` containing:

* ``subdomains.txt`` - the enumerated subdomains (one per line)
* ``httpx.jsonl``    - raw httpx output
* ``httpx.json``     - httpx results as a JSON array (what the UI reads)
* ``meta.json``      - scan metadata (status, timestamps, counts)

The store is the single place that touches the results directory, and it
re-validates every domain it is given so a crafted value can never escape it.
"""
import json
import os
from datetime import datetime, timezone

from .validators import ValidationError, normalize_domain


def _iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class Store:
    def __init__(self, results_dir):
        self.results_dir = os.path.abspath(results_dir)

    # -- paths -------------------------------------------------------------
    def _domain_dir(self, domain):
        """Return the absolute results directory for ``domain``.

        Validates the domain and confirms the resolved path stays inside
        ``results_dir`` (defence in depth against traversal).
        """
        domain = normalize_domain(domain)
        path = os.path.abspath(os.path.join(self.results_dir, domain))
        root = self.results_dir + os.sep
        if path != self.results_dir and not path.startswith(root):
            raise ValidationError("Invalid domain path.")
        return path

    def ensure_root(self):
        os.makedirs(self.results_dir, exist_ok=True)

    # -- listing -----------------------------------------------------------
    def list_domains(self):
        if not os.path.isdir(self.results_dir):
            return []
        domains = []
        for entry in os.scandir(self.results_dir):
            if entry.is_dir() and is_valid_dirname(entry.name):
                domains.append(entry.name)
        return sorted(domains)

    def domain_exists(self, domain):
        try:
            return os.path.isdir(self._domain_dir(domain))
        except ValidationError:
            return False

    # -- reads -------------------------------------------------------------
    def load_results(self, domain):
        """Return httpx results as a list of dicts.

        Prefers ``httpx.json`` (a JSON array). Falls back to ``httpx.jsonl``
        and to legacy files that may be JSON-lines stored under a ``.json``
        name, so results written by older versions still load.
        """
        domain_dir = self._domain_dir(domain)
        json_path = os.path.join(domain_dir, "httpx.json")
        jsonl_path = os.path.join(domain_dir, "httpx.jsonl")

        if os.path.exists(json_path):
            results = _load_json_or_jsonl(json_path)
            if results is not None:
                return results
        if os.path.exists(jsonl_path):
            results = _load_json_or_jsonl(jsonl_path)
            if results is not None:
                return results
        return []

    def load_subdomains(self, domain):
        domain_dir = self._domain_dir(domain)
        path = os.path.join(domain_dir, "subdomains.txt")
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return [line.strip() for line in fh if line.strip()]

    def load_meta(self, domain):
        """Return scan metadata, synthesizing sensible defaults if absent."""
        domain_dir = self._domain_dir(domain)
        meta_path = os.path.join(domain_dir, "meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as fh:
                    meta = json.load(fh)
                meta.setdefault("domain", domain)
                return meta
            except (json.JSONDecodeError, OSError):
                pass

        # Synthesize metadata for a directory that has results but no meta
        # (e.g. the bundled example, or results from an older version).
        httpx_path = os.path.join(domain_dir, "httpx.json")
        when = _iso(os.path.getmtime(httpx_path)) if os.path.exists(httpx_path) else None
        return {
            "domain": domain,
            "status": "completed",
            "message": "Imported results",
            "created_at": when,
            "started_at": None,
            "finished_at": when,
            "duration_seconds": None,
            "subdomains_found": len(self.load_subdomains(domain)),
            "hosts_live": len(self.load_results(domain)),
            "error": None,
            "synthesized": True,
        }

    # -- writes ------------------------------------------------------------
    def save_meta(self, domain, meta):
        domain_dir = self._domain_dir(domain)
        os.makedirs(domain_dir, exist_ok=True)
        meta_path = os.path.join(domain_dir, "meta.json")
        tmp = meta_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)
        os.replace(tmp, meta_path)

    def delete_domain(self, domain):
        """Remove a domain's results directory. Returns True if it existed."""
        import shutil

        domain_dir = self._domain_dir(domain)
        if os.path.isdir(domain_dir):
            shutil.rmtree(domain_dir)
            return True
        return False

    # -- aggregation -------------------------------------------------------
    def summary(self, results):
        return summarize(results)


def is_valid_dirname(name):
    try:
        normalize_domain(name)
        return True
    except ValidationError:
        return False


def _load_json_or_jsonl(path):
    """Load a file that is either a JSON array or JSON-lines. None on failure."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return None

    text = text.strip()
    if not text:
        return []

    # Try a single JSON document first (array or object).
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
    except json.JSONDecodeError:
        pass

    # Fall back to JSON-lines.
    results = []
    for line in text.splitlines():
        line = line.strip().rstrip(",")
        if not line or line in ("[", "]"):
            continue
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return results or None


def summarize(results):
    """Compute dashboard statistics from a list of httpx result dicts."""
    total = len(results)
    status_classes = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "other": 0}
    tech_counts = {}
    server_counts = {}
    cdn_count = 0

    for item in results:
        if not isinstance(item, dict):
            continue
        code = item.get("status_code")
        bucket = _status_bucket(code)
        status_classes[bucket] += 1

        for tech in item.get("tech", []) or []:
            tech_counts[tech] = tech_counts.get(tech, 0) + 1

        server = item.get("webserver")
        if server:
            server_counts[server] = server_counts.get(server, 0) + 1

        if item.get("cdn"):
            cdn_count += 1

    top_tech = [
        {"name": name, "count": count}
        for name, count in sorted(
            tech_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )
    ]
    top_servers = [
        {"name": name, "count": count}
        for name, count in sorted(
            server_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )
    ]

    live = status_classes["2xx"] + status_classes["3xx"] + status_classes["4xx"] + status_classes["5xx"]
    return {
        "total": total,
        "live": live,
        "status_classes": status_classes,
        "technologies": top_tech,
        "unique_technologies": len(tech_counts),
        "servers": top_servers,
        "cdn_count": cdn_count,
    }


def _status_bucket(code):
    try:
        code = int(code)
    except (TypeError, ValueError):
        return "other"
    if 200 <= code < 300:
        return "2xx"
    if 300 <= code < 400:
        return "3xx"
    if 400 <= code < 500:
        return "4xx"
    if 500 <= code < 600:
        return "5xx"
    return "other"
