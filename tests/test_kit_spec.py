"""Smoke-tests for the kit's spec.yaml and its referenced files.

Run from the repo root:
    python3 -m unittest discover -s .
"""

import os
import stat
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
KIT_DIR = REPO_ROOT / "sbx-kits" / "claude-custom"
SPEC_FILE = KIT_DIR / "spec.yaml"
FILES_HOME = KIT_DIR / "files" / "home" / ".claude"


def load_spec() -> dict:
    with SPEC_FILE.open() as f:
        return yaml.safe_load(f)


class TestSpecYamlName(unittest.TestCase):
    def test_name_matches_directory(self):
        spec = load_spec()
        self.assertEqual(spec["name"], KIT_DIR.name)


class TestSetupCommandFiles(unittest.TestCase):
    """Every file path referenced by a setup command must exist on disk."""

    def _paths_in_command(self, command_str: str) -> list[Path]:
        """Return kit file paths that must pre-exist (source args, not mv destinations)."""
        paths = []
        for line in command_str.splitlines():
            tokens = line.split()
            is_mv = tokens and tokens[0] in ("mv", "mv -f", "cp", "cp -f")
            for i, token in enumerate(tokens):
                # For mv/cp, skip the last token (destination) — it need not pre-exist.
                if is_mv and i == len(tokens) - 1:
                    continue
                for prefix in ("/home/agent/.claude/", "${HOME}/"):
                    if token.startswith(prefix):
                        rel = token[len(prefix) :]
                        paths.append(FILES_HOME / rel)
        return paths

    def _all_setup_commands(self) -> list[str]:
        spec = load_spec()
        commands = []
        for phase in ("install", "startup"):
            for step in spec.get("setup", {}).get(phase, []):
                cmd = step.get("command", "")
                if isinstance(cmd, list):
                    commands.append(" ".join(cmd))
                else:
                    commands.append(cmd)
        return commands

    def test_referenced_files_exist(self):
        for cmd in self._all_setup_commands():
            for path in self._paths_in_command(cmd):
                self.assertTrue(
                    path.exists(),
                    f"spec references {path} but it does not exist on disk",
                )


class TestChmodTargetsAreExecutable(unittest.TestCase):
    """Every file targeted by chmod +x must be executable in the working tree."""

    def _chmod_targets(self) -> list[Path]:
        spec = load_spec()
        targets = []
        for phase in ("install", "startup"):
            for step in spec.get("setup", {}).get(phase, []):
                cmd = step.get("command", "")
                if not isinstance(cmd, str):
                    continue
                for line in cmd.splitlines():
                    line = line.strip()
                    if line.startswith("chmod +x "):
                        path_str = line[len("chmod +x ") :].strip()
                        path_str = path_str.replace("/home/agent/.claude/", "")
                        path_str = path_str.replace("${HOME}/.claude/", "")
                        if "/" in path_str or "." in path_str:
                            targets.append(FILES_HOME / path_str)
        return targets

    def test_chmod_targets_are_already_executable(self):
        targets = self._chmod_targets()
        self.assertGreater(len(targets), 0, "expected at least one chmod +x target")
        for path in targets:
            if not path.exists():
                continue
            mode = os.stat(path).st_mode
            self.assertTrue(
                mode & stat.S_IXUSR,
                f"{path} is targeted by chmod +x but is not executable in git",
            )
