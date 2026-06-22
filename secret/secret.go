// Package secret reads secret values that Kubernetes injected into the process
// environment via a Secret's secretKeyRef. good-citizen deliberately does NOT
// call the Kubernetes API: the fleet contract is that a Secret is mounted into
// the pod env (env.valueFrom.secretKeyRef), so a citizen just reads the env var.
// This keeps citizens credential-free in their code and config -- the value
// arrives at runtime, injected by the operator, and never lives in a file or a
// committed default. (See the kube-migration secrets rule.)
package secret

import (
	"fmt"
	"os"
	"strings"
)

// Get returns the secret at env var name, or an error if it is unset/empty. Use
// it for required secrets (e.g. a cloudflared tunnel token) where a missing value
// must fail fast and visibly rather than silently disable something.
func Get(name string) (string, error) {
	if v := os.Getenv(name); v != "" {
		return v, nil
	}
	return "", fmt.Errorf("secret %q not present in environment (expected a Kube secretKeyRef injection)", name)
}

// GetOr returns the secret at env var name, or def if unset. Use it for optional
// secrets where a default or disabled path is acceptable.
func GetOr(name, def string) string {
	if v := os.Getenv(name); v != "" {
		return v
	}
	return def
}

// Require checks that every named secret is present, returning one error naming
// all the missing ones. Call it once at startup so a misconfigured deployment
// fails immediately with a complete list, not one missing var at a time.
func Require(names ...string) error {
	var missing []string
	for _, n := range names {
		if os.Getenv(n) == "" {
			missing = append(missing, n)
		}
	}
	if len(missing) > 0 {
		return fmt.Errorf("missing required secrets (expected Kube secretKeyRef injections): %s", strings.Join(missing, ", "))
	}
	return nil
}
