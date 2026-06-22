package secret

import "testing"

func TestGet(t *testing.T) {
	t.Setenv("GC_TEST_TOKEN", "s3cr3t")
	if v, err := Get("GC_TEST_TOKEN"); err != nil || v != "s3cr3t" {
		t.Fatalf("Get present: got %q, %v", v, err)
	}
	if _, err := Get("GC_TEST_ABSENT"); err == nil {
		t.Error("Get absent: expected error for unset secret")
	}
}

func TestGetOr(t *testing.T) {
	if v := GetOr("GC_TEST_ABSENT", "fallback"); v != "fallback" {
		t.Errorf("GetOr unset: got %q, want fallback", v)
	}
	t.Setenv("GC_TEST_SET", "real")
	if v := GetOr("GC_TEST_SET", "fallback"); v != "real" {
		t.Errorf("GetOr set: got %q, want real", v)
	}
}

func TestRequire(t *testing.T) {
	t.Setenv("GC_TEST_A", "a")
	if err := Require("GC_TEST_A"); err != nil {
		t.Errorf("Require present: unexpected error %v", err)
	}
	// names all missing ones at once
	err := Require("GC_TEST_A", "GC_TEST_MISSING_1", "GC_TEST_MISSING_2")
	if err == nil {
		t.Fatal("Require: expected error for missing secrets")
	}
}
