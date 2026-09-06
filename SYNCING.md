# Keeping this folder in sync with GitHub

This folder **is** the Git repository. Edit files here, push, and
github.com/KK4ODA/emcomm-bbs matches.

## Day to day

| You want to... | Do this |
|---|---|
| Send your changes to GitHub | Double-click **`PUSH-TO-GITHUB.bat`** |
| Get changes made on GitHub | Double-click **`PULL-FROM-GITHUB.bat`** |
| See what changed | Open a terminal in this folder and run `git status` |

`PUSH-TO-GITHUB.bat` asks for a one-line description of what you changed. Press
Enter to accept a dated default. The first push may open a browser window to
sign in to GitHub; approve it once and Git remembers the login.

## Working from a terminal

```
git status                 # what changed
git add -A                 # stage everything
git commit -m "message"    # record it
git push                   # send to GitHub
git pull --rebase          # fetch changes made elsewhere
```

## What never gets uploaded

`.gitignore` blocks these on purpose:

- `emcomm_bbs_config.json` — **your API keys**
- `data/` — incoming, archived, and errored check-in files
- `welfare_board.html`, `welfare_*.csv` and generated bulletins
- `__pycache__/`, logs, editor and OS junk, Dropbox conflict copies

If you add a new file that should stay private, add its name to `.gitignore`
before pushing.

## A note about Dropbox

If this folder lives inside Dropbox, both Dropbox and Git watch it. That
works, but if Dropbox ever creates a "conflicted copy" of a file inside
`.git`, Git can get confused. The fix is a fresh clone:

```
git clone https://github.com/KK4ODA/emcomm-bbs.git
```

GitHub holds the authoritative copy, so nothing pushed is ever lost.
