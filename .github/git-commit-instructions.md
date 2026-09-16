# Git guidelines
## Writing git commit messages
- The first line should start with the task identifier (see Prefixes) and be followed by a capitalized imperative verb (e.g., Fix, Add, Refactor, ...)
- A git commit message should start with a short description (max 72 chars, following the git best practices), and should not end with a dot.
- Then should follow an empty line
- After that there should be a longer description of the commit:
- Do not repeat comments from the code
- Instead explain the intent and reason for this commit
- Never include `Co-authored-by:` trailers — the `commit-msg` hook rejects them
- Release commits are the one exception to the body rule: they have no body (see the [git-commit skill](skills/git-commit/SKILL.md))

## Prefixes
Every commit message should be prefixed by the board subtask identifier that this commit belongs to:

HS-XXX

## Atomicity of git commits
To facilitate reviewing, reverting and future understanding of changes, each commit of a PR should satisfy these requirements:

- The system should work
- The tests should pass
- The code should lint
- The amount of modifications should be limited: one commit for one purpose

These requirements imply:

That a PR should not contain a commit fixing another commit of the same PR.

It is usually better to have both the test and the changes being tested in the same commit because:

- The tests limit the risk of introducing broken code that we later have to fix;
- Reverting the commit introducing the change automatically reverts the test as well;
- The tests help understand the purpose of the commit;
