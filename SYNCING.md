# Keeping this folder in sync with GitHub

This folder **is** the Git repository. There is no separate copy to maintain —
edit files here, push, and github.com/KK4ODA/emcomm-bbs matches.

## One-time setup

1. Install [Git for Windows](https://git-scm.com/download/win). Accept the
   defaults; the "Git Credential Manager" it installs is what remembers your
   GitHub login.
2. Double-click **`PUSH-TO-GITHUB.bat`**. The first time, a browser window
   opens asking you to authorize GitHub. Approve it once and it is remembered.

## Day to day

| You want to... | Do this |
|---|---|
| Send your changes to GitHub | Double-click **`PUSH-TO-GITHUB.bat`** |
| Get changes made on GitHub | Double-click **`PULL-FROM-GITHUB.bat`** |
| See what changed | Right-click the folder → *Open Git Bash here* → `git status` |

`PUSH-TO-GITHUB.bat` asks for a one-line description of what you changed. Press
Enter to accept a dated default.

## What never gets uploaded

`.gitignore` blocks these, on purpose:

- `emcomm_bbs_config.json` — **your API keys**
- `data/` — incoming, archived, and errored check-in files
- `welfare_board.html`, `welfare_board.csv` and generated bulletins
- `__pycache__/`, logs, editor and OS junk, Dropbox conflict copies

If you add a new file that should stay private, add its name to `.gitignore`
before pushing.

## Working from your development folder instead

If you prefer to keep developing in `Emcomm_BBS\` and copy changes over, copy
only the source files — never `emcomm_bbs_config.json`, `data\`, or
`__pycache__\`:

```
robocopy "..\..\Emcomm_BBS" "." *.py *.txt *.bat *.sh /XF emcomm_bbs_config.json /XD data __pycache__ old "old bat files"
```

Then run `PUSH-TO-GITHUB.bat`. Simpler still: work directly in this folder and
skip the copying.

## A note about Dropbox

This folder lives inside Dropbox, so Dropbox and Git are both watching it. That
works, but if Dropbox ever creates a "conflicted copy" of a file inside `.git`,
Git can get confused. If that happens, the fix is to pull a fresh clone:

```
git clone https://github.com/KK4ODA/emcomm-bbs.git
```

GitHub holds the authoritative copy, so nothing pushed is ever lost.
