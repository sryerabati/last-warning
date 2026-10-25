"""Archive visible demo history without resetting model billing or job idempotency."""
import argparse
import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KINDS = ("runs", "analyses", "comparisons", "stimuli")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    source = ROOT / "data"
    with sqlite3.connect(source / "last-warning.sqlite3", timeout=30) as db:
        jobs = [json.loads(row[0]) for row in db.execute("SELECT payload FROM records WHERE kind='run_jobs'")]
        if any(job["status"] in {"queued", "running"} for job in jobs):
            raise RuntimeError("Wait for active run jobs before archiving")
        rows = db.execute("SELECT kind,id FROM records WHERE kind IN (?,?,?,?)", KINDS).fetchall()
        counts = {kind: sum(row[0] == kind for row in rows) for kind in KINDS}
        if not args.apply or not rows:
            print(json.dumps({"apply": args.apply, "counts": counts}))
            return
        archive = source / "archives" / (datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ") + "-before-video-demo")
        archive.mkdir(parents=True)
        with sqlite3.connect(archive / "history.sqlite3") as backup:
            db.backup(backup)
            assert backup.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        for folder in ("recordings", "neural", "stimuli"):
            shutil.copytree(source / folder, archive / folder)
        manifest = {"created_at": datetime.now(UTC).isoformat(), "counts": counts,
                    "records": rows, "preserved": ["warnings", "scenarios", "settings", "run_jobs", "run_job_keys", "data/agents"]}
        (archive / "manifest.json").write_text(json.dumps(manifest, indent=2))
        (archive / "RESTORE.md").write_text(
            "# Recover archived history\n\nThe SQLite backup and recording/neural/stimulus files are complete. "
            "To restore, copy missing artifact files into their matching data folders, attach history.sqlite3, "
            "and INSERT OR IGNORE the records whose kind is runs, analyses, comparisons, or stimuli. "
            "Do not replace the live database or the data/agents billing ledger. "
            "Warnings, scenarios, job idempotency, and spending records were retained.\n"
        )
        db.execute("BEGIN IMMEDIATE")
        active = [json.loads(row[0]) for row in db.execute("SELECT payload FROM records WHERE kind='run_jobs'")]
        if any(job["status"] in {"queued", "running"} for job in active):
            raise RuntimeError("A job started while archiving; no visible records were removed")
        db.executemany("DELETE FROM records WHERE kind=? AND id=?", rows)
        db.commit()
    print(json.dumps({"archive": str(archive), "cleared": counts, "billing_and_job_keys_preserved": True}))


if __name__ == "__main__":
    main()
