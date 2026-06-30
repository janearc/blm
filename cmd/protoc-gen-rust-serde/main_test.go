package main

import "testing"

// TestParsePackages covers the dual-separator behavior #63 added: the in-Go default uses
// commas, but buf splits an opt string on commas before the plugin sees it, so multi-package
// via `buf opt:` must use semicolons. Both must work, with whitespace trimmed and empties dropped.
func TestParsePackages(t *testing.T) {
	cases := []struct {
		name string
		in   string
		want []string
	}{
		{"comma (in-Go default form)", "a.v1,b.v1", []string{"a.v1", "b.v1"}},
		{"semicolon (buf opt form)", "a.v1;b.v1", []string{"a.v1", "b.v1"}},
		{"mixed + whitespace", " a.v1 ; b.v1 , c.v1 ", []string{"a.v1", "b.v1", "c.v1"}},
		{"single", "observability.v1", []string{"observability.v1"}},
		{"empty", "", nil},
		{"separators only", "  ,  ; ", nil},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := parsePackages(tc.in)
			if len(got) != len(tc.want) {
				t.Fatalf("parsePackages(%q) = %v, want %v", tc.in, sortedKeys(got), tc.want)
			}
			for _, w := range tc.want {
				if !got[w] {
					t.Errorf("parsePackages(%q) missing %q (got %v)", tc.in, w, sortedKeys(got))
				}
			}
		})
	}
}
