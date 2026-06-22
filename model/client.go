// Package model is good-citizen's model client: resolve a logical model name to a
// ModelDescriptor and invoke it, dispatching on provider. It is the Go half of
// the matched Go+Python pair (the Python client mirrors it, generalized from
// paling's modelclient); both are first-class because the fleet does much of both.
// Built over the generated model.v1.ModelDescriptor contract.
//
// Resolution goes through delightd's discovery (the fleet's LLM authority) and is
// fail-closed: if delightd is down or nothing healthy serves the model, callers
// get ErrModelUnavailable rather than a silent local fallback -- the availability
// mandate says resilience lives in delightd coming up, not in every consumer
// hedging.
package model

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"

	modelv1 "github.com/janearc/blm/gen/go/model/v1"
)

// ErrModelUnavailable means no healthy backend could be resolved for a model.
var ErrModelUnavailable = errors.New("no healthy backend for model")

// Client resolves and invokes models via delightd discovery.
type Client struct {
	delightdURL string
	http        *http.Client
}

// New builds a Client. An empty delightdURL defaults to the local control port.
func New(delightdURL string) *Client {
	if delightdURL == "" {
		delightdURL = "http://localhost:8088"
	}
	return &Client{delightdURL: delightdURL, http: &http.Client{Timeout: 5 * time.Second}}
}

func providerFor(name string) modelv1.Provider {
	switch strings.ToLower(name) {
	case "ollama":
		return modelv1.Provider_PROVIDER_OLLAMA
	case "anthropic":
		return modelv1.Provider_PROVIDER_ANTHROPIC
	default:
		return modelv1.Provider_PROVIDER_UNSPECIFIED
	}
}

// Resolve maps a logical model name to a live ModelDescriptor via delightd's
// /discovery/llms: the first healthy provider whose served model name contains
// `name` (ollama reports e.g. "mistral:latest", so substring-match). Fail-closed.
func (c *Client) Resolve(ctx context.Context, name string) (*modelv1.ModelDescriptor, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, strings.TrimRight(c.delightdURL, "/")+"/discovery/llms", nil)
	if err != nil {
		return nil, err
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("%w: delightd discovery unreachable: %v", ErrModelUnavailable, err)
	}
	defer resp.Body.Close()

	var data struct {
		Sources []struct {
			Provider string   `json:"provider"`
			URL      string   `json:"url"`
			Healthy  bool     `json:"healthy"`
			Models   []string `json:"models"`
		} `json:"sources"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return nil, err
	}

	want := strings.ToLower(name)
	for _, s := range data.Sources {
		if !s.Healthy {
			continue
		}
		for _, m := range s.Models {
			if strings.Contains(strings.ToLower(m), want) {
				return &modelv1.ModelDescriptor{
					Name:     name,
					Provider: providerFor(s.Provider),
					Endpoint: s.URL,
					ModelId:  m,
				}, nil
			}
		}
	}
	return nil, fmt.Errorf("%w: %q", ErrModelUnavailable, name)
}

// Generate resolves name and runs a single (non-streaming) completion, dispatching
// on the resolved provider. timeout bounds the generation call (separate from the
// short discovery timeout).
func (c *Client) Generate(ctx context.Context, name, prompt string, timeout time.Duration) (string, error) {
	d, err := c.Resolve(ctx, name)
	if err != nil {
		return "", err
	}
	switch d.Provider {
	case modelv1.Provider_PROVIDER_OLLAMA:
		return c.ollamaGenerate(ctx, d, prompt, timeout)
	default:
		// in-process (MLX/transformers), anthropic, openai-compatible: the Python
		// client owns in-process today; remote providers land with the model-svc
		// gateway. Surface clearly rather than pretend.
		return "", fmt.Errorf("provider %s not yet supported by the Go client", d.Provider.String())
	}
}

// ollamaGenerate runs a non-streaming ollama /api/generate completion.
func (c *Client) ollamaGenerate(ctx context.Context, d *modelv1.ModelDescriptor, prompt string, timeout time.Duration) (string, error) {
	body, err := json.Marshal(map[string]any{"model": d.ModelId, "prompt": prompt, "stream": false})
	if err != nil {
		return "", err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, strings.TrimRight(d.Endpoint, "/")+"/api/generate", bytes.NewReader(body))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := (&http.Client{Timeout: timeout}).Do(req)
	if err != nil {
		return "", fmt.Errorf("ollama generate: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("ollama returned %d", resp.StatusCode)
	}
	var out struct {
		Response string `json:"response"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return "", err
	}
	return out.Response, nil
}
