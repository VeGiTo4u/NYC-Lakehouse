#!/usr/bin/env python3
"""
Sync KPI Parquet exports from S3 latest/ into dashboard/data/.

Phase 2 pipeline step — reads the atomic-write latest/ prefix produced by
export_kpi_parquet.py, consolidates Spark parquet directories into single
local files, validates schema/grain, and writes a sync manifest.

Usage:
    python scripts/export/sync_kpi_from_s3.py

Environment:
    S3_KPI_EXPORT_PREFIX  Optional. Defaults to s3://nyc-lakehouse-store/exports/kpi/latest/
    AWS_ACCESS_KEY_ID     Required for S3 access (also AWS_SECRET_ACCESS_KEY, AWS region)
    KPI_DATA_DIR          Optional. Defaults to dashboard/data/
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

import boto3
import pyarrow.parquet as pq

from export_constants import EXPORT_FILES, EXPORT_VALIDATION, MAX_EXPORT_BYTES

DEFAULT_S3_PREFIX = "s3://nyc-lakehouse-store/exports/kpi/latest/"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"CONFIGURATION ERROR: Invalid S3 URI '{uri}'")
    prefix = parsed.path.lstrip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return parsed.netloc, prefix


def _download_s3_prefix(s3_client, bucket: str, prefix: str, local_dir: Path) -> None:
    """Downloads all objects under an S3 prefix into a local directory."""
    local_dir.mkdir(parents=True, exist_ok=True)
    paginator = s3_client.get_paginator("list_objects_v2")

    found = False
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue
            found = True
            relative = key[len(prefix) :].lstrip("/")
            target = local_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            s3_client.download_file(bucket, key, str(target))

    if not found:
        raise FileNotFoundError(f"FAILED: No objects found at s3://{bucket}/{prefix}")


def _consolidate_parquet(source_dir: Path, target_file: Path) -> int:
    """Reads a Spark parquet directory and writes a single consolidated file."""
    table = pq.read_table(source_dir)
    row_count = table.num_rows
    target_file.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, target_file, compression="snappy")
    return row_count


def _validate_local_export(export_filename: str, target_file: Path, row_count: int) -> None:
    """Validates row count, schema, grain keys, and file size."""
    validation_cfg = EXPORT_VALIDATION[export_filename]
    grain_keys: List[str] = validation_cfg["grain_keys"]  # type: ignore[assignment]
    required_columns: List[str] = validation_cfg["required_columns"]  # type: ignore[assignment]

    if row_count <= 0:
        raise ValueError(f"[FAIL] {export_filename}: row count must be > 0")

    size_bytes = target_file.stat().st_size
    if size_bytes >= MAX_EXPORT_BYTES:
        size_mb = size_bytes / (1024 * 1024)
        raise ValueError(
            f"[FAIL] {export_filename}: size {size_mb:.2f} MB exceeds 10 MB limit"
        )

    table = pq.read_table(target_file)
    columns = set(table.column_names)

    missing = [c for c in required_columns if c not in columns]
    if missing:
        raise ValueError(f"[FAIL] {export_filename}: missing columns {missing}")

    import pyarrow.compute as pc

    for key in grain_keys:
        col = table.column(key)
        null_count = pc.sum(pc.is_null(col)).as_py()
        if null_count and null_count > 0:
            raise ValueError(f"[FAIL] {export_filename}: {key} has {null_count} NULLs")

    print(f"[PASS] {export_filename}: {row_count:,} rows, {size_bytes / (1024 * 1024):.2f} MB")


def sync_kpi_exports(
    s3_prefix: str | None = None,
    local_data_dir: Path | None = None,
) -> Dict[str, object]:
    """
    Downloads all KPI exports from S3 latest/ and writes consolidated parquet locally.

    Returns a manifest dict suitable for dashboard/data/manifest.json.
    """
    s3_prefix = s3_prefix or os.environ.get("S3_KPI_EXPORT_PREFIX", DEFAULT_S3_PREFIX)
    local_data_dir = local_data_dir or Path(
        os.environ.get("KPI_DATA_DIR", str(_repo_root() / "dashboard" / "data"))
    )

    bucket, key_prefix = _parse_s3_uri(s3_prefix)
    s3_client = boto3.client("s3")

    print("[INFO] KPI sync configuration:")
    print(f"  S3 source     : s3://{bucket}/{key_prefix}")
    print(f"  Local target  : {local_data_dir}")

    export_stats: Dict[str, Dict[str, object]] = {}

    with tempfile.TemporaryDirectory(prefix="kpi_sync_") as tmp_root:
        tmp_base = Path(tmp_root)

        for export_filename in EXPORT_FILES:
            s3_export_prefix = f"{key_prefix}{export_filename}/"
            tmp_download = tmp_base / export_filename
            local_target = local_data_dir / export_filename

            print(f"[INFO] Downloading s3://{bucket}/{s3_export_prefix}")
            _download_s3_prefix(s3_client, bucket, s3_export_prefix, tmp_download)

            print(f"[INFO] Consolidating {export_filename}")
            row_count = _consolidate_parquet(tmp_download, local_target)
            _validate_local_export(export_filename, local_target, row_count)

            export_stats[export_filename] = {
                "rows": row_count,
                "bytes": local_target.stat().st_size,
                "local_path": str(local_target.relative_to(_repo_root())),
            }
            print(f"[SUCCESS] Synced {export_filename}")

    synced_at = datetime.now(timezone.utc).isoformat()
    manifest: Dict[str, object] = {
        "synced_at": synced_at,
        "s3_source": f"s3://{bucket}/{key_prefix}",
        "exports": export_stats,
    }

    manifest_path = local_data_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[SUCCESS] Wrote manifest: {manifest_path}")

    return manifest


def main() -> int:
    try:
        manifest = sync_kpi_exports()
        total_rows = sum(
            stats["rows"] for stats in manifest["exports"].values()  # type: ignore[union-attr]
        )
        print("\n" + "=" * 70)
        print("KPI S3 → DASHBOARD SYNC SUMMARY")
        print("=" * 70)
        print(f"Synced at   : {manifest['synced_at']}")
        print(f"S3 source   : {manifest['s3_source']}")
        print(f"Total rows  : {total_rows:,}")
        print(f"Export count: {len(EXPORT_FILES)}")
        print("=" * 70)
        print("[END] KPI sync completed successfully")
        print("=" * 70)
        return 0
    except Exception as exc:
        print(f"[FAIL] KPI sync failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
