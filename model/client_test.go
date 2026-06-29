package model

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	modelv1 "github.com/janearc/big-little-mesh/gen/go/model/v1"
)

func discoveryServer(body string) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(body))
	}))
}

func TestResolve(t *testing.T) {
	d := discoveryServer(`{"sources":[{"provider":"ollama","url":"http://x:11434","healthy":true,"models":["mistral:latest"]}]}`)
	defer d.Close()
	desc, err := New(d.URL).Resolve(context.Background(), "mistral")
	if err != nil {
		t.Fatalf("Resolve: %v", err)
	}
	if desc.ModelId != "mistral:latest" || desc.Provider != modelv1.Provider_PROVIDER_OLLAMA {
		t.Errorf("got %+v", desc)
	}
}

func TestResolve_FailClosed(t *testing.T) {
	// nothing healthy -> ErrModelUnavailable, not a fabricated fallback.
	d := discoveryServer(`{"sources":[{"provider":"ollama","url":"http://x","healthy":false,"models":["mistral:latest"]}]}`)
	defer d.Close()
	if _, err := New(d.URL).Resolve(context.Background(), "mistral"); !errors.Is(err, ErrModelUnavailable) {
		t.Fatalf("want ErrModelUnavailable, got %v", err)
	}
	// delightd unreachable -> also fail-closed.
	if _, err := New("http://127.0.0.1:1").Resolve(context.Background(), "mistral"); !errors.Is(err, ErrModelUnavailable) {
		t.Fatalf("unreachable: want ErrModelUnavailable, got %v", err)
	}
}

func TestGenerate_Ollama(t *testing.T) {
	ollama := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/generate" {
			t.Errorf("path = %s", r.URL.Path)
		}
		_, _ = w.Write([]byte(`{"response":"hello from mistral"}`))
	}))
	defer ollama.Close()
	d := discoveryServer(fmt.Sprintf(`{"sources":[{"provider":"ollama","url":"%s","healthy":true,"models":["mistral:latest"]}]}`, ollama.URL))
	defer d.Close()

	out, err := New(d.URL).Generate(context.Background(), "mistral", "hi", 5*time.Second)
	if err != nil {
		t.Fatalf("Generate: %v", err)
	}
	if out != "hello from mistral" {
		t.Errorf("got %q", out)
	}
}
