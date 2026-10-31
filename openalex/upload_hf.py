#!/usr/bin/env python3
"""Publish a staged dataset folder to the Hugging Face Hub. Does nothing without --confirm.

Requires the HF_TOKEN environment variable and the huggingface_hub package
(pip install huggingface_hub). The repository is created private unless --public is given,
so the first publish can be reviewed before anyone else can see it.

Usage:
  python openalex/upload_hf.py --folder <staging dir> --repo-id <owner/name>            # dry run
  python openalex/upload_hf.py --folder <staging dir> --repo-id <owner/name> --confirm  # upload
  add --public only after the private upload has been reviewed
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Upload a staged dataset folder to HF.")
    parser.add_argument("--folder", required=True, type=Path)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--public", action="store_true", help="create the repo public")
    parser.add_argument("--confirm", action="store_true", help="actually upload")
    args = parser.parse_args(argv)

    folder = args.folder.resolve()
    if not (folder / "README.md").is_file() or not (folder / "SHA256SUMS").is_file():
        print("not a staged dataset folder (missing README.md or SHA256SUMS)", file=sys.stderr)
        return 2
    files = [p for p in folder.rglob("*") if p.is_file()]
    size = sum(p.stat().st_size for p in files)
    visibility = "public" if args.public else "private"
    print(f"plan: {len(files)} files, {size:,} bytes -> {args.repo_id} ({visibility} dataset)")
    if not args.confirm:
        print("dry run: nothing uploaded. Re-run with --confirm to upload.")
        return 0

    token = os.environ.get("HF_TOKEN")
    if not token:
        print("HF_TOKEN is not set; nothing uploaded.", file=sys.stderr)
        return 2
    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("huggingface_hub is not installed (pip install huggingface_hub).", file=sys.stderr)
        return 2

    api = HfApi(token=token)
    api.create_repo(repo_id=args.repo_id, repo_type="dataset",
                    private=not args.public, exist_ok=True)
    if hasattr(api, "upload_large_folder"):
        api.upload_large_folder(repo_id=args.repo_id, repo_type="dataset", folder_path=str(folder))
    else:
        # Older and newer huggingface_hub releases differ; upload_folder works on both.
        api.upload_folder(repo_id=args.repo_id, repo_type="dataset", folder_path=str(folder),
                          commit_message="Upload OpenAlex BibTeX 1M proof of concept (private)")
    print(f"uploaded to {args.repo_id} ({visibility})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
