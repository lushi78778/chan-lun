# -*- coding: utf-8 -*-
"""发布版本与已验收产物清单；不构建、不联网、不发布，兼容 Python 3.6。

seal 冻结 wheel/sdist 的版本、提交和 SHA-256；verify 拒绝版本错配、
新增/缺失产物、内容篡改或 validation 误入发行包。历史清单禁止覆盖。
"""
import argparse
import ast
from email.parser import Parser
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import tarfile
import zipfile
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "release-manifest.json"


def source_version(root):
    root = Path(root)
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    project = text.split("[project]\n", 1)[1].split("\n[", 1)[0]
    match = re.search(r'^version\s*=\s*"([^"]+)"', project, re.M)
    if not match:
        raise ValueError("pyproject 缺少版本")
    version = match.group(1)
    tree = ast.parse((root / "src/chan/__init__.py").read_text(encoding="utf-8"))
    actual = [ast.literal_eval(n.value) for n in tree.body
              if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and
              t.id == "__version__" for t in n.targets)]
    if actual != [version]:
        raise ValueError("源码与 pyproject 版本不一致")
    return version


def check_tag(version, tag):
    if tag is not None and tag != "v" + version:
        raise ValueError("标签 {} 与包版本 {} 不一致".format(tag, version))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect_artifact(path, version):
    path = Path(path)
    if path.name.endswith(".whl"):
        with zipfile.ZipFile(str(path)) as archive:
            names = archive.namelist()
            metadata = [n for n in names if n.endswith(".dist-info/METADATA")]
            if len(metadata) != 1:
                raise ValueError("wheel 元数据不唯一")
            text = archive.read(metadata[0]).decode("utf-8")
            relative = names
    elif path.name.endswith(".tar.gz"):
        with tarfile.open(str(path)) as archive:
            names = archive.getnames()
            metadata = [n for n in names if n.count("/") == 1 and n.endswith("/PKG-INFO")]
            if len(metadata) != 1:
                raise ValueError("sdist 元数据不唯一")
            text = archive.extractfile(metadata[0]).read().decode("utf-8")
            relative = [n.split("/", 1)[1] for n in names if "/" in n]
        required = {"AGENTS.md", "CONTRIBUTING.md", "README.md",
                    "docs/README.md", "docs/api.md", "docs/architecture.md",
                    "docs/migration.md", "docs/usage.md", "docs/installation.md",
                    "tools/check_core.py", "tools/release_artifacts.py"}
        if not required.issubset(set(relative)):
            raise ValueError("sdist 缺少包验收或协作文件")
    else:
        raise ValueError("未知产物格式")
    if any("validation" in n.split("/") for n in relative):
        raise ValueError("validation 不得进入发行包")
    metadata = Parser().parsestr(text)
    name = re.sub(r"[-_.]+", "-", metadata.get("Name", "")).lower()
    if name != "chan-lun-core" or metadata.get("Version") != version:
        raise ValueError("产物元数据版本/名称不一致: {}".format(path.name))
    return metadata


def check_descriptions(root, dist):
    """现代构建环境真实渲染两种产物描述；缺少渲染器不能算通过。"""
    from readme_renderer.markdown import render

    class Links(HTMLParser):
        def __init__(self):
            HTMLParser.__init__(self)
            self.hrefs = []
            self.ids = set()

        def handle_starttag(self, tag, attrs):
            self.ids.update(value for key, value in attrs if key == "id")
            if tag == "a":
                self.hrefs.extend(value for key, value in attrs if key == "href")

    version = source_version(root)
    for path in artifacts(dist):
        metadata = inspect_artifact(path, version)
        if metadata.get("Description-Content-Type") != "text/markdown":
            raise ValueError("产物描述须声明 text/markdown")
        html = render(metadata.get_payload())
        if not html:
            raise ValueError("Markdown 未实际渲染；检查 readme-renderer[md]")
        links = Links()
        links.feed(html)
        if not links.hrefs:
            raise ValueError("产物描述缺少导航链接")
        for href in links.hrefs:
            url = urlsplit(href)
            if url.fragment and not (url.scheme or url.netloc or url.path or url.query):
                if unquote(url.fragment) not in links.ids:
                    raise ValueError("产物描述页内锚点不存在")
            elif url.scheme != "https" or not url.netloc:
                raise ValueError("产物描述链接须使用 HTTPS 绝对地址或有效页内锚点")
    return version


def artifacts(dist):
    dist = Path(dist)
    wheels = sorted(dist.glob("*.whl"))
    sources = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError("须且仅须一份 wheel 与一份 sdist")
    return wheels + sources


def seal(root, dist, commit=None, tag=None):
    version = source_version(root)
    check_tag(version, tag)
    paths = artifacts(dist)
    for path in paths:
        inspect_artifact(path, version)
    record = {"schema": "chan-release-artifacts-v1", "name": "chan-lun-core",
              "version": version, "commit": commit, "tag": tag,
              "files": [{"name": p.name, "sha256": digest(p), "bytes": p.stat().st_size}
                        for p in paths]}
    with (Path(dist) / MANIFEST).open("x", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return record


def verify(root, dist, commit=None, tag=None):
    version = source_version(root)
    check_tag(version, tag)
    record = json.loads((Path(dist) / MANIFEST).read_text(encoding="utf-8"))
    if record.get("schema") != "chan-release-artifacts-v1" or record.get("name") != "chan-lun-core":
        raise ValueError("产物清单格式无效")
    if record.get("version") != version or record.get("tag") != tag:
        raise ValueError("产物清单版本/标签不一致")
    if commit is not None and record.get("commit") != commit:
        raise ValueError("产物清单提交不一致")
    paths = artifacts(dist)
    entries = record.get("files", [])
    if len(entries) != 2 or sorted(p.name for p in paths) != sorted(x["name"] for x in entries):
        raise ValueError("产物集合与清单不一致")
    entries = {x["name"]: x for x in entries}
    for path in paths:
        inspect_artifact(path, version)
        entry = entries[path.name]
        if path.stat().st_size != entry["bytes"] or digest(path) != entry["sha256"]:
            raise ValueError("产物摘要不一致: {}".format(path.name))
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check-source", "check-description", "seal", "verify"))
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--dist", default=str(ROOT / "dist"))
    parser.add_argument("--commit")
    parser.add_argument("--tag")
    args = parser.parse_args(argv)
    args.tag = args.tag or None
    try:
        if args.command == "check-source":
            version = source_version(args.root)
            check_tag(version, args.tag)
            print("source version OK:", version)
        elif args.command == "check-description":
            print("description OK:", check_descriptions(args.root, args.dist))
        else:
            action = seal if args.command == "seal" else verify
            record = action(args.root, args.dist, args.commit, args.tag)
            print("{} OK: {}".format(args.command, record["version"]))
    except Exception as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
