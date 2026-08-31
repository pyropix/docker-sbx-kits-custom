"""Unit tests for the pure functions in sbx_run.py."""

import argparse
import unittest
from pathlib import Path

import sbx_run


class TestDeriveName(unittest.TestCase):
    def test_default_is_custom_kit_agent_mode(self):
        self.assertEqual(sbx_run.derive_name(True, None, "agent"), "claude-custom")

    def test_no_kit_agent_mode(self):
        self.assertEqual(sbx_run.derive_name(False, None, "agent"), "claude")

    def test_kit_ssh(self):
        self.assertEqual(sbx_run.derive_name(True, None, "ssh"), "claude-custom-ssh")

    def test_kit_vscode(self):
        self.assertEqual(sbx_run.derive_name(True, None, "vscode"), "claude-custom-vscode")

    def test_no_kit_ssh(self):
        self.assertEqual(sbx_run.derive_name(False, None, "ssh"), "claude-ssh")

    def test_no_kit_vscode(self):
        self.assertEqual(sbx_run.derive_name(False, None, "vscode"), "claude-vscode")

    def test_mcp_gets_its_own_segment(self):
        self.assertEqual(sbx_run.derive_name(False, "mslearn", "agent"), "claude-mcp")

    def test_mcp_composes_with_kit_and_mode(self):
        self.assertEqual(sbx_run.derive_name(True, "mslearn", "ssh"), "claude-custom-mcp-ssh")

    def test_agent_bash_and_tmux_derive_the_same_name(self):
        """Regression test for the 30/31 defect.

        31_docker_sbx_claude_custom_kit_bash.sh exec'd into `claude-custom`
        while 30_docker_sbx_claude_custom_kit.sh created `claude-custom-kit`,
        so it never attached to anything. Deriving all three from one
        expression makes them agree by construction.
        """
        for use_kit in (True, False):
            for mcp in (None, "mslearn"):
                base = sbx_run.derive_name(use_kit, mcp, "agent")
                self.assertEqual(sbx_run.derive_name(use_kit, mcp, "bash"), base)
                self.assertEqual(sbx_run.derive_name(use_kit, mcp, "tmux"), base)

    def test_all_ten_kit_mode_combinations(self):
        expected = {
            (True, "agent"): "claude-custom",
            (True, "bash"): "claude-custom",
            (True, "tmux"): "claude-custom",
            (True, "ssh"): "claude-custom-ssh",
            (True, "vscode"): "claude-custom-vscode",
            (False, "agent"): "claude",
            (False, "bash"): "claude",
            (False, "tmux"): "claude",
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
                "sbx",
                "run",
                "--name",
                "claude-custom",
                "--kit",
                "/repo/sbx-kits/claude-custom",
                "claude",
                "/home/user/proj",
            ],
        )

    def test_run_with_mcp(self):
        argv = sbx_run.build_sbx_argv("run", "claude-mcp", None, "mslearn", self.WORKSPACE)
        self.assertEqual(
            argv,
            [
                "sbx",
                "run",
                "--name",
                "claude-mcp",
                "--static-mcp",
                "mslearn",
                "claude",
                "/home/user/proj",
            ],
        )

    def test_create_verb(self):
        argv = sbx_run.build_sbx_argv("create", "claude-ssh", None, None, self.WORKSPACE)
        self.assertEqual(argv[:2], ["sbx", "create"])

    def test_flags_precede_agent_and_workspace_is_last(self):
        """Scripts 20 and 30 write `sbx run --name ... claude`; script 21 writes
        `sbx run claude --name ...`. The canonical form follows the majority."""
        argv = sbx_run.build_sbx_argv("run", "n", Path("/k"), "mslearn", self.WORKSPACE)
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
            sbx_run.build_exec_argv("claude-custom", ["bash"]),
            ["sbx", "exec", "-it", "claude-custom", "bash"],
        )

    def test_attach_argv_agent_reattaches(self):
        self.assertEqual(
            sbx_run.build_attach_argv("agent", "claude-custom"),
            ["sbx", "run", "--name", "claude-custom"],
        )

    def test_attach_argv_bash_execs_bash(self):
        self.assertEqual(
            sbx_run.build_attach_argv("bash", "claude-custom"),
            ["sbx", "exec", "-it", "claude-custom", "bash"],
        )

    def test_attach_argv_tmux_attaches_or_creates_main_session(self):
        self.assertEqual(
            sbx_run.build_attach_argv("tmux", "claude-custom"),
            ["sbx", "exec", "-it", "claude-custom", "tmux", "new-session", "-A", "-s", "main"],
        )

    def test_ssh_argv(self):
        self.assertEqual(
            sbx_run.build_ssh_argv("claude-ssh", "/work/proj"),
            ["ssh", "-t", "claude-ssh.sbx", "cd /work/proj ; bash --login"],
        )

    def test_ssh_argv_quotes_a_path_with_a_space(self):
        self.assertEqual(
            sbx_run.build_ssh_argv("claude-ssh", "/home/u/My Project"),
            [
                "ssh",
                "-t",
                "claude-ssh.sbx",
                "cd '/home/u/My Project' ; bash --login",
            ],
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
        self.assertEqual(sbx_run.resolve_mcp("custom", "https://example.test/mcp"), "custom")


class TestParser(unittest.TestCase):
    def setUp(self):
        self.parser = sbx_run.build_parser()

    def test_bare_invocation_defaults_to_agent_mode_with_the_kit(self):
        args = self.parser.parse_args([])
        self.assertEqual(args.command, "run")
        self.assertEqual(args.mode, "agent")
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
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = sbx_run.run_interactive(["definitely-not-a-real-binary"], dry_run=True)
        self.assertEqual(rc, 0)
        self.assertIn("definitely-not-a-real-binary", buf.getvalue())

    def test_dry_run_of_run_mode_emits_the_full_command(self):
        import contextlib
        import io

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
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sbx_run.main(["--dry-run", "--workspace", "/somewhere/unrelated"])
        self.assertIn(str(sbx_run.KIT_DIR), buf.getvalue())

    def test_dry_run_bash_mode_targets_the_run_sandbox(self):
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sbx_run.main(["--dry-run", "--mode", "bash"])
        self.assertIn("sbx exec -it claude-custom bash", buf.getvalue())


class TestParseInspectWorkspace(unittest.TestCase):
    """The parser handles both the verified real-world format and several
    plausible variants, returning None for anything it cannot recognise."""

    # Real shape verified against `sbx inspect --json` on daemon v0.39.0.
    REAL_INSPECT_JSON = """{
      "name": "claude-custom",
      "agent": "claude",
      "kits": ["/repo/sbx-kits/claude-custom"],
      "state": "stopped",
      "workspace": "/home/user/proj",
      "network": "claude-custom",
      "sessions": 0
    }"""

    def test_real_sbx_inspect_json_shape(self):
        """Verified against sbx daemon v0.39.0 (sbx inspect --json)."""
        self.assertEqual(
            sbx_run.parse_inspect_workspace(self.REAL_INSPECT_JSON),
            "/home/user/proj",
        )

    def test_json_workspace_key(self):
        self.assertEqual(
            sbx_run.parse_inspect_workspace('{"workspace": "/work/proj"}'),
            "/work/proj",
        )

    def test_json_camel_case_key(self):
        self.assertEqual(
            sbx_run.parse_inspect_workspace('{"workspaceDir": "/work/proj"}'),
            "/work/proj",
        )

    def test_json_nested_under_a_parent_object(self):
        self.assertEqual(
            sbx_run.parse_inspect_workspace('{"config": {"WorkspaceDir": "/work/proj"}}'),
            "/work/proj",
        )

    def test_json_list_wrapper(self):
        self.assertEqual(
            sbx_run.parse_inspect_workspace('[{"workspace": "/work/proj"}]'),
            "/work/proj",
        )

    def test_unrecognised_output_returns_none(self):
        self.assertIsNone(sbx_run.parse_inspect_workspace("some unstructured text"))

    def test_invalid_json_returns_none(self):
        self.assertIsNone(sbx_run.parse_inspect_workspace("{not json"))

    def test_empty_output_returns_none(self):
        self.assertIsNone(sbx_run.parse_inspect_workspace(""))


class TestSandboxWorkspacePathDryRun(unittest.TestCase):
    def test_dry_run_uses_the_host_path_without_probing(self):
        result = sbx_run.sandbox_workspace_path("claude-ssh", Path("/home/user/proj"), dry_run=True)
        self.assertEqual(result, "/home/user/proj")


class TestSandboxWorkspacePathProbeChain(unittest.TestCase):
    """`sbx inspect` is host-side data, so a non-absolute candidate (e.g. a
    Windows host path) must not shortcut the fallback chain."""

    def test_non_absolute_inspect_result_falls_through_to_exec_probe(self):
        calls = []

        def fake_run_capture(argv):
            calls.append(argv)
            if argv[:2] == ["sbx", "inspect"]:
                return 0, '{"workspace": "C:\\\\Users\\\\me\\\\proj"}'
            if argv[:2] == ["sbx", "exec"]:
                return 0, "/home/user/proj\n"
            raise AssertionError(f"unexpected call: {argv}")

        original = sbx_run.run_capture
        sbx_run.run_capture = fake_run_capture
        try:
            result = sbx_run.sandbox_workspace_path("claude-ssh", Path("/host/proj"), dry_run=False)
        finally:
            sbx_run.run_capture = original

        self.assertEqual(result, "/home/user/proj")
        self.assertEqual(len(calls), 2)

    def test_absolute_inspect_result_is_accepted_without_further_probes(self):
        calls = []

        def fake_run_capture(argv):
            calls.append(argv)
            if argv[:2] == ["sbx", "inspect"]:
                return 0, '{"workspace": "/sandbox/proj"}'
            raise AssertionError(f"unexpected call: {argv}")

        original = sbx_run.run_capture
        sbx_run.run_capture = fake_run_capture
        try:
            result = sbx_run.sandbox_workspace_path("claude-ssh", Path("/host/proj"), dry_run=False)
        finally:
            sbx_run.run_capture = original

        self.assertEqual(result, "/sandbox/proj")
        self.assertEqual(len(calls), 1)


class TestAttachDryRun(unittest.TestCase):
    def _run(self, argv):
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = sbx_run.main(argv)
        return rc, buf.getvalue()

    def test_ssh_mode_creates_sets_up_ssh_then_connects(self):
        rc, out = self._run(["--dry-run", "--mode", "ssh", "--workspace", "/tmp/proj"])
        self.assertEqual(rc, 0)
        self.assertIn("sbx create --name claude-custom-ssh", out)
        self.assertIn("sbx setup ssh --alias claude-custom-ssh.sbx", out)
        self.assertIn("ssh -t claude-custom-ssh.sbx", out)
        self.assertLess(out.index("sbx create"), out.index("sbx setup ssh"))
        self.assertLess(out.index("sbx setup ssh"), out.index("ssh -t"))

    def test_vscode_mode_emits_the_remote_flag(self):
        rc, out = self._run(["--dry-run", "--mode", "vscode", "--no-kit"])
        self.assertEqual(rc, 0)
        self.assertIn("--remote ssh-remote+claude-vscode.sbx", out)

    def test_mcp_registration_precedes_the_run(self):
        rc, out = self._run(["--dry-run", "--no-kit", "--mcp", "mslearn"])
        self.assertEqual(rc, 0)
        self.assertIn("sbx mcp add mslearn --url https://learn.microsoft.com/api/mcp", out)
        self.assertLess(out.index("sbx mcp add"), out.index("sbx run"))


class TestStopDryRun(unittest.TestCase):
    def _run(self, argv):
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = sbx_run.main(argv)
        return rc, buf.getvalue()

    def test_stop_without_rm(self):
        rc, out = self._run(["stop", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("sbx stop claude-custom", out)
        self.assertNotIn("sbx rm", out)

    def test_stop_with_rm_stops_then_removes(self):
        rc, out = self._run(["stop", "--rm", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("sbx stop claude-custom", out)
        self.assertIn("sbx rm claude-custom --force", out)
        self.assertLess(out.index("sbx stop"), out.index("sbx rm"))

    def test_stop_derives_the_same_name_as_the_matching_run(self):
        _, run_out = self._run(["--dry-run", "--mode", "ssh", "--no-kit"])
        _, stop_out = self._run(["stop", "--dry-run", "--mode", "ssh", "--no-kit"])
        self.assertIn("claude-ssh", run_out)
        self.assertIn("sbx stop claude-ssh", stop_out)


class TestPromptCleanup(unittest.TestCase):
    """The printed `stop` command must resolve to the sandbox actually named
    in the message above it -- i.e. round-trip through build_parser() and
    sandbox_name() back to the same name."""

    def _printed_command(self, out: str) -> str:
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("./sbx_run.py"):
                return line
        raise AssertionError(f"no printed command found in: {out!r}")

    def _round_trip_name(self, printed_command: str) -> str:
        # Strip the leading "./sbx_run.py" token; the rest are argparse args.
        import shlex as _shlex

        tokens = _shlex.split(printed_command)[1:]
        args = sbx_run.build_parser().parse_args(tokens)
        return sbx_run.sandbox_name(args)

    def _capture(self, args: argparse.Namespace, name: str) -> str:
        import contextlib
        import io
        from unittest.mock import patch

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), patch("builtins.input", return_value=""):
            sbx_run.prompt_cleanup(args, name)
        return buf.getvalue()

    def test_name_present_round_trips_to_the_same_sandbox(self):
        args = sbx_run.build_parser().parse_args(["--mode", "ssh", "--name", "my-sandbox"])
        name = sbx_run.sandbox_name(args)
        out = self._capture(args, name)
        printed = self._printed_command(out)
        self.assertIn("--name my-sandbox", printed)
        self.assertEqual(self._round_trip_name(printed), name)
        self.assertEqual(name, "my-sandbox")

    def test_name_absent_default_mode_and_kit_round_trips(self):
        args = sbx_run.build_parser().parse_args([])
        name = sbx_run.sandbox_name(args)
        out = self._capture(args, name)
        printed = self._printed_command(out)
        self.assertEqual(self._round_trip_name(printed), name)

    def test_name_absent_ssh_no_kit_round_trips(self):
        args = sbx_run.build_parser().parse_args(["--mode", "ssh", "--no-kit"])
        name = sbx_run.sandbox_name(args)
        out = self._capture(args, name)
        printed = self._printed_command(out)
        self.assertIn("--mode ssh", printed)
        self.assertIn("--no-kit", printed)
        self.assertEqual(self._round_trip_name(printed), name)

    def test_name_absent_vscode_mcp_round_trips(self):
        args = sbx_run.build_parser().parse_args(["--mode", "vscode", "--mcp", "mslearn"])
        name = sbx_run.sandbox_name(args)
        out = self._capture(args, name)
        printed = self._printed_command(out)
        self.assertIn("--mode vscode", printed)
        self.assertIn("--mcp mslearn", printed)
        self.assertEqual(self._round_trip_name(printed), name)


class TestBuildReattachArgv(unittest.TestCase):
    def test_only_contains_name_flag(self):
        argv = sbx_run.build_reattach_argv("claude-custom")
        self.assertEqual(argv, ["sbx", "run", "--name", "claude-custom"])

    def test_does_not_include_kit_or_workspace(self):
        argv = sbx_run.build_reattach_argv("claude-custom")
        self.assertNotIn("--kit", argv)
        self.assertNotIn("--static-mcp", argv)


class TestAgentModeExistingSandbox(unittest.TestCase):
    def _patch(self, inspect_rc, create_rc=0):
        capture_calls = []
        interactive_calls = []

        def fake_capture(argv):
            capture_calls.append(argv)
            if argv[:2] == ["sbx", "inspect"]:
                return inspect_rc, ""
            raise AssertionError(f"unexpected run_capture call: {argv}")

        def fake_interactive(argv, dry_run=False):
            interactive_calls.append(argv)
            if argv[:2] == ["sbx", "create"]:
                return create_rc
            return 0

        self._orig_cap = sbx_run.run_capture
        self._orig_int = sbx_run.run_interactive
        sbx_run.run_capture = fake_capture
        sbx_run.run_interactive = fake_interactive
        return capture_calls, interactive_calls

    def _restore(self):
        sbx_run.run_capture = self._orig_cap
        sbx_run.run_interactive = self._orig_int

    def test_existing_sandbox_skips_create_and_reattaches(self):
        _cap, inter = self._patch(inspect_rc=0)
        try:
            args = sbx_run.build_parser().parse_args(["--workspace", "/tmp/proj"])
            sbx_run.cmd_run(args)
        finally:
            self._restore()
        self.assertFalse(any(c[:2] == ["sbx", "create"] for c in inter))
        self.assertEqual(inter, [["sbx", "run", "--name", "claude-custom"]])

    def test_new_sandbox_is_created_then_reattached(self):
        _cap, inter = self._patch(inspect_rc=1)
        try:
            args = sbx_run.build_parser().parse_args(["--workspace", "/tmp/proj"])
            sbx_run.cmd_run(args)
        finally:
            self._restore()
        create_calls = [c for c in inter if c[:2] == ["sbx", "create"]]
        self.assertEqual(len(create_calls), 1)
        self.assertIn("--kit", create_calls[0])
        self.assertEqual(
            inter,
            [create_calls[0], ["sbx", "run", "--name", "claude-custom"]],
        )

    def test_dry_run_skips_probe_and_emits_full_command(self):
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = sbx_run.main(["--dry-run", "--workspace", "/tmp/proj"])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("sbx run --name claude-custom", out)
        self.assertIn("--kit", out)

    def test_inspect_probe_is_not_called_in_dry_run(self):
        def fail_if_inspect(argv):
            if argv[:2] == ["sbx", "inspect"]:
                raise AssertionError("probe must not fire in dry_run")
            return 0, ""

        orig = sbx_run.run_capture
        sbx_run.run_capture = fail_if_inspect
        try:
            sbx_run.main(["--dry-run", "--workspace", "/tmp/proj"])
        finally:
            sbx_run.run_capture = orig


class TestNormaliseExit(unittest.TestCase):
    def test_zero_and_positive_pass_through(self):
        self.assertEqual(sbx_run.normalise_exit(0), 0)
        self.assertEqual(sbx_run.normalise_exit(1), 1)
        self.assertEqual(sbx_run.normalise_exit(143), 143)

    def test_signal_codes_become_128_plus_signal(self):
        # -15 (SIGTERM) -> 143, not the 241 that sys.exit(-15) would yield.
        self.assertEqual(sbx_run.normalise_exit(-15), 143)
        self.assertEqual(sbx_run.normalise_exit(-2), 130)
        self.assertEqual(sbx_run.normalise_exit(-9), 137)


class TestCmdStop(unittest.TestCase):
    """A failed `sbx stop` must not be masked by a following successful rm."""

    def _run_with(self, argv, returns):
        calls = []

        def fake(cmd, dry_run=False):
            calls.append(cmd)
            return returns[cmd[1]]

        original = sbx_run.run_interactive
        sbx_run.run_interactive = fake
        try:
            args = sbx_run.build_parser().parse_args(argv)
            rc = sbx_run.cmd_stop(args)
        finally:
            sbx_run.run_interactive = original
        return rc, calls

    def test_failed_stop_then_successful_rm_reports_failure(self):
        rc, calls = self._run_with(["stop", "--rm"], {"stop": 3, "rm": 0})
        self.assertEqual(rc, 3)
        self.assertEqual([c[1] for c in calls], ["stop", "rm"])

    def test_successful_stop_then_failed_rm_reports_failure(self):
        rc, _ = self._run_with(["stop", "--rm"], {"stop": 0, "rm": 4})
        self.assertEqual(rc, 4)

    def test_both_succeed(self):
        rc, _ = self._run_with(["stop", "--rm"], {"stop": 0, "rm": 0})
        self.assertEqual(rc, 0)


class TestEnsureMcpRegistered(unittest.TestCase):
    def _patch(self, inspect_rc, add_rc=0):
        capture_calls = []
        interactive_calls = []

        def fake_capture(argv):
            capture_calls.append(argv)
            return inspect_rc, ""

        def fake_interactive(argv, dry_run=False):
            interactive_calls.append(argv)
            return add_rc

        self._orig_cap = sbx_run.run_capture
        self._orig_int = sbx_run.run_interactive
        sbx_run.run_capture = fake_capture
        sbx_run.run_interactive = fake_interactive
        return capture_calls, interactive_calls

    def _restore(self):
        sbx_run.run_capture = self._orig_cap
        sbx_run.run_interactive = self._orig_int

    def test_already_registered_skips_add(self):
        cap, inter = self._patch(inspect_rc=0)
        try:
            sbx_run.ensure_mcp_registered("mslearn", None, dry_run=False)
        finally:
            self._restore()
        self.assertEqual(cap[0][:3], ["sbx", "mcp", "inspect"])
        self.assertEqual(inter, [])

    def test_missing_server_is_added(self):
        _cap, inter = self._patch(inspect_rc=1, add_rc=0)
        try:
            sbx_run.ensure_mcp_registered("mslearn", None, dry_run=False)
        finally:
            self._restore()
        self.assertEqual(len(inter), 1)
        self.assertEqual(inter[0][:3], ["sbx", "mcp", "add"])

    def test_failed_add_exits_nonzero(self):
        self._patch(inspect_rc=1, add_rc=5)
        try:
            with self.assertRaises(SystemExit) as ctx:
                sbx_run.ensure_mcp_registered("mslearn", None, dry_run=False)
        finally:
            self._restore()
        self.assertEqual(ctx.exception.code, 5)


class TestSandboxWorkspaceInspectUsesJson(unittest.TestCase):
    def test_inspect_probe_passes_json_flag(self):
        calls = []

        def fake_run_capture(argv):
            calls.append(argv)
            if argv[:2] == ["sbx", "inspect"]:
                return 0, '{"workspace": "/sandbox/proj"}'
            raise AssertionError(f"unexpected call: {argv}")

        original = sbx_run.run_capture
        sbx_run.run_capture = fake_run_capture
        try:
            result = sbx_run.sandbox_workspace_path("claude-ssh", Path("/host/proj"), dry_run=False)
        finally:
            sbx_run.run_capture = original
        self.assertEqual(result, "/sandbox/proj")
        self.assertIn("--json", calls[0])


class TestInvocationPrefix(unittest.TestCase):
    def test_posix_uses_dot_slash(self):
        import unittest.mock

        with unittest.mock.patch.object(sbx_run.sys, "platform", "linux"):
            self.assertEqual(sbx_run.invocation_prefix(), "./sbx_run.py")

    def test_windows_uses_uv_run(self):
        import unittest.mock

        with unittest.mock.patch.object(sbx_run.sys, "platform", "win32"):
            self.assertEqual(sbx_run.invocation_prefix(), "uv run sbx_run.py")


class TestMcpUrlValidation(unittest.TestCase):
    """#10: --mcp-url without --mcp is rejected; already-registered warns."""

    def test_mcp_url_without_mcp_is_rejected(self):
        with self.assertRaises(SystemExit):
            sbx_run.main(["--dry-run", "--mcp-url", "https://example.test/mcp"])

    def test_mcp_url_with_mcp_is_accepted(self):
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = sbx_run.main(
                ["--dry-run", "--mcp", "mslearn", "--mcp-url", "https://example.test/mcp"]
            )
        self.assertEqual(rc, 0)

    def test_already_registered_with_mcp_url_prints_warning(self):
        import contextlib
        import io

        def fake_capture(argv):
            if argv[:3] == ["sbx", "mcp", "inspect"]:
                return 0, ""
            return 0, ""

        original = sbx_run.run_capture
        sbx_run.run_capture = fake_capture
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                sbx_run.ensure_mcp_registered("mslearn", "https://other.test/mcp", dry_run=False)
        finally:
            sbx_run.run_capture = original
        self.assertIn("already registered", buf.getvalue())
        self.assertIn("--mcp-url is ignored", buf.getvalue())


class TestRmValidation(unittest.TestCase):
    """#10: --rm outside the stop command is rejected."""

    def test_rm_without_stop_is_rejected(self):
        with self.assertRaises(SystemExit):
            sbx_run.main(["--dry-run", "--rm"])

    def test_rm_with_stop_is_accepted(self):
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = sbx_run.main(["stop", "--rm", "--dry-run"])
        self.assertEqual(rc, 0)


class TestBashAndTmuxModeCreateIfMissing(unittest.TestCase):
    """--mode bash/tmux create the sandbox first instead of erroring out."""

    def _patch(self, inspect_rc, create_rc=0):
        capture_calls = []
        interactive_calls = []

        def fake_capture(argv):
            capture_calls.append(argv)
            if argv[:2] == ["sbx", "inspect"]:
                return inspect_rc, ""
            raise AssertionError(f"unexpected run_capture call: {argv}")

        def fake_interactive(argv, dry_run=False):
            interactive_calls.append(argv)
            if argv[:2] == ["sbx", "create"]:
                return create_rc
            return 0

        self._orig_cap = sbx_run.run_capture
        self._orig_int = sbx_run.run_interactive
        sbx_run.run_capture = fake_capture
        sbx_run.run_interactive = fake_interactive
        return capture_calls, interactive_calls

    def _restore(self):
        sbx_run.run_capture = self._orig_cap
        sbx_run.run_interactive = self._orig_int

    def test_bash_mode_creates_then_execs_bash_when_missing(self):
        _cap, inter = self._patch(inspect_rc=1)
        try:
            args = sbx_run.build_parser().parse_args(["--mode", "bash", "--workspace", "/tmp/proj"])
            sbx_run.cmd_run(args)
        finally:
            self._restore()
        self.assertTrue(any(c[:2] == ["sbx", "create"] for c in inter))
        self.assertEqual(
            inter,
            [
                [
                    "sbx",
                    "create",
                    "--name",
                    "claude-custom",
                    "--kit",
                    str(sbx_run.KIT_DIR),
                    "claude",
                    "/tmp/proj",
                ],
                ["sbx", "exec", "-it", "claude-custom", "bash"],
            ],
        )

    def test_tmux_mode_skips_create_and_attaches_when_sandbox_exists(self):
        _cap, inter = self._patch(inspect_rc=0)
        try:
            args = sbx_run.build_parser().parse_args(["--mode", "tmux", "--workspace", "/tmp/proj"])
            sbx_run.cmd_run(args)
        finally:
            self._restore()
        self.assertFalse(any(c[:2] == ["sbx", "create"] for c in inter))
        self.assertEqual(
            inter,
            [["sbx", "exec", "-it", "claude-custom", "tmux", "new-session", "-A", "-s", "main"]],
        )


class TestSandboxExistsUsesJson(unittest.TestCase):
    """#11: sandbox_exists and sandbox_workspace_path both pass --json."""

    def test_sandbox_exists_passes_json_flag(self):
        calls = []

        def fake_capture(argv):
            calls.append(argv)
            return 0, ""

        original = sbx_run.run_capture
        sbx_run.run_capture = fake_capture
        try:
            sbx_run.sandbox_exists("claude-custom")
        finally:
            sbx_run.run_capture = original
        self.assertIn("--json", calls[0])


if __name__ == "__main__":
    unittest.main()
