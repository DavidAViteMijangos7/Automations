# CLAUDE.md

Guidance for Claude Code when working in `automation-toolkit`.

## Repo layout

Monorepo with two independent CLI subprojects:

| Path      | Project     | Stack                          |
| --------- | ----------- | ------------------------------ |
| `python/` | `xlsreport` | Python 3.11+, uv, typer, pytest |
| `cpp/`    | `triage`    | C++20, CMake, GoogleTest        |

Shared at root: `LICENSE`, `.gitignore`, `.pre-commit-config.yaml`, `README.md`,
`.github/workflows/`.

## Scaffolding

All repos start from my templates — never scaffold a project from scratch.
Copy the template in, then rename the placeholders. If something is missing from
a template, fix the template rather than hand-rolling it here.

## Commits

Conventional Commits, enforced by `conventional-pre-commit` at the `commit-msg`
stage. Allowed types:

`feat:` `fix:` `docs:` `test:` `chore:` `ci:`

## README

The root `README.md` has exactly 8 sections, in this order:

1. Pitch
2. Demo
3. Problem
4. Install
5. Usage
6. Architecture
7. Results
8. License

No more, no fewer. If a section has nothing in it, fill it in — don't leave it
empty and don't add sections that aren't on this list.

## License

MIT. One `LICENSE` at the repo root covers both subprojects. Subprojects do not
carry their own `LICENSE` file.

## CI

Two path-filtered workflows at the root, so touching one subproject does not run
the other's jobs:

- `.github/workflows/ci-python.yml` — triggers on `python/**` and its own file.
  All `uv` steps run with `working-directory: python`.
- `.github/workflows/ci-cpp.yml` — triggers on `cpp/**` and its own file.
  Configures with `cmake -B cpp/build -S cpp`; `ctest` runs in `cpp/build`;
  `clang-format` / `clang-tidy` walk `cpp/src`, `cpp/include`, `cpp/tests`.

Every path inside these workflows is relative to the repo root, not the
subproject. When adding a step, prefix it accordingly.

## Git

**Never run git commands.** No `git add`, `commit`, `push`, `checkout`, `merge`,
`rebase`, or `stash`. David commits through GitHub Desktop and reviews every
change there first. Make the file edits and stop.
