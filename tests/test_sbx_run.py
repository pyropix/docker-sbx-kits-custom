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


class TestResolveWorkspace(unittest.TestCase):
    def test_default_is_cwd(self):
        self.assertEqual(sbx_run.resolve_workspace(None), Path.cwd())

    def test_explicit_path_is_made_absolute(self):
        result = sbx_run.resolve_workspace("..")
        self.assertTrue(result.is_absolute())
        self.assertEqual(result, Path.cwd().parent.resolve())

    def test_tilde_is_expanded(self):
        result = sbx_run.resolve_workspace("~")
        self.assertEqual(result, Path.home().resolve())


class TestResolveMcp(unittest.TestCase):
    def test_none_when_not_requested(self):
        self.assertIsNone(sbx_run.resolve_mcp(None, None))

    def test_known_name_needs_no_url(self):
        self.assertEqual(sbx_run.resolve_mcp("mslearn", None), "mslearn")

    def test_unknown_name_without_url_is_an_error(self):
        with self.assertRaises(SystemExit):
            sbx_run.resolve_mcp("something-else", None)

    def test_unknown_name_with_url_is_accepted(self):
        self.assertEqual(
            sbx_run.resolve_mcp("custom", "https://example.test/mcp"), "custom"
        )


class TestParser(unittest.TestCase):
    def setUp(self):
        self.parser = sbx_run.build_parser()

    def test_bare_invocation_defaults_to_run_with_the_kit(self):
        args = self.parser.parse_args([])
        self.assertEqual(args.command, "run")
        self.assertEqual(args.mode, "run")
        self.assertFalse(args.no_kit)

    def test_stop_is_a_positional_not_a_subparser(self):
        args = self.parser.parse_args(["stop", "--rm"])
        self.assertEqual(args.command, "stop")
        self.assertTrue(args.rm)

    def test_stop_accepts_the_name_deriving_flags(self):
        args = self.parser.parse_args(["stop", "--mode", "ssh", "--no-kit"])
        self.assertEqual(args.mode, "ssh")
        self.assertTrue(args.no_kit)

    def test_stop_accepts_but_ignores_workspace(self):
        """--workspace is meaningless for stop; it is silently ignored, not
        rejected, because run and stop share one flag namespace."""
        args = self.parser.parse_args(["stop", "--workspace", "/tmp"])
        self.assertEqual(args.command, "stop")

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["--mode", "telepathy"])


class TestDryRun(unittest.TestCase):
    def test_dry_run_prints_and_does_not_execute(self):
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = sbx_run.run_interactive(["definitely-not-a-real-binary"], dry_run=True)
        self.assertEqual(rc, 0)
        self.assertIn("definitely-not-a-real-binary", buf.getvalue())

    def test_dry_run_of_run_mode_emits_the_full_command(self):
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = sbx_run.main(["--dry-run", "--workspace", "/tmp/proj"])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("sbx run --name claude-custom", out)
        self.assertIn(str(sbx_run.KIT_DIR), out)
        self.assertIn("/tmp/proj", out)

    def test_dry_run_kit_path_is_independent_of_the_workspace(self):
        """Regression guard: the kit must not be resolved relative to the
        mounted workspace."""
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sbx_run.main(["--dry-run", "--workspace", "/somewhere/unrelated"])
        self.assertIn(str(sbx_run.KIT_DIR), buf.getvalue())

    def test_dry_run_bash_mode_targets_the_run_sandbox(self):
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sbx_run.main(["--dry-run", "--mode", "bash"])
        self.assertIn("sbx exec -it claude-custom bash", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
