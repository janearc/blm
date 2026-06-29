// Package git provides the git-churn watcher Oracle: "does this working tree
// have uncommitted changes?". It is delightd's git oracle lifted into the
// frood watcher shape, so any frood can watch a repo without
// re-implementing it. go-git evaluates the tree in-process -- no shelling out to
// the git binary -- and this dependency is isolated in its own package so a
// frood that only watches a directory does not pull go-git in.
package git

import (
	"context"
	"fmt"

	"github.com/go-git/go-git/v5"

	"github.com/janearc/big-little-mesh/watcher"
)

// ChurnOracle reports working-tree churn for one repository path.
type ChurnOracle struct{ path string }

// NewChurnOracle watches the repository at repoPath for uncommitted changes.
func NewChurnOracle(repoPath string) *ChurnOracle { return &ChurnOracle{path: repoPath} }

// Name implements watcher.Oracle.
func (o *ChurnOracle) Name() string { return "git-churn:" + o.path }

// Poll opens the repo and reports HasWork when the working tree is not clean.
// Errors (not a repo, unreadable worktree) are returned for the loop to log;
// they are not treated as churn.
func (o *ChurnOracle) Poll(ctx context.Context) (watcher.Result, error) {
	r, err := git.PlainOpen(o.path)
	if err != nil {
		if err == git.ErrRepositoryNotExists {
			return watcher.Result{}, fmt.Errorf("not a git repository: %s", o.path)
		}
		return watcher.Result{}, fmt.Errorf("open repo: %w", err)
	}
	w, err := r.Worktree()
	if err != nil {
		return watcher.Result{}, fmt.Errorf("worktree: %w", err)
	}
	status, err := w.Status()
	if err != nil {
		return watcher.Result{}, fmt.Errorf("status: %w", err)
	}
	// IsClean() is false when there are staged or unstaged changes -- the same
	// signal delightd's backup loop reacts to.
	return watcher.Result{HasWork: !status.IsClean()}, nil
}
