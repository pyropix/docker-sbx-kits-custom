"""Unit tests for sbx_setup.py command building."""

import contextlib
import io
import unittest

import sbx_setup


class TestCurrentPlatform(unittest.TestCase):
    def test_maps_sys_platform_names(self):
        self.assertEqual(sbx_setup.normalise_platform("linux"), "linux")
        self.assertEqual(sbx_setup.normalise_platform("win32"), "windows")
        self.assertEqual(sbx_setup.normalise_platform("darwin"), "darwin")

    def test_unknown_platform_exits_rather_than_guessing(self):
        with self.assertRaises(SystemExit):
            sbx_setup.normalise_platform("plan9")


class TestBuildSetupCommands(unittest.TestCase):
    def _rendered(self, platform, user="agent"):
        return [
            c.args if isinstance(c.args, str) else " ".join(c.args)
            for c in sbx_setup.build_setup_commands(platform, user)
        ]

    def test_linux_sequence(self):
        self.assertEqual(
            self._rendered("linux"),
            [
                "curl -fsSL https://get.docker.com | sudo REPO_ONLY=1 sh",
                "sudo apt-get install -y docker-sbx",
                "sudo usermod -aG kvm agent",
                "sbx login",
            ],
        )

    def test_linux_pipeline_is_the_only_shell_command(self):
        cmds = sbx_setup.build_setup_commands("linux", "agent")
        self.assertTrue(cmds[0].shell)
        for cmd in cmds[1:]:
            self.assertFalse(cmd.shell)

    def test_linux_uses_the_given_user_not_a_literal(self):
        self.assertIn("sudo usermod -aG kvm someone-else", self._rendered("linux", "someone-else"))

    def test_windows_sequence(self):
        rendered = self._rendered("windows")
        self.assertIn("winget install -h Docker.sbx", rendered)
        self.assertIn("sbx login", rendered)
        self.assertTrue(
            any("HypervisorPlatform" in r for r in rendered),
            "the hypervisor check must be present",
        )

    def test_windows_hypervisor_check_tolerates_failure(self):
        """Get-WindowsOptionalFeature needs elevation; a failure there must
        not abort the install."""
        cmds = sbx_setup.build_setup_commands("windows", "agent")
        check = next(
            c for c in cmds if "HypervisorPlatform" in " ".join(c.args)
        )
        self.assertTrue(check.tolerate_failure)

    def test_darwin_sequence(self):
        self.assertEqual(
            self._rendered("darwin"),
            [
                "brew trust docker/tap",
                "brew install docker/tap/sbx",
                "sbx login",
            ],
        )

    def test_no_command_uses_shell_except_the_linux_pipeline(self):
        for platform in ("windows", "darwin"):
            for cmd in sbx_setup.build_setup_commands(platform, "agent"):
                self.assertFalse(cmd.shell, f"{platform}: {cmd.args}")


class TestDryRun(unittest.TestCase):
    def _run(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = sbx_setup.main(argv)
        return rc, buf.getvalue()

    def test_dry_run_linux_from_any_host(self):
        rc, out = self._run(["--dry-run", "--platform", "linux"])
        self.assertEqual(rc, 0)
        self.assertIn("REPO_ONLY=1", out)

    def test_dry_run_windows_from_any_host(self):
        rc, out = self._run(["--dry-run", "--platform", "windows"])
        self.assertEqual(rc, 0)
        self.assertIn("winget install -h Docker.sbx", out)

    def test_dry_run_darwin_from_any_host(self):
        rc, out = self._run(["--dry-run", "--platform", "darwin"])
        self.assertEqual(rc, 0)
        self.assertIn("brew install docker/tap/sbx", out)

    def test_dry_run_mentions_the_kvm_group_relogin(self):
        """newgrp kvm cannot work from a subprocess -- it spawns a
        replacement shell that exits immediately -- so the instruction is
        printed instead of faked."""
        _, out = self._run(["--dry-run", "--platform", "linux"])
        self.assertIn("log out", out.lower())

    def test_secret_gh_dry_run(self):
        rc, out = self._run(["--dry-run", "--secret-gh"])
        self.assertEqual(rc, 0)
        self.assertIn("gh auth token", out)
        self.assertIn("sbx secret set github --force", out)

    def test_secret_gh_skips_the_install(self):
        _, out = self._run(["--dry-run", "--secret-gh"])
        self.assertNotIn("docker-sbx", out)


class TestConfirmPlan(unittest.TestCase):
    def test_dry_run_does_not_prompt(self):
        import unittest.mock

        with unittest.mock.patch("builtins.input") as mock_input:
            rc, _ = TestDryRun()._run(["--dry-run", "--platform", "linux"])
        mock_input.assert_not_called()

    def test_declining_aborts_before_any_command_runs(self):
        import unittest.mock

        with unittest.mock.patch("builtins.input", return_value="n"):
            with unittest.mock.patch.object(sbx_setup.subprocess, "run") as run:
                rc = sbx_setup.do_install("linux", dry_run=False)
        run.assert_not_called()
        self.assertNotEqual(rc, 0)

    def test_yes_flag_skips_the_prompt(self):
        import unittest.mock

        completed = unittest.mock.Mock(returncode=0)
        with unittest.mock.patch("builtins.input") as mock_input:
            with unittest.mock.patch.object(sbx_setup.shutil, "which", return_value="/usr/bin/x"):
                with unittest.mock.patch.object(
                    sbx_setup.subprocess, "run", return_value=completed
                ):
                    rc = sbx_setup.do_install("linux", dry_run=False, assume_yes=True)
        mock_input.assert_not_called()
        self.assertEqual(rc, 0)


class TestNormaliseExit(unittest.TestCase):
    def test_signal_codes_become_128_plus_signal(self):
        self.assertEqual(sbx_setup.normalise_exit(-15), 143)
        self.assertEqual(sbx_setup.normalise_exit(-2), 130)

    def test_zero_and_positive_pass_through(self):
        self.assertEqual(sbx_setup.normalise_exit(0), 0)
        self.assertEqual(sbx_setup.normalise_exit(7), 7)


class TestRequireTool(unittest.TestCase):
    def test_missing_tool_exits_with_hint(self):
        import unittest.mock

        with unittest.mock.patch.object(sbx_setup.shutil, "which", return_value=None):
            with self.assertRaises(SystemExit) as ctx:
                sbx_setup.require_tool("gh", "Run 'gh auth login'.")
        self.assertIn("gh", str(ctx.exception))
        self.assertIn("gh auth login", str(ctx.exception))

    def test_present_tool_returns_path(self):
        import unittest.mock

        with unittest.mock.patch.object(
            sbx_setup.shutil, "which", return_value="/usr/bin/gh"
        ):
            self.assertEqual(sbx_setup.require_tool("gh", "hint"), "/usr/bin/gh")


class TestRequiredInstallTools(unittest.TestCase):
    def test_darwin_requires_brew(self):
        names = [n for n, _ in sbx_setup.required_install_tools("darwin")]
        self.assertEqual(names, ["brew"])

    def test_windows_requires_winget(self):
        names = [n for n, _ in sbx_setup.required_install_tools("windows")]
        self.assertEqual(names, ["winget"])

    def test_linux_requires_curl_and_sudo(self):
        names = [n for n, _ in sbx_setup.required_install_tools("linux")]
        self.assertEqual(names, ["curl", "sudo"])


class TestSecretGhToolChecks(unittest.TestCase):
    def test_missing_gh_exits_before_running(self):
        import unittest.mock

        def fake_which(name):
            return None if name == "gh" else f"/usr/bin/{name}"

        with unittest.mock.patch.object(sbx_setup.shutil, "which", fake_which):
            with unittest.mock.patch.object(sbx_setup.subprocess, "run") as run:
                with self.assertRaises(SystemExit):
                    sbx_setup.do_secret_gh(dry_run=False)
                run.assert_not_called()

    def test_dry_run_needs_no_tools(self):
        import unittest.mock

        with unittest.mock.patch.object(sbx_setup.shutil, "which", return_value=None):
            rc = sbx_setup.do_secret_gh(dry_run=True)
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
