"""Unit tests for the pure functions in sbx_run.py."""

import unittest
from pathlib import Path

import sbx_run


class TestDeriveName(unittest.TestCase):
    def test_default_is_custom_kit_run_mode(self):
        self.assertEqual(sbx_run.derive_name(True, None, "run"), "claude-custom")

    def test_no_kit_run_mode(self):
        self.assertEqual(sbx_run.derive_name(False, None, "run"), "claude")

    def test_kit_ssh(self):
        self.assertEqual(sbx_run.derive_name(True, None, "ssh"), "claude-custom-ssh")

    def test_kit_vscode(self):
        self.assertEqual(sbx_run.derive_name(True, None, "vscode"), "claude-custom-vscode")

    def test_no_kit_ssh(self):
        self.assertEqual(sbx_run.derive_name(False, None, "ssh"), "claude-ssh")

    def test_no_kit_vscode(self):
        self.assertEqual(sbx_run.derive_name(False, None, "vscode"), "claude-vscode")

    def test_mcp_gets_its_own_segment(self):
        self.assertEqual(sbx_run.derive_name(False, "mslearn", "run"), "claude-mcp")

    def test_mcp_composes_with_kit_and_mode(self):
        self.assertEqual(
            sbx_run.derive_name(True, "mslearn", "ssh"), "claude-custom-mcp-ssh"
        )

    def test_bash_and_run_derive_the_same_name(self):
        """Regression test for the 30/31 defect.

        31_docker_sbx_claude_custom_kit_bash.sh exec'd into `claude-custom`
        while 30_docker_sbx_claude_custom_kit.sh created `claude-custom-kit`,
        so it never attached to anything. Deriving both from one expression
        makes them agree by construction.
        """
        for use_kit in (True, False):
            for mcp in (None, "mslearn"):
                self.assertEqual(
                    sbx_run.derive_name(use_kit, mcp, "bash"),
                    sbx_run.derive_name(use_kit, mcp, "run"),
                )

    def test_all_eight_kit_mode_combinations(self):
        expected = {
            (True, "run"): "claude-custom",
            (True, "bash"): "claude-custom",
            (True, "ssh"): "claude-custom-ssh",
            (True, "vscode"): "claude-custom-vscode",
            (False, "run"): "claude",
            (False, "bash"): "claude",
            (False, "ssh"): "claude-ssh",
            (False, "vscode"): "claude-vscode",
        }
        for (use_kit, mode), want in expected.items():
            with self.subTest(use_kit=use_kit, mode=mode):
                self.assertEqual(sbx_run.derive_name(use_kit, None, mode), want)


class TestBuildSbxArgv(unittest.TestCase):
    WORKSPACE = Path("/home/user/proj")

    def test_run_without_kit(self):
        self.assertEqual(
            sbx_run.build_sbx_argv("run", "claude", None, None, self.WORKSPACE),
            ["sbx", "run", "--name", "claude", "claude", "/home/user/proj"],
        )

    def test_run_with_kit(self):
        argv = sbx_run.build_sbx_argv(
            "run", "claude-custom", Path("/repo/sbx-kits/claude-custom"), None, self.WORKSPACE
        )
        self.assertEqual(
            argv,
            [
                "sbx", "run", "--name", "claude-custom",
                "--kit", "/repo/sbx-kits/claude-custom",
                "claude", "/home/user/proj",
            ],
        )

    def test_run_with_mcp(self):
        argv = sbx_run.build_sbx_argv("run", "claude-mcp", None, "mslearn", self.WORKSPACE)
        self.assertEqual(
            argv,
            [
                "sbx", "run", "--name", "claude-mcp",
                "--static-mcp", "mslearn",
                "claude", "/home/user/proj",
            ],
        )

    def test_create_verb(self):
        argv = sbx_run.build_sbx_argv("create", "claude-ssh", None, None, self.WORKSPACE)
        self.assertEqual(argv[:2], ["sbx", "create"])

    def test_flags_precede_agent_and_workspace_is_last(self):
        """Scripts 20 and 30 write `sbx run --name ... claude`; script 21 writes
        `sbx run claude --name ...`. The canonical form follows the majority."""
        argv = sbx_run.build_sbx_argv(
            "run", "n", Path("/k"), "mslearn", self.WORKSPACE
        )
        self.assertEqual(argv[-2:], ["claude", "/home/user/proj"])
        self.assertLess(argv.index("--name"), argv.index("claude"))

    def test_kit_path_is_stringified_not_a_path_object(self):
        argv = sbx_run.build_sbx_argv("run", "n", Path("/k"), None, self.WORKSPACE)
        for item in argv:
            self.assertIsInstance(item, str)


class TestOtherArgvBuilders(unittest.TestCase):
    def test_alias_appends_sbx_suffix(self):
        self.assertEqual(sbx_run.alias_for("claude-custom-ssh"), "claude-custom-ssh.sbx")

    def test_exec_argv(self):
        self.assertEqual(
            sbx_run.build_exec_argv("claude-custom"),
            ["sbx", "exec", "-it", "claude-custom", "bash"],
        )

    def test_ssh_argv(self):
        self.assertEqual(
            sbx_run.build_ssh_argv("claude-ssh", "/work/proj"),
            ["ssh", "-t", "claude-ssh.sbx", "cd /work/proj ; bash --login"],
        )

    def test_vscode_argv(self):
        self.assertEqual(
            sbx_run.build_vscode_argv("/usr/bin/code", "claude-vscode", "/work/proj"),
            ["/usr/bin/code", "--remote", "ssh-remote+claude-vscode.sbx", "/work/proj"],
        )


class TestKitDir(unittest.TestCase):
    def test_kit_dir_is_anchored_to_the_script_not_the_cwd(self):
        """`./sbx_run.py` run from an unrelated project must still find the kit
        in this repository."""
        expected = Path(sbx_run.__file__).resolve().parent / "sbx-kits" / "claude-custom"
        self.assertEqual(sbx_run.KIT_DIR, expected)
        self.assertTrue(sbx_run.KIT_DIR.is_absolute())


if __name__ == "__main__":
    unittest.main()
