#!/usr/bin/env python3
"""Feed demo-data/ into a running backend.

    python3 demo-data/seed.py                          # http://localhost:8000
    python3 demo-data/seed.py --api http://host:8000 --factory demo-factory
    python3 demo-data/seed.py --reindex                # also ingest docs into the RAG index

Safe to re-run: assets match on external_id, readings and maintenance records
carry external_ids the backend de-duplicates on, and the business context is a
full replace by design. Documents are the one exception — uploading twice
creates two copies.
"""
from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).parent

# document -> (kind, asset external_id or None for factory-wide)
DOCUMENTS = {
    "sop-pm-001-penggantian-bearing-pompa.pdf": ("sop", "PUMP-01"),
    "sop-pm-002-pemeliharaan-kompresor-sekrup.pdf": ("sop", "COMP-01"),
    "sop-ik-cnc-003-perawatan-harian-cnc-milling.pdf": ("sop", "CNC-MILL-01"),
    "sop-lockout-tagout-osha-3120.pdf": ("sop", None),
    "manual-pump-grundfos-nk-nkg.pdf": ("manual", "PUMP-01"),
    "manual-pump-life-cycle-costs-doe.pdf": ("manual", None),
    "manual-screw-air-compressor-oppair.pdf": ("manual", "COMP-01"),
    "manual-bridgeport-series-i-milling-machine.pdf": ("manual", "CNC-MILL-01"),
    "manual-motor-abb-low-voltage.pdf": ("manual", "MOTOR-01"),
    "manual-bearing-handbook-electric-motors-skf.pdf": ("manual", "MOTOR-01"),
    "manual-bearing-installation-maintenance-skf.pdf": ("manual", None),
}


class Client:
    def __init__(self, api: str, factory: str):
        self.api = api.rstrip("/")
        self.headers = {"X-Factory-Id": factory, "X-Demo-User": "demo-engineer"}

    def request(self, method: str, path: str, body: bytes | None = None, content_type: str | None = None):
        request = urllib.request.Request(f"{self.api}{path}", data=body, method=method, headers=self.headers)
        if content_type:
            request.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.loads(response.read() or b"null")
        except urllib.error.HTTPError as error:
            raise SystemExit(f"{method} {path} -> {error.code} {error.read().decode()[:400]}")

    def json(self, method: str, path: str, payload):
        return self.request(method, path, json.dumps(payload).encode(), "application/json")

    def upload(self, path: str, file: Path):
        boundary = uuid.uuid4().hex
        mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        body = b"".join([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{file.name}"\r\n'.encode(),
            f"Content-Type: {mime}\r\n\r\n".encode(),
            file.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        ])
        return self.request("POST", path, body, f"multipart/form-data; boundary={boundary}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--factory", default="demo-factory")
    parser.add_argument("--reindex", action="store_true", help="ingest uploaded documents into the AI knowledge base")
    args = parser.parse_args()
    client = Client(args.api, args.factory)

    # 1. machines
    ids = {a["external_id"]: a["id"] for a in client.request("GET", "/api/v1/assets") if a.get("external_id")}
    for row in csv.DictReader((HERE / "assets.csv").open(encoding="utf-8")):
        if row["external_id"] in ids:
            print(f"asset {row['external_id']}: exists")
            continue
        created = client.json("POST", "/api/v1/assets", {
            "name": row["name"], "asset_type": row["asset_type"],
            "criticality": row["criticality"], "location": row["location"],
            "specs_json": json.loads(row["specs_json"]), "external_id": row["external_id"],
        })
        ids[row["external_id"]] = created["id"]
        print(f"asset {row['external_id']}: created")

    # 2. sensor readings (PLC export), then the anomaly baseline fitted on them
    for file in sorted((HERE / "readings").glob("*.csv")):
        asset_id = ids.get(file.stem)
        if not asset_id:
            print(f"readings {file.stem}: no such asset, skipped")
            continue
        result = client.upload(f"/api/v1/assets/{asset_id}/readings/import", file)
        line = f"readings {file.stem}: {result['count']} imported, {len(result['errors'])} errors"
        try:
            fitted = client.request("POST", f"/api/v1/assets/{asset_id}/baseline")
            line += f", baseline fitted on {len(fitted['tags'])} tags"
        except SystemExit as error:
            # No ai-engine on this deployment: the analyzer falls back to the
            # per-batch IQR fence, which these readings also trip.
            line += f", baseline skipped ({str(error).split(' -> ')[-1][:60]})"
        print(line)

    # 3. maintenance history
    result = client.upload("/api/v1/maintenance-records/import", HERE / "maintenance-history.csv")
    print(f"maintenance history: {result['imported']} imported, {len(result['errors'])} errors")

    # 4. business context: shifts, roster and warehouse are factory-wide (full
    #    replace); the operator report is per machine.
    context = json.loads((HERE / "business-context.json").read_text(encoding="utf-8"))
    reports = context.pop("operator_reports", {})
    context["inventory"] = [
        {**{key: value for key, value in part.items() if key != "asset_external_ids"},
         "asset_ids": [ids[external_id] for external_id in part["asset_external_ids"]]}
        for part in context["inventory"]
    ]
    client.json("PUT", "/api/v1/business-context", context)
    print(f"business context: {len(context['inventory'])} parts, {len(context['technicians'])} technicians")
    for external_id, report in reports.items():
        client.json("PUT", f"/api/v1/assets/{ids[external_id]}/condition", {"condition": report})
        print(f"operator report {external_id}: set")

    # 5. SOPs and manuals
    for name, (kind, external_id) in DOCUMENTS.items():
        query = f"?kind={kind}" + (f"&asset_id={ids[external_id]}" if external_id else "")
        document = client.upload(f"/api/v1/knowledge/documents{query}", HERE / "docs" / name)
        note = ""
        if args.reindex:
            indexed = client.request("POST", f"/api/v1/knowledge/documents/{document['id']}/reindex")
            error = indexed.get("ingestion_error")
            note = f", index {indexed['ingestion_status']}" + (f": {error[:80]}" if error else "")
        print(f"document {name}: {document['size_bytes']} bytes, kind={document['kind']}{note}")


if __name__ == "__main__":
    main()
