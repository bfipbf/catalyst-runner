#!/usr/bin/env python3
"""Catalyst validation. Intentionally prints no source content, paths, references or errors."""
import json
import pathlib
import subprocess
import sys

def run():
    repo = pathlib.Path(sys.argv[1]).resolve()
    doc = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
    git = lambda *a: subprocess.check_output(["git", "-C", str(repo), *a], text=True).strip()
    actual_head = git("rev-parse", "HEAD")
    branch_head = git("rev-parse", "Branch_Gabungan^{commit}")
    assert actual_head == branch_head == doc["source"]["commit_sha"]
    assert doc["source"]["branch"] == "Branch_Gabungan"
    assert doc["coverage"] == "parsed_repository"
    tree = git("ls-tree", "-r", "--name-only", "HEAD").splitlines()
    xml_paths = [p for p in tree if p.endswith(".xml")]
    flow_paths = [p for p in tree if p.startswith("force-app/main/default/flows/") and p.endswith(".flow-meta.xml")]
    files = doc["files"]
    assert len(tree) == len(files) == doc["statistics"]["files"]
    assert {x["path"] for x in files} == set(tree)
    assert len(xml_paths) == doc["statistics"]["xml_parsed"]
    assert len(flow_paths) == doc["statistics"]["flows_parsed"] == len(doc["flows"])
    assert not doc.get("parse_errors")
    assert doc["statistics"]["errors"] == 0
    assert doc["reverse_index"]
    for name, flow in doc["flows"].items():
        assert flow["path"] in set(flow_paths)
        assert len(flow["blob_sha"]) == 40
        names = [n["name"] for n in flow["nodes"]]
        assert len(names) == len(set(names))
        assert not flow.get("unresolved_connectors")
    print("VALID")

if __name__ == "__main__":
    try:
        run()
    except BaseException:
        print("INVALID", file=sys.stderr)
        sys.exit(1)
