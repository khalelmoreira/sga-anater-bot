# Building the Windows .exe

PyInstaller can't cross-compile, so the `.exe` is built on a GitHub Actions
Windows runner (`.github/workflows/build-windows.yml`), triggered from the
devcontainer. The VM only tests the result; it never builds.

The workflow only builds and uploads `SGA-ANATER-Bot.zip`. It runs no tests and
no `--selftest` (the VM does that, see `docs/windows-test.md`).

## Build (devcontainer)

Push the commit to build first (the workflow runs on the ref you give it).

```bash
gh workflow run build-windows.yml --ref main     # or a branch name
gh run watch                                     # pick the run just started
gh run download -n SGA-ANATER-Bot-windows -D dist-win
```

`dist-win/SGA-ANATER-Bot.zip` is the app. Don't commit it (it's ~900 MB
unzipped); hand it to the VM, or download it there with the same
`gh run download` command (`gh run list --workflow build-windows.yml` for the
run id).

## Test (Windows VM)

Unzip, then run from `docs/windows-test.md` step 5 on:

```powershell
SGA-ANATER-Bot\SGA-ANATER-Bot.exe --selftest
```

## If the build fails

`gh run view <id> --log-failed`. Build problems in `packaging/` are
Windows-specific; fix them and re-trigger. Pipeline/fill code problems follow
the normal issue flow in `CLAUDE.md`.

## Notes

- Free for public repos; private repos use the account's monthly Actions minutes.
- Artifacts expire after 90 days (GitHub default).
- The exe is unsigned, so SmartScreen warns on first run.
