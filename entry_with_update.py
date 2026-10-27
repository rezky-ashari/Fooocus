import os
import sys
import subprocess


root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(root)
os.chdir(root)


try:
    import pygit2
    pygit2.option(pygit2.GIT_OPT_SET_OWNER_VALIDATION, 0)

    repo = pygit2.Repository(os.path.abspath(os.path.dirname(__file__)))

    branch_name = repo.head.shorthand

    remote_name = 'origin'
    remote = repo.remotes[remote_name]

    remote.fetch()

    local_branch_ref = f'refs/heads/{branch_name}'
    local_branch = repo.lookup_reference(local_branch_ref)

    remote_reference = f'refs/remotes/{remote_name}/{branch_name}'
    remote_commit = repo.revparse_single(remote_reference)

    merge_result, _ = repo.merge_analysis(remote_commit.id)

    if merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
        print("[Update] Already up-to-date")
    elif merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
        local_branch.set_target(remote_commit.id)
        repo.head.set_target(remote_commit.id)
        repo.checkout_tree(repo.get(remote_commit.id))
        repo.reset(local_branch.target, pygit2.GIT_RESET_HARD)
        print("[Update] Fast-forward merge succeeded.")
    elif merge_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL:
        print("[Update] Skipped - local changes detected.")
except ImportError:
    # pygit2 not installed, fallback to git CLI
    try:
        git_res = subprocess.run(["git", "pull", "--ff-only"], capture_output=True, text=True, check=False)
        if git_res.returncode == 0:
            print("[Update] Git update succeeded via git CLI.")
        else:
            print("[Update] Already up-to-date or local modifications present.")
    except Exception:
        print("[Update] Git check skipped.")
except Exception as e:
    print(f"[Update] Skipped: {e}")

from launch import *
