#!/usr/bin/env python3
"""Customize official TizenTube releases without compiling or signing app code.

Local: python build_funtube.py --input TizenTube.wgt --icon icon.png --tag v2.0.1 --output-dir out
Actions: python build_funtube.py --icon standalone/icon.png --output-dir out [--publish]
Uses only Python's standard library; GitHub mode also uses the preinstalled gh CLI.
"""
import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
import zlib

UPSTREAM = "reisxd/TizenTube"
PACKAGE_ID = "FunTube001"  # Confirmed working on the TV; keep fixed for future updates.
WIDGET_ID = "https://tizentube.app/noadstube"
W = "{http://www.w3.org/ns/widgets}"
T = "{http://tizen.org/ns/widgets}"
ET.register_namespace("", W[1:-1])
ET.register_namespace("tizen", T[1:-1])
MAX_SIZE = 100 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def gh(*args, data=None):
    command = ["gh", *args]
    if data is not None:
        command += ["--input", "-"]
    result = subprocess.run(command, input=json.dumps(data) if data is not None else None,
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def read_png(path):
    raw = path.read_bytes()
    require(raw[:8] == b"\x89PNG\r\n\x1a\n", "Icon must be a PNG.")
    offset, chunks = 8, []
    while offset < len(raw):
        require(offset + 12 <= len(raw), "Truncated PNG chunk.")
        length = struct.unpack(">I", raw[offset:offset + 4])[0]
        end = offset + length + 12
        require(end <= len(raw), "Truncated PNG data.")
        kind = raw[offset + 4:offset + 8]
        payload = raw[offset + 8:end - 4]
        crc = struct.unpack(">I", raw[end - 4:end])[0]
        require(zlib.crc32(kind + payload) & 0xffffffff == crc, "PNG checksum failed.")
        chunks.append((kind, payload))
        offset = end
    require(chunks and chunks[0][0] == b"IHDR" and len(chunks[0][1]) == 13,
            "Missing PNG header.")
    require(struct.unpack(">II", chunks[0][1][:8]) == (512, 512), "Icon must be 512 x 512.")
    require(chunks[-1] == (b"IEND", b"") and any(k == b"IDAT" for k, _ in chunks),
            "PNG image data missing.")
    return raw


def build(source, icon_path, tag, output_dir, source_url=None, expected_digest=None):
    match = re.fullmatch(r"v?(\d+\.\d+\.\d+)", tag)
    require(match, "Expected a stable release tag such as v2.0.1; review new tag formats manually.")
    version = match.group(1)
    source_bytes = source.read_bytes()
    require(len(source_bytes) <= MAX_SIZE, "Unexpectedly large upstream package.")
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    if expected_digest:
        require(expected_digest == "sha256:" + source_hash, "Upstream asset digest mismatch.")
    icon = read_png(icon_path)
    with zipfile.ZipFile(io.BytesIO(source_bytes)) as archive:
        entries = archive.infolist()
        require(len(entries) <= 10000, "Unexpectedly many ZIP entries.")
        require(sum(e.file_size for e in entries) <= 2 * MAX_SIZE, "Unpacked package too large.")
        for entry in entries:
            path = PurePosixPath(entry.filename)
            require(not path.is_absolute() and ".." not in path.parts and "\\" not in entry.filename,
                    "Unsafe archive path.")
            require(not stat.S_ISLNK(entry.external_attr >> 16), "Unexpected archive symlink.")
        require(len({e.filename for e in entries}) == len(entries), "Duplicate ZIP entries.")
        original = {entry.filename: archive.read(entry) for entry in entries}
    require({"config.xml", "icon.png", "index.html", "service/dist/index.js"} <= original.keys(),
            "Upstream package layout changed; manual review needed.")
    original_root = ET.fromstring(original["config.xml"])
    require(original_root.tag == W + "widget", "Unexpected manifest format.")
    require(original_root.attrib.get("version") == version,
            "Release tag and WGT version differ; refusing to invent or change a version.")
    root = copy.deepcopy(original_root)
    app = root.find(T + "application")
    service = root.find(T + "service")
    name = root.find(W + "name")
    require(app is not None and service is not None and name is not None,
            "Upstream app/service manifest changed.")
    old_package = app.attrib["package"]
    require(app.attrib["id"] == old_package + ".TizenTubeStandalone" and
            service.attrib["id"] == old_package + ".StandaloneService",
            "Upstream app/service identity structure changed.")
    root.set("id", WIDGET_ID)
    app.set("package", PACKAGE_ID)
    app.set("id", PACKAGE_ID + ".TizenTubeStandalone")
    service.set("id", PACKAGE_ID + ".StandaloneService")
    name.text = "FunTube"
    icons = root.findall(W + "icon")
    require(icons, "Upstream manifest has no icon.")
    for item in icons:
        root.remove(item)
    icon_index = list(root).index(root.find(W + "content")) + 1
    root.insert(icon_index, ET.Element(W + "icon", {"src": "icon.png"}))
    require(root.find(W + "content").attrib["src"] in original, "Missing frontend entry point.")
    require(service.find(T + "content").attrib["src"] in original, "Missing service entry point.")
    html = original["index.html"].decode("utf-8")
    html, count = re.subn(r"(<h1\b[^>]*>\s*)TizenTube(\s*</h1>)", r"\g<1>FunTube\2", html)
    require(count == 1, "Loading-screen markup changed; manual review needed.")
    replacements = {
        "config.xml": ET.tostring(root, encoding="utf-8", xml_declaration=True),
        "icon.png": icon,
        "index.html": html.encode("utf-8"),
    }
    removed = {n for n in original if re.fullmatch(r"(?:author-signature|signature\d+)\.xml", n)}
    if "icon_16b9.png" in original:
        removed.add("icon_16b9.png")
    for filename, contents in original.items():
        if filename.endswith((".js", ".html", ".json")):
            require(old_package.encode() not in contents,
                    "Hardcoded upstream package ID appeared in code; manual review needed.")
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"FunTube-{version}.wgt"
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as result:
        for entry in entries:
            if entry.filename not in removed:
                result.writestr(entry, replacements.get(entry.filename, original[entry.filename]))
    with zipfile.ZipFile(destination) as result:
        require(result.testzip() is None, "Output ZIP failed verification.")
        require(set(result.namelist()) == original.keys() - removed, "Unexpected output files.")
        for filename in result.namelist():
            require(result.read(filename) == replacements.get(filename, original[filename]),
                    f"Unexpected content change: {filename}")
        scripts = lambda b: re.findall(rb"<script\b[^>]*>(.*?)</script>", b, re.S)
        require(scripts(result.read("index.html")) == scripts(original["index.html"]),
                "Frontend JavaScript changed.")
        require(ET.fromstring(result.read("config.xml")).attrib["version"] == version,
                "Version changed unexpectedly.")
    output_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
    provenance = {
        "upstream_repository": UPSTREAM, "upstream_tag": tag, "upstream_version": version,
        "upstream_release": source_url or f"https://github.com/{UPSTREAM}/releases/tag/{tag}",
        "upstream_wgt_sha256": source_hash, "icon_sha256": hashlib.sha256(icon).hexdigest(),
        "output_sha256": output_hash, "package_id": PACKAGE_ID,
        "recipe_commit": os.environ.get("GITHUB_SHA"), "signed": False,
        "changed_files": sorted(replacements), "removed_files": sorted(removed),
        "verification": "Every retained file outside the listed changes is byte-identical to upstream; frontend scripts unchanged.",
    }
    (output_dir / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    (output_dir / "SHA256SUMS.txt").write_text(f"{output_hash}  {destination.name}\n")
    print(f"Built and verified {destination}; version {version} matches upstream exactly.")
    return destination, provenance


def remote_release(tag):
    endpoint = f"repos/{UPSTREAM}/releases/latest" if tag == "latest" else f"repos/{UPSTREAM}/releases/tags/{tag}"
    return gh("api", endpoint)


def run(args):
    if args.input:
        require(args.tag != "latest" and not args.publish, "Local builds require an explicit tag and cannot publish.")
        build(args.input, args.icon, args.tag, args.output_dir)
        return
    require(args.tag == "latest" or re.fullmatch(r"v?\d+\.\d+\.\d+", args.tag), "Invalid release tag.")
    release = remote_release(args.tag)
    require(not release["draft"] and not release["prerelease"], "Only stable upstream releases are supported.")
    tag = release["tag_name"]
    require(re.fullmatch(r"v?\d+\.\d+\.\d+", tag), "Unrecognized stable release tag.")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    publish_tag = "funtube/" + tag  # Separate Git tag namespace; package version remains 1:1.
    existing = None
    if args.publish:
        require(repository == "giyorah/FunTube", "Publishing is restricted to giyorah/FunTube.")
        pages = gh("api", "--paginate", "--slurp", f"repos/{repository}/releases?per_page=100")
        existing = next((r for page in pages for r in page if r["tag_name"] == publish_tag), None)
        if existing and not existing["draft"]:
            expected_name = f"FunTube-{tag.removeprefix('v')}.wgt"
            require({expected_name, "provenance.json", "SHA256SUMS.txt"} <= {a["name"] for a in existing["assets"]},
                    "Published release is incomplete; inspect it manually.")
            print(f"Already published {publish_tag}; nothing to do.")
            return
    assets = [a for a in release["assets"] if a["name"] == "TizenTube.wgt" and a["state"] == "uploaded"]
    require(len(assets) == 1, "Expected exactly one official TizenTube.wgt asset.")
    asset = assets[0]
    require(0 < asset["size"] <= MAX_SIZE, "Unexpected upstream WGT size.")
    require(asset["browser_download_url"].startswith(f"https://github.com/{UPSTREAM}/releases/download/"),
            "Unexpected upstream asset URL.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Do not send the repository token to the release-asset download host.
    request = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": "FunTube-packager"})
    with urllib.request.urlopen(request, timeout=90) as response:
        contents = response.read(MAX_SIZE + 1)
    require(len(contents) == asset["size"], "Downloaded asset size mismatch.")
    source = args.output_dir.parent / "TizenTube-upstream.wgt"
    source.write_bytes(contents)
    destination, provenance = build(source, args.icon, tag, args.output_dir,
                                    release["html_url"], asset.get("digest"))
    notes = (
        f"# FunTube {provenance['upstream_version']} is ready to install\n\n"
        f"Based on [TizenTube {tag}]({release['html_url']}). The package version matches upstream exactly.\n\n"
        f"Download **{destination.name}**, then use **Custom WGT** in Apps2Samsung to sign and install it "
        "with the same author certificate as your existing FunTube installation. TV installation is manual.\n\n"
        "Changes: custom square icon, one icon declaration, FunTube displayed name, and the existing "
        "FunTube app identity. Original signatures are removed; all other retained files are unchanged.\n\n"
        "Package checks passed. Playback and icon rendering still need verification on your TV.\n\n"
        f"Upstream source and license: https://github.com/{UPSTREAM}/tree/{tag}\n"
        f"Packaging recipe commit: {os.environ.get('GITHUB_SHA', 'local')}\n"
    )
    (args.output_dir / "release-notes.md").write_text(notes)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a") as report:
            report.write(notes + ("\nPublishing enabled.\n" if args.publish else "\nPreview only: no GitHub Release published.\n"))
    if not args.publish:
        print("Preview complete; no remote writes performed.")
        return
    # Upload all files to a draft before publishing, so the notification points to a complete package.
    if existing:
        require(f"https://github.com/{UPSTREAM}/releases/tag/{tag}" in (existing.get("body") or ""),
                "Existing draft does not look like our release; inspect manually.")
        draft = existing
    else:
        draft = gh("api", "--method", "POST", f"repos/{repository}/releases", data={
            "tag_name": publish_tag, "target_commitish": os.environ["GITHUB_SHA"],
            "name": f"FunTube {provenance['upstream_version']}", "body": notes,
            "draft": True, "prerelease": False,
        })
    subprocess.run(["gh", "release", "upload", publish_tag, str(destination),
                    str(args.output_dir / "provenance.json"), str(args.output_dir / "SHA256SUMS.txt"),
                    "--repo", repository, "--clobber"], check=True)
    gh("api", "--method", "PATCH", f"repos/{repository}/releases/{draft['id']}",
       data={"body": notes, "draft": False, "make_latest": "true"})
    print(f"Published https://github.com/{repository}/releases/tag/{publish_tag}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Local upstream WGT; no GitHub calls or publishing")
    parser.add_argument("--icon", type=Path, default=Path("standalone/icon.png"))
    parser.add_argument("--tag", default="latest")
    parser.add_argument("--output-dir", type=Path, default=Path("out"))
    parser.add_argument("--publish", action="store_true")
    run(parser.parse_args())
