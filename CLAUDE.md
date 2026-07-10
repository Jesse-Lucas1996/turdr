# CLAUDE.md

## Purpose

This file defines the engineering standards, working conventions, and safety requirements that must be followed when making changes in this repository.

Prioritize correctness, clarity, safety, maintainability, and predictable terminal behavior over cleverness or unnecessary abstraction.

## Core Principles

1. Make the smallest change that fully solves the problem.
2. Preserve existing behavior unless a change is explicitly required.
3. Prefer readable, explicit code over compressed or clever code.
4. Treat all user-provided values as untrusted input.
5. Avoid hidden side effects.
6. Keep terminal interactions deterministic and easy to debug.
7. Fail clearly, early, and safely.
8. Do not silently ignore errors.
9. Do not introduce new dependencies unless they provide clear value.
10. Keep platform assumptions explicit.

## Before Making Changes

Before editing code:

- Read the relevant files completely.
- Identify existing conventions and follow them.
- Check for nearby tests, fixtures, and helper functions.
- Understand the current command execution path.
- Verify how errors are surfaced to users.
- Check whether behavior differs between interactive and non-interactive environments.
- Search for existing implementations before creating new abstractions.
- Confirm whether commands depend on shell configuration, environment variables, or external binaries.

Do not rewrite unrelated code while implementing a focused change.

## Change Planning

For non-trivial work, define:

- The intended behavior.
- The files likely to change.
- Failure modes.
- Backward-compatibility concerns.
- Validation and testing steps.
- Any assumptions about the operating system, shell, terminal, or installed tools.

Prefer incremental changes that can be tested independently.

## Code Quality

### General Style

- Use descriptive names.
- Keep functions focused on one responsibility.
- Avoid deeply nested conditionals.
- Extract repeated logic only when the abstraction is genuinely reusable.
- Prefer early returns for validation and error handling.
- Add comments only when they explain intent, constraints, or non-obvious behavior.
- Do not add comments that merely restate the code.
- Remove dead code rather than commenting it out.
- Keep public interfaces narrow.
- Avoid mutable global state.

### Function Design

Functions should:

- Have a clear purpose.
- Accept explicit inputs.
- Return predictable outputs.
- Avoid modifying unrelated state.
- Be independently testable where practical.
- Separate command construction from command execution.
- Separate validation from side effects.
- Separate user-facing formatting from core logic.

### Error Handling

- Return or raise actionable errors.
- Include enough context to identify the failed operation.
- Preserve the underlying error when wrapping it.
- Distinguish invalid input from runtime failure.
- Distinguish missing dependencies from command failure.
- Avoid exposing sensitive environment values in error messages.
- Do not convert failures into successful exit codes.
- Do not catch broad errors unless they are re-raised or handled meaningfully.

Good error messages should state:

- What failed.
- Why it likely failed.
- What the user can do next.

## Command Execution

Command execution is a security-sensitive boundary.

### Required Practices

- Prefer argument arrays over shell-interpolated strings.
- Avoid invoking a shell unless shell features are strictly required.
- Never concatenate untrusted input into a command string.
- Validate command arguments before execution.
- Capture stdout and stderr separately when useful.
- Check exit codes.
- Propagate failures with useful context.
- Use timeouts where a command could hang indefinitely.
- Avoid inheriting unnecessary environment variables.
- Keep command construction deterministic.
- Log or expose a safe representation of failed commands for debugging.
- Never log secrets, tokens, credentials, or sensitive environment values.

### Shell Invocation

Do not use patterns equivalent to:

```sh
sh -c "$USER_INPUT"
```

or:

```sh
eval "$COMMAND"
```

Avoid `eval` entirely.

When a shell is unavoidable:

- Use a fixed command template.
- Pass dynamic values as positional parameters.
- Quote every variable correctly.
- Document why direct process execution is insufficient.
- Add tests for spaces, quotes, Unicode, punctuation, and shell metacharacters.

### Quoting and Escaping

Do not assume that escaping for one context is safe in another.

Treat these as separate contexts:

- Process arguments.
- Shell strings.
- Configuration syntax.
- Terminal commands.
- Format strings.
- Regular expressions.
- File paths.

Use context-specific escaping rather than a single generic escape helper.

## Terminal and Session Safety

Terminal tooling must behave predictably across interactive environments.

### General Requirements

- Do not assume a terminal is attached.
- Detect interactive and non-interactive execution where relevant.
- Avoid commands that block waiting for input unless explicitly intended.
- Do not unexpectedly attach, switch, or replace the user’s current terminal state.
- Make destructive or disruptive actions explicit.
- Preserve user state whenever possible.
- Avoid relying on timing-based behavior.
- Avoid parsing human-readable command output when a structured format is available.
- Verify external state before mutating it.
- Handle race conditions between existence checks and creation operations.

### Naming

Names used for sessions, windows, panes, sockets, resources, or identifiers must be validated.

Validation should consider:

- Empty values.
- Leading or trailing whitespace.
- Control characters.
- Newlines.
- Tabs.
- Shell metacharacters.
- Delimiters used by external commands.
- Duplicate names.
- Length limits.
- Unicode behavior.
- Case sensitivity.
- Reserved values.

Do not silently rewrite user input unless the normalization rule is documented and predictable.

When normalization is required:

- Keep it minimal.
- Make collisions detectable.
- Preserve the original value for user-facing output where appropriate.

### Idempotency

Operations should be idempotent where practical.

Running the same command repeatedly should:

- Produce the same result.
- Reuse existing state when appropriate.
- Avoid duplicate resources.
- Avoid accumulating stale state.
- Clearly report whether something was created, reused, replaced, or skipped.

If an operation is intentionally non-idempotent, document that behavior and test it.

### Existing State

Always handle pre-existing state deliberately.

Define behavior for:

- Resource already exists.
- Resource partially exists.
- Resource is stale.
- Resource is inaccessible.
- Resource belongs to another process.
- Resource was removed between inspection and mutation.
- Multiple processes attempt creation concurrently.

Do not assume that “not found” and “not accessible” are equivalent.

## External Dependencies

For every external binary or runtime dependency:

- Check availability before relying on it.
- Provide a clear error when it is missing.
- Avoid version-specific flags unless compatibility is verified.
- Keep minimum supported versions documented in the repository.
- Prefer capability detection over version parsing where practical.
- Do not assume shell aliases or functions are available.
- Do not depend on interactive shell startup files.
- Do not assume a specific `PATH` layout.
- Avoid environment-specific absolute paths.

When invoking a dependency:

- Use the binary directly.
- Avoid relying on aliases.
- Avoid parsing localized output.
- Prefer stable machine-readable output.
- Treat warnings on stderr separately from fatal failures when necessary.

## Configuration

Configuration should be explicit and validated.

### Configuration Rules

- Define precedence clearly.
- Keep defaults safe.
- Reject invalid values with actionable messages.
- Avoid surprising implicit behavior.
- Do not silently ignore unknown fields unless forward compatibility requires it.
- Validate configuration before performing side effects.
- Keep configuration parsing separate from execution.
- Avoid embedding machine-specific paths in committed files.
- Support environment variables only where they provide clear value.
- Document environment-variable precedence.
- Do not store secrets in repository configuration.

A typical precedence model is:

1. Explicit command-line arguments.
2. Environment variables.
3. Local configuration.
4. User configuration.
5. Built-in defaults.

Use the repository’s existing precedence rules if they differ.

## Filesystem Safety

- Use platform-appropriate path handling.
- Do not build paths using string concatenation.
- Normalize paths only when necessary.
- Be careful with symlinks.
- Avoid overwriting files without explicit intent.
- Use atomic writes for important state.
- Write temporary files to an appropriate temporary directory.
- Clean up temporary files on success and failure.
- Set restrictive permissions for sensitive files.
- Do not assume the current working directory.
- Clearly distinguish repository-relative, user-relative, and absolute paths.
- Handle spaces and Unicode in paths.
- Avoid recursive deletion unless the target has been strongly validated.

Before deleting or replacing a path:

- Confirm the path is non-empty.
- Confirm it resolves to the intended location.
- Confirm it is within an expected parent directory.
- Reject root directories and ambiguous targets.
- Avoid following untrusted symlinks.

## Concurrency and Race Conditions

Assume multiple instances may run at the same time.

Where shared state exists:

- Use atomic operations.
- Avoid check-then-create logic without handling races.
- Use locking only where necessary.
- Keep lock scope small.
- Make stale-lock recovery explicit.
- Ensure locks are released after failures.
- Do not use arbitrary sleeps as synchronization.
- Test concurrent creation and duplicate requests where practical.

## Logging and User Output

### User-Facing Output

Output should be:

- Concise.
- Actionable.
- Consistent.
- Suitable for terminal use.
- Stable enough for users to understand.
- Separate from machine-readable output.

Do not print internal stack traces by default.

Use stderr for errors and diagnostics.

Use stdout for successful command output or requested data.

### Machine-Readable Output

When structured output is supported:

- Keep the schema stable.
- Avoid mixing logs with structured output.
- Use deterministic field names.
- Represent errors consistently.
- Avoid color codes.
- Avoid terminal control sequences.
- Include explicit status fields where useful.

### Color and Formatting

- Respect `NO_COLOR` where applicable.
- Disable color when output is not connected to a terminal.
- Do not rely on color alone to communicate meaning.
- Avoid terminal escape sequences in redirected output.
- Keep formatting usable in narrow terminal widths.

## Exit Codes

Use exit codes consistently.

Recommended categories:

- `0`: Success.
- Non-zero: Failure.

Where multiple exit codes are used, distinguish categories such as:

- Invalid arguments.
- Invalid configuration.
- Missing dependency.
- Resource conflict.
- External command failure.
- Filesystem failure.
- Unexpected internal error.

Do not change established exit-code behavior without a compatibility reason.

## Signals and Cleanup

Long-running or stateful operations must handle interruption safely.

Consider:

- `SIGINT`.
- `SIGTERM`.
- Parent process termination.
- Broken pipes.
- Partial command execution.

Cleanup should:

- Avoid deleting resources created by another process.
- Remove temporary state owned by the current process.
- Leave persistent state valid.
- Avoid masking the original error.
- Be safe to run more than once.

## Testing Requirements

Every behavior change should include tests where practical.

### Unit Tests

Unit tests should cover:

- Input validation.
- Name normalization.
- Command construction.
- Configuration precedence.
- Error conversion.
- Output formatting.
- Existing-state handling.
- Boundary cases.
- Paths containing spaces.
- Unicode input.
- Quotes and punctuation.
- Empty values.
- Duplicate requests.

Mock process execution at the boundary rather than mocking internal implementation details.

### Integration Tests

Integration tests should verify:

- Real command invocation.
- Successful creation.
- Existing-resource behavior.
- Failure propagation.
- Cleanup.
- Non-interactive execution.
- Concurrent requests where relevant.
- Missing dependency behavior.
- Compatibility with supported dependency versions.

Integration tests must:

- Use isolated state.
- Avoid modifying the developer’s active terminal environment.
- Avoid relying on existing user configuration.
- Clean up created resources.
- Use unique generated names.
- Be safe to rerun.

### Regression Tests

When fixing a bug:

1. Add a test that reproduces the failure.
2. Confirm the test fails before the fix.
3. Implement the smallest correct fix.
4. Confirm the new test passes.
5. Run the broader test suite.

### Test Quality

Tests should:

- Assert observable behavior.
- Avoid arbitrary sleeps.
- Avoid depending on test order.
- Avoid shared mutable state.
- Use descriptive test names.
- Include failure messages where assertions may be unclear.
- Be deterministic.
- Keep fixtures minimal.

## Security

Treat terminal automation as security-sensitive.

### Input Security

Validate all input crossing a trust boundary, including:

- Command-line arguments.
- Environment variables.
- Configuration files.
- File names.
- Directory paths.
- Session identifiers.
- External command output.
- Data read from standard input.

### Injection Prevention

Protect against:

- Shell injection.
- Argument injection.
- Option injection.
- Path traversal.
- Format-string injection.
- Configuration injection.
- Terminal escape-sequence injection.

When user-controlled values may begin with `-`, use an end-of-options marker such as `--` when the external command supports it.

Do not assume that passing arguments without a shell prevents all injection risks. Some commands interpret argument values as options, expressions, formats, or embedded command languages.

### Sensitive Data

Never expose:

- Tokens.
- Credentials.
- Private keys.
- Session secrets.
- Full environment dumps.
- Sensitive paths unless necessary.
- Contents of unrelated configuration files.

Redact sensitive values in logs and error reports.

## Compatibility

Maintain compatibility with supported:

- Operating systems.
- Shells.
- Terminal environments.
- External dependency versions.
- Configuration formats.
- Public command interfaces.
- Output formats.
- Exit codes.

Do not assume GNU-specific behavior when portability is expected.

When platform behavior differs:

- Isolate platform-specific code.
- Document the difference.
- Add targeted tests.
- Fail clearly on unsupported platforms.

## Documentation

Update documentation when changing:

- Command behavior.
- Flags.
- Configuration.
- Defaults.
- Environment variables.
- Output.
- Exit codes.
- Dependencies.
- Compatibility.
- Error behavior.

Documentation examples must:

- Be runnable.
- Use safe placeholder values.
- Avoid machine-specific paths.
- Match current behavior.
- Show quoting where needed.
- Avoid implying unsupported behavior.

## Dependency Management

Before adding a dependency:

- Confirm the standard library or existing dependencies cannot solve the problem cleanly.
- Evaluate maintenance status.
- Evaluate security implications.
- Check license compatibility.
- Consider binary size and startup cost.
- Consider cross-platform support.
- Prefer small, focused dependencies.
- Pin versions according to repository conventions.

Remove unused dependencies after refactoring.

Do not update unrelated dependencies in a focused change.

## Performance

Optimize only when there is evidence or a clear operational need.

Pay particular attention to:

- Process startup count.
- Repeated external command calls.
- Repeated state queries.
- Blocking I/O.
- Unbounded retries.
- Unbounded output capture.
- Polling loops.
- Large configuration files.
- Startup latency.

Prefer one structured query over multiple human-readable queries when supported.

Do not cache external state without a clear invalidation strategy.

## Retries and Timeouts

Retries must be intentional.

- Retry only transient failures.
- Use bounded retry counts.
- Use backoff where appropriate.
- Do not retry validation errors.
- Do not retry deterministic command failures.
- Preserve the final error context.
- Avoid duplicate side effects.
- Use timeouts for operations that may hang.
- Make timeout behavior configurable only when users genuinely need control.

## Backward Compatibility

Before changing existing behavior, consider:

- Existing scripts.
- Aliases.
- Configuration files.
- Automation.
- CI environments.
- Machine-readable consumers.
- Exit-code checks.
- Users relying on current naming behavior.

Prefer additive changes.

For breaking changes:

- Make the break explicit.
- Provide a migration path.
- Update tests and documentation.
- Avoid combining the breaking change with unrelated refactoring.

## Refactoring

Refactor only when it improves the current change or removes meaningful risk.

Good refactoring goals include:

- Isolating process execution.
- Separating validation from side effects.
- Reducing duplicated command construction.
- Improving testability.
- Replacing unsafe shell interpolation.
- Clarifying error handling.

Avoid broad aesthetic refactoring during bug fixes.

Keep behavior-preserving refactors separate from behavior changes where possible.

## Review Checklist

Before considering work complete, verify:

- The change solves the requested behavior.
- Existing behavior remains intact where required.
- Inputs are validated.
- Shell interpolation is avoided.
- Arguments are passed safely.
- Errors are actionable.
- Exit codes remain correct.
- Existing-state behavior is defined.
- Non-interactive behavior is safe.
- Temporary resources are cleaned up.
- Tests cover success and failure paths.
- Tests do not affect active user state.
- Formatting and lint checks pass.
- Documentation is updated where needed.
- No secrets or machine-specific values were introduced.
- No unrelated files were changed.
- The diff is as small as reasonably possible.

## Commands

Use the repository’s existing commands for:

- Formatting.
- Linting.
- Type checking.
- Unit tests.
- Integration tests.
- Building.
- Packaging.

Do not invent replacement commands when established scripts already exist.

Before finishing, run the most relevant checks available in the repository. At minimum, run focused tests for the changed code. Run the full suite when the scope or risk justifies it.

## Working Agreement

When modifying this repository:

- Inspect before editing.
- Reuse existing patterns.
- Explain assumptions in code only when they are non-obvious.
- Avoid speculative features.
- Avoid unrelated cleanup.
- Preserve user state.
- Prefer safe failure over partial mutation.
- Add tests for behavior changes.
- Keep the final diff focused and reviewable.
