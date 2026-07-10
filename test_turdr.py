#!/usr/bin/env python3
"""turdr test suite.

Three layers, all stdlib:
  * unit tests with the process boundary stubbed (no gary/tmux needed)
  * CLI integration tests against a real temp gary db (skipped without gary)
  * an end-to-end tmux test on an isolated socket (skipped without tmux);
    it never touches the developer's own tmux server or sessions.

Run: python3 test_turdr.py
"""

import importlib.machinery
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
TURDR = os.path.join(HERE, "turdr")

loader = importlib.machinery.SourceFileLoader("turdr_mod", TURDR)
spec = importlib.util.spec_from_loader("turdr_mod", loader)
turdr = importlib.util.module_from_spec(spec)
loader.exec_module(turdr)

HAVE_GARY = shutil.which("gary") is not None
HAVE_TMUX = shutil.which("tmux") is not None


def completed(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def base_cfg(**overrides):
    cfg = dict(turdr.DEFAULTS)
    cfg["agents"] = {}
    cfg.update(overrides)
    return cfg


class ConfigTests(unittest.TestCase):
    def write(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False)
        self.addCleanup(os.unlink, f.name)
        f.write(text)
        f.close()
        return f.name

    def test_missing_path_means_defaults(self):
        cfg = turdr.load_config(None)
        self.assertEqual(cfg["session"], "gary")
        self.assertEqual(cfg["agents"], {})

    def test_values_override_defaults(self):
        cfg = turdr.load_config(self.write(
            'session = "fleet"\npoll_interval = 7\n'
            '[agents.a1]\ncommand = "run {agent}"\n'))
        self.assertEqual(cfg["session"], "fleet")
        self.assertEqual(cfg["poll_interval"], 7)
        self.assertEqual(cfg["agents"]["a1"]["command"], "run {agent}")

    def test_rejects_bad_agent_name(self):
        with self.assertRaisesRegex(turdr.TurdrError, "bad agent name"):
            turdr.load_config(self.write('[agents."has space"]\ncommand="x"\n'))

    def test_rejects_unknown_agent_key(self):
        with self.assertRaisesRegex(turdr.TurdrError, "unknown keys"):
            turdr.load_config(self.write('[agents.a]\nrepo = "x"\n'))

    def test_rejects_bad_session(self):
        with self.assertRaisesRegex(turdr.TurdrError, "invalid session"):
            turdr.load_config(self.write('session = "a;b"\n'))

    def test_rejects_nonpositive_interval(self):
        with self.assertRaisesRegex(turdr.TurdrError, "poll_interval"):
            turdr.load_config(self.write("poll_interval = 0\n"))

    def test_nonexistent_file_is_an_error(self):
        with self.assertRaisesRegex(turdr.TurdrError, "not found"):
            turdr.load_config("/nonexistent/turdr.toml")


class RosterTests(unittest.TestCase):
    def test_merges_config_and_defaults(self):
        cfg = base_cfg(agents={"a1": {"command": "custom {agent}", "dir": "/x"}})
        with mock.patch.object(turdr, "gary", return_value=[
                {"name": "a1", "description": "d"}, {"name": "a2"}]):
            agents = turdr.roster(cfg)
        self.assertEqual(agents[0]["command"], "custom {agent}")
        self.assertEqual(agents[0]["dir"], "/x")
        self.assertEqual(agents[1]["command"], cfg["default_command"])

    def test_skip_unlisted(self):
        cfg = base_cfg(skip_unlisted=True, agents={"a1": {}})
        with mock.patch.object(turdr, "gary", return_value=[
                {"name": "a1"}, {"name": "a2"}]):
            agents = turdr.roster(cfg)
        self.assertEqual([a["name"] for a in agents], ["a1"])

    def test_unsafe_names_are_skipped(self):
        cfg = base_cfg()
        with mock.patch.object(turdr, "gary", return_value=[
                {"name": "ok"}, {"name": "bad;rm -rf"}, {"name": ""}]):
            agents = turdr.roster(cfg)
        self.assertEqual([a["name"] for a in agents], ["ok"])


class StatusTests(unittest.TestCase):
    def agent(self, **kw):
        return {"name": "a1", "description": "", "command": "x",
                "dir": None, "state_file": None, **kw}

    def test_idle_and_pending_from_inbox(self):
        cfg = base_cfg()
        with mock.patch.object(turdr, "gary", return_value=[]):
            self.assertEqual(turdr.agent_status(cfg, self.agent()), ("idle", 0))
        with mock.patch.object(turdr, "gary", return_value=[{"id": 1}, {"id": 2}]):
            self.assertEqual(turdr.agent_status(cfg, self.agent()), ("pending", 2))

    def test_state_file_working_then_stuck(self):
        cfg = base_cfg(stuck_after=60)
        with tempfile.TemporaryDirectory() as tmp:
            marker = os.path.join(tmp, "a1.busy")
            open(marker, "w").close()
            agent = self.agent(state_file=os.path.join(tmp, "{agent}.busy"))
            with mock.patch.object(turdr, "gary", return_value=[{"id": 1}]):
                self.assertEqual(turdr.agent_status(cfg, agent), ("working", 1))
                past = time.time() - 3600
                os.utime(marker, (past, past))
                self.assertEqual(turdr.agent_status(cfg, agent), ("stuck", 1))
                os.unlink(marker)  # marker gone -> back to inbox-derived state
                self.assertEqual(turdr.agent_status(cfg, agent), ("pending", 1))

    def test_effective_status_overlays_pane_death(self):
        self.assertEqual(turdr.effective_status("working", None), "exited")
        self.assertEqual(
            turdr.effective_status("idle", {"dead": True}), "exited")
        self.assertEqual(
            turdr.effective_status("pending", {"dead": False}), "pending")


class CommandConstructionTests(unittest.TestCase):
    def test_launch_command_substitutes_and_quotes(self):
        agent = {"name": "a.b-c@1", "command": "run {agent} --x", "dir": None,
                 "state_file": None}
        self.assertEqual(turdr.launch_command(base_cfg(), agent),
                         "run a.b-c@1 --x")

    def test_scan_session_parses_tagged_panes(self):
        outputs = [
            completed("@1\tmain\tturdr\n@2\t\talpha\n@3\t\tname\twith\ttabs\n"),
            completed("%0\t@1\t0\tsidebar\t\n"
                      "%1\t@1\t0\t\talpha\n"
                      "%2\t@2\t1\t\tbeta\n"
                      "%3\t@3\t0\tplaceholder\t\n"),
        ]
        with mock.patch.object(turdr, "run_process", side_effect=outputs):
            scan = turdr.scan_session("gary")
        self.assertEqual(scan["main_window"], "@1")
        self.assertEqual(scan["sidebar"]["id"], "%0")
        self.assertEqual(scan["shown"]["agent"], "alpha")
        self.assertTrue(scan["agent_panes"]["beta"]["dead"])
        self.assertEqual(scan["placeholder"]["id"], "%3")
        self.assertEqual(scan["windows"]["@3"]["name"], "name\twith\ttabs")

    def test_scan_session_missing_session(self):
        with mock.patch.object(turdr, "run_process",
                               return_value=completed(returncode=1)):
            self.assertIsNone(turdr.scan_session("gone"))


@unittest.skipUnless(HAVE_GARY, "gary not on PATH")
class CliIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="turdr-test-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.db = os.path.join(self.tmp, "gary.db")
        self.gary("register", "alpha", "--description", "worker")
        self.gary("register", "beta")
        self.gary("send", "alpha", "--from", "beta", "hi")
        self.state = os.path.join(self.tmp, "beta.busy")
        open(self.state, "w").close()
        self.cfg = os.path.join(self.tmp, "turdr.toml")
        with open(self.cfg, "w") as f:
            f.write(f'''
session = "turdr-test-{os.getpid()}"
db = "{self.db}"
stuck_after = 60
sender = "operator"
[agents.beta]
command = "echo {{agent}}"
state_file = "{self.tmp}/{{agent}}.busy"
''')

    def gary(self, *args):
        proc = subprocess.run(["gary", *args, "--db", self.db],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def turdr(self, *args, expect=0, stdin=None):
        proc = subprocess.run([TURDR, *args], capture_output=True, text=True,
                              input=stdin)
        self.assertEqual(proc.returncode, expect,
                         f"stdout={proc.stdout!r} stderr={proc.stderr!r}")
        return proc

    def test_status_json(self):
        out = json.loads(self.turdr("status", "--json", "-c", self.cfg).stdout)
        agents = {a["name"]: a for a in out["agents"]}
        self.assertEqual(agents["alpha"]["status"], "pending")
        self.assertEqual(agents["alpha"]["pending"], 1)
        self.assertEqual(agents["alpha"]["command"], "gary watch alpha")
        self.assertEqual(agents["beta"]["status"], "working")
        self.assertEqual(agents["beta"]["command"], "echo beta")
        self.assertTrue(all(a["would_create_pane"] for a in out["agents"]))

    def test_status_human_and_stuck(self):
        past = time.time() - 3600
        os.utime(self.state, (past, past))
        out = self.turdr("status", "-c", self.cfg).stdout
        self.assertIn("stuck", out)
        self.assertIn("pending=1", out)

    def test_send_argv_and_stdin(self):
        self.turdr("send", "beta", "do", "the", "thing", "-c", self.cfg)
        self.turdr("send", "beta", "-c", self.cfg, stdin="-starts with dash\n")
        inbox = json.loads(self.gary("inbox", "beta", "--json"))
        bodies = [m["body"] for m in inbox]
        self.assertIn("do the thing", bodies)
        self.assertIn("-starts with dash", bodies)
        self.assertTrue(all(m["from"] == "operator" for m in inbox))

    def test_send_empty_message_refused(self):
        proc = self.turdr("send", "beta", "-c", self.cfg, stdin="  \n", expect=1)
        self.assertIn("empty message", proc.stderr)

    def test_bad_config_fails_loudly(self):
        bad = os.path.join(self.tmp, "bad.toml")
        with open(bad, "w") as f:
            f.write('[agents."no spaces"]\ncommand = "x"\n')
        proc = self.turdr("status", "-c", bad, expect=1)
        self.assertIn("bad agent name", proc.stderr)

    def test_version(self):
        out = self.turdr("version").stdout
        self.assertIn(turdr.__version__, out)


@unittest.skipUnless(HAVE_GARY and HAVE_TMUX, "gary and tmux required")
class TmuxEndToEndTests(unittest.TestCase):
    """Full bootstrap on an isolated tmux socket via a PATH shim, so the
    developer's real tmux server is never touched."""

    SOCKET = f"turdr-selftest-{os.getpid()}"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="turdr-e2e-")
        self.addCleanup(shutil.rmtree, self.tmp)
        shim_dir = os.path.join(self.tmp, "bin")
        os.makedirs(shim_dir)
        shim = os.path.join(shim_dir, "tmux")
        real_tmux = shutil.which("tmux")
        with open(shim, "w") as f:
            f.write(f'#!/bin/sh\nexec {real_tmux} -L {self.SOCKET} "$@"\n')
        os.chmod(shim, os.stat(shim).st_mode | stat.S_IEXEC)
        self.env = dict(os.environ, PATH=f"{shim_dir}:{os.environ['PATH']}")
        self.env.pop("TMUX", None)
        self.addCleanup(self.tmux, "kill-server", check=False)

        self.db = os.path.join(self.tmp, "gary.db")
        for name in ("alpha", "beta"):
            subprocess.run(["gary", "register", name, "--db", self.db],
                           capture_output=True, check=True)
        self.cfg = os.path.join(self.tmp, "turdr.toml")
        with open(self.cfg, "w") as f:
            f.write(f'''
session = "gary"
db = "{self.db}"
poll_interval = 1
default_command = "gary watch {{agent}} --db {self.db}"
''')

    def tmux(self, *args, check=True):
        proc = subprocess.run(["tmux", *args], capture_output=True, text=True,
                              env=self.env)
        if check:
            self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc

    def run_turdr(self):
        # The final `tmux attach` fails (no tty here); everything before it
        # must already have set the session up.
        return subprocess.run([TURDR, "run", "-c", self.cfg],
                              capture_output=True, text=True, env=self.env)

    def panes(self):
        out = self.tmux("list-panes", "-s", "-t", "gary", "-F",
                        "#{pane_id}\t#{window_id}\t#{@turdr_role}\t"
                        "#{@turdr_agent}").stdout
        return [line.split("\t") for line in out.splitlines()]

    def wait_for(self, predicate, message, timeout=8):
        deadline = time.time() + timeout
        while time.time() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(0.3)
        self.fail(message)

    def test_bootstrap_select_and_idempotency(self):
        self.run_turdr()
        roles = {p[2] for p in self.panes()}
        self.assertIn("sidebar", roles)
        self.assertIn("placeholder", roles)

        # Agent panes are created by the sidebar's poller (single writer).
        def all_windows():
            windows = self.tmux("list-windows", "-t", "gary",
                                "-F", "#{window_name}").stdout.split()
            return sorted(windows) == ["alpha", "beta", "turdr"] and windows
        self.wait_for(all_windows, "agent windows never appeared")
        agents = {p[3] for p in self.panes()}
        self.assertLessEqual({"alpha", "beta"}, agents)

        before = sorted(p[0] for p in self.panes())
        self.run_turdr()  # idempotent: same panes, no duplicates
        self.assertEqual(sorted(p[0] for p in self.panes()), before)

        # Select an agent in the sidebar: its live pane swaps into the main
        # window and the placeholder is retired.
        sidebar = next(p for p in self.panes() if p[2] == "sidebar")
        time.sleep(2)  # let the sidebar's first poll land
        self.tmux("send-keys", "-t", sidebar[0], "Down", "Enter")
        deadline = time.time() + 5
        while time.time() < deadline:
            panes = self.panes()
            shown = [p for p in panes
                     if p[1] == sidebar[1] and p[3] in ("alpha", "beta")]
            if shown and not any(p[2] == "placeholder" for p in panes):
                break
            time.sleep(0.3)
        else:
            self.fail(f"agent pane never swapped into main window: {panes}")

        before = sorted(p[0] for p in self.panes())
        self.run_turdr()  # still idempotent after a selection
        self.assertEqual(sorted(p[0] for p in self.panes()), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
