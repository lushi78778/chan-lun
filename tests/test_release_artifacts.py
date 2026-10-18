# -*- coding: utf-8 -*-
"""发布边界回归：错误标签、产物元数据错配和验收后篡改必须被拒绝。"""
import importlib.util
import io
import json
import sys
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock
from types import ModuleType
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_artifacts", str(ROOT / "tools/release_artifacts.py"))
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


def prepare(folder, artifact_version="1.0.0", validation=False, legacy_api=False):
    root = Path(folder)
    (root / "src/chan").mkdir(parents=True)
    (root / "src/chan/__init__.py").write_text('__version__ = "1.0.0"\n')
    (root / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
    dist = root / "dist"
    dist.mkdir()
    metadata = ("Name: chan-lun-core\nVersion: {}\n"
                "Description-Content-Type: text/markdown\n\n"
                "[docs](https://example.com/docs)\n").format(artifact_version)
    wheel = dist / "chan_lun_core-1.0.0-py3-none-any.whl"
    with zipfile.ZipFile(str(wheel), "w") as archive:
        archive.writestr("chan_lun_core-1.0.0.dist-info/METADATA", metadata)
    source = dist / "chan_lun_core-1.0.0.tar.gz"
    with tarfile.open(str(source), "w:gz") as archive:
        members = {"PKG-INFO": metadata, "AGENTS.md": "rules",
                   "docs/README.md": "docs", "docs/architecture.md": "architecture",
                   "docs/migration.md": "migration", "docs/usage.md": "usage",
                   "docs/installation.md": "installation",
                   "CONTRIBUTING.md": "flow", "README.md": "usage",
                   "tools/check_core.py": "# entry", "tools/release_artifacts.py": "# guard"}
        members["API.md" if legacy_api else "docs/api.md"] = "contract"
        if validation:
            members["validation/private.json"] = "{}"
        for name, text in members.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo("chan_lun_core-1.0.0/" + name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return root, dist


class TestReleaseArtifacts(unittest.TestCase):
    def test_unrendered_or_relative_description_cannot_pass(self):
        """渲染不可用和产物中的相对链接都必须明确失败，不能只看元数据。"""
        renderer = ModuleType("readme_renderer.markdown")
        package = ModuleType("readme_renderer")
        package.markdown = renderer
        modules = {"readme_renderer": package, "readme_renderer.markdown": renderer}
        with tempfile.TemporaryDirectory() as folder:
            root, dist = prepare(folder)
            with mock.patch.dict(sys.modules, modules):
                renderer.render = lambda text: None
                with self.assertRaisesRegex(ValueError, "未实际渲染"):
                    TOOL.check_descriptions(root, dist)
                renderer.render = lambda text: '<a href="docs/api.md">API</a>'
                with self.assertRaisesRegex(ValueError, "绝对地址"):
                    TOOL.check_descriptions(root, dist)
                renderer.render = lambda text: '<a href="https://example.com/docs">docs</a>'
                self.assertEqual(TOOL.check_descriptions(root, dist), "1.0.0")
                renderer.render = lambda text: '<h1 id="title">H</h1><a href="#title">H</a>'
                self.assertEqual(TOOL.check_descriptions(root, dist), "1.0.0")
                renderer.render = lambda text: '<a href="#missing">H</a>'
                with self.assertRaisesRegex(ValueError, "页内锚点不存在"):
                    TOOL.check_descriptions(root, dist)

    def test_wrong_tag_rejected_before_sealing(self):
        with tempfile.TemporaryDirectory() as folder:
            root, dist = prepare(folder)
            with self.assertRaisesRegex(ValueError, "标签"):
                TOOL.seal(root, dist, "commit", "v1.0.1")
            self.assertFalse((dist / TOOL.MANIFEST).exists())

    def test_artifact_version_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root, dist = prepare(folder, artifact_version="0.9.0")
            with self.assertRaisesRegex(ValueError, "元数据"):
                TOOL.seal(root, dist)

    def test_sealed_candidate_matches_both_publication_channels(self):
        with tempfile.TemporaryDirectory() as folder:
            root, dist = prepare(folder)
            before = TOOL.seal(root, dist, "commit", "v1.0.0")
            self.assertEqual(TOOL.verify(root, dist, "commit", "v1.0.0"), before)
            with self.assertRaisesRegex(ValueError, "提交"):
                TOOL.verify(root, dist, "different", "v1.0.0")
            with self.assertRaises(FileExistsError):
                TOOL.seal(root, dist, "commit", "v1.0.0")

    def test_modified_candidate_is_not_publishable(self):
        with tempfile.TemporaryDirectory() as folder:
            root, dist = prepare(folder)
            TOOL.seal(root, dist)
            wheel = next(dist.glob("*.whl"))
            with zipfile.ZipFile(str(wheel), "a") as archive:
                archive.writestr("changed.py", "# changed after testing")
            with self.assertRaisesRegex(ValueError, "摘要"):
                TOOL.verify(root, dist)

    def test_validation_data_cannot_leak_into_source_distribution(self):
        with tempfile.TemporaryDirectory() as folder:
            root, dist = prepare(folder, validation=True)
            with self.assertRaisesRegex(ValueError, "validation"):
                TOOL.seal(root, dist)

    def test_legacy_root_api_does_not_replace_canonical_document(self):
        """有旧 API 文件但缺新契约路径时，不能封存为已验收源码包。"""
        with tempfile.TemporaryDirectory() as folder:
            root, dist = prepare(folder, legacy_api=True)
            with self.assertRaisesRegex(ValueError, "sdist 缺少"):
                TOOL.seal(root, dist)
            self.assertFalse((dist / TOOL.MANIFEST).exists())

    def test_extra_wheel_or_missing_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root, dist = prepare(folder)
            next(dist.glob("*.tar.gz")).unlink()
            with self.assertRaisesRegex(ValueError, "一份"):
                TOOL.seal(root, dist)


if __name__ == "__main__":
    unittest.main()
