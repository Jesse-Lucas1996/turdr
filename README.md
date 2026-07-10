# turdr

A status-aware tmux controller for [Gary](https://github.com/Jesse-Lucas1996/gary)-managed
agent fleets — herdr's UX without reimplementing tmux. Every agent owns a whole tmux
window: an interactive terminal session in the agent's working directory, running the
agent CLI you configure (or a plain shell where you start the agent yourself). A slim
sidebar lists the fleet with live status dots and *hops* into whichever agent's window
you select — you talk to an agent by typing into its session, like any terminal.

Gary is **cross-agent communication only**: it supplies the roster (`gary list`) and the
pending/idle signal (`gary inbox`, peek-only); turdr never runs your agents through it.

Single Python-stdlib script. Requires Python ≥ 3.11, tmux ≥ 3.0, and `gary` on PATH.
turdr only ever shells out to `gary` and `tmux` (argument arrays, no sqlite access of
its own).

```
window "api" (selected)               window "cases" (another agent)
+--------+-------------------------+  +--------------------------+
|▸○ api  |  agent session — its    |  |  cases' session, still   |
| ● cases|  repo & CLI; type here  |  |  running untouched       |
| ○ edge |  to steer the agent     |  +--------------------------+
| ...    +-------------------------+
|        |  extra shell pane (t)   |
+--------+-------------------------+
```

Agent windows are normal tmux windows — split them however you like; turdr only tracks
the tagged agent pane and never rearranges your splits. The sidebar is a gutter: at most
`sidebar_width` columns (default 24), never more than a third of the window, holding its
size across resizes; rows adapt to whatever width remains (the dot color always carries
the status).

Selecting an agent **swaps** its live pane into the main window — the agent's process is
never restarted by selection. Hidden agents keep running in parking windows (also
reachable with plain tmux: `prefix + n/p/0-9`).

## Usage

```sh
turdr                        # launch/attach; ./turdr.toml if present, else defaults
turdr run -c fleet.toml      # explicit config ("run" is the default command)
turdr --db ~/team/gary.db    # point at any Gary db, zero per-agent config
turdr status [--json]        # read-only roster + status report; mutates nothing
turdr send <agent> [words…]  # gary send (body from args or stdin)
turdr update                 # self-update: pull latest from GitHub, reinstall
turdr version
```

Sidebar keys: `↑/↓` (or `j/k`) move · `Enter` show agent (Enter again moves your
keyboard into its session) · `Tab`/`→` show **and** focus · `t` open/focus a shell pane
inside the selected agent's window, in its directory · `m` send a Gary message to the
selected agent (cross-comms, same channel agents use with each other) · `r` poll now ·
`q` quit (agents keep running; rerun `turdr` to get the sidebar back). Mouse: click an
agent to show it; click a pane to focus it (turdr turns `mouse on` for its own session
only — set `mouse = false` to opt out). Get back to the sidebar with `prefix + ←` or by
clicking it.

## Config

TOML, everything optional (see `turdr.example.toml`). Precedence: CLI flags > config
file > built-in defaults.

```toml
session = "gary"                        # tmux session turdr owns
db = "~/team/gary.db"                   # passed to gary as --db; omit for gary's default
poll_interval = 3                       # seconds between polls (gary watch cadence)
default_command = "claude"              # launch template for agents not listed below;
                                        # {agent} -> name, {db} -> "--db <path>" when
                                        # db is set. Built-in default: a banner + an
                                        # interactive shell in the agent's dir, so you
                                        # can start the agent yourself.
default_dir = "~"
skip_unlisted = false                   # true -> ignore Gary agents with no entry below
stuck_after = 120                       # state file older than this (s) -> stuck
sidebar_width = 24                      # max columns; also capped at 1/3 of window
mouse = true
sender = "turdr"                        # --from identity for send/composer (excluded
                                        # from the managed roster)
auto_respawn = false                    # respawn exited agents, bounded with backoff

[agents.builder]
command = "./agent-loop.sh {agent}"     # {agent} -> agent name (quoted for you; don't
dir = "~/Work/myproject"                #   add your own quotes around it)
state_file = "/tmp/agents/{agent}.busy" # optional; enables working/stuck states
```

## Status dots

Polled every `poll_interval` seconds via `gary inbox <name> --json` (peek only — never
dequeues) plus one tmux pane scan; per-agent inbox checks run concurrently.

| dot | status | meaning |
|-----|--------|---------|
| ○ white | `idle` | inbox empty |
| ● yellow | `pending` | inbox has messages waiting (count shown) |
| ● green | `working` | agent's `state_file` exists |
| ● red | `stuck` | `state_file` exists but is older than `stuck_after` |
| ✗ magenta | `exited` | the agent's pane process has died (last output stays visible) |

`working`/`stuck` exist only for agents whose config sets `state_file` — the convention
is that the launch command touches that file while processing a message and removes it
when done. Without one, turdr shows only `idle`/`pending`/`exited`; it never fabricates
a state it can't observe.

Exited agents: `Enter` respawns the pane in place (same window, output history intact).
With `auto_respawn = true`, turdr respawns automatically with exponential backoff, giving
up after 5 attempts (so a broken launch command can't crash-loop); `Enter` resets the
counter.

## How windows/panes are created and reused

- Roster = Gary's registry (`gary list`), minus the `sender` identity, minus unsafe
  names, minus unlisted agents when `skip_unlisted = true`. Config entries for agents
  not registered in Gary are ignored.
- Every turdr-owned pane is tagged with tmux user options (`@turdr_agent`,
  `@turdr_role`), so a restarted turdr rediscovers everything — no state file.
- Only the sidebar's poller creates agent windows (single writer — two cooperating
  creators would race and duplicate windows). New Gary registrations get a window
  within one poll, created detached without stealing focus.
- Selecting an agent moves the sidebar pane into that agent's window (`join-pane` — the
  sidebar process survives the move) and switches there. Nothing about the agent's
  window is restarted or rearranged by selection.
- Single-pane windows named after a roster agent (e.g. from an older turdr) are adopted
  by tagging, not duplicated. Multi-pane or unrelated windows are never touched, and
  turdr never kills anything it didn't create.
- Re-running `turdr` is idempotent: session, sidebar, and windows are reused. Quitting
  the sidebar leaves all agents running.

## Install / update

```sh
git clone https://github.com/Jesse-Lucas1996/turdr && cd turdr
./turdr update        # installs to ~/.local/bin/turdr (and pulls latest)
```

`turdr update` treats git as the source of truth: if the running script lives in a git
checkout it pulls that (`--ff-only`); otherwise it maintains a clone under
`~/.local/share/turdr`. Either way the result is installed to `~/.local/bin/turdr`.
Override the origin with `TURDR_REPO=<url>`.

## Tests

```sh
python3 test_turdr.py
```

Unit tests stub the process boundary (no gary/tmux needed); CLI tests run against a
temp Gary db; the end-to-end test bootstraps a real session on an isolated tmux socket
— your own tmux server and sessions are never touched.
