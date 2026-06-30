// protoc-gen-rust-serde emits a plain serde Rust crate from the contracts, so a Rust
// consumer (today: the observability "floater", which lives in its own repo and takes a
// git/path dependency on the generated crate) speaks the fleet's protojson wire format
// with NO prost and NO protobuf runtime. The contract stays the single source of truth,
// the Rust moves with it under `buf generate`, and the gen-drift gate catches any skew --
// the same discipline as every other gen tree.
//
// Why not prost? prost is for BINARY protobuf: it generates encode/decode against the
// length-delimited wire and pulls in the prost runtime (and usually prost-build/protoc at
// the consumer's build time). Our wire is protojson -- JSON with protobuf's field-name and
// enum-name conventions -- carried over HTTP and Kafka, framed by the emit layer. So the
// Rust side needs nothing more than serde structs/enums whose JSON shape IS protojson:
// no binary codec, no runtime, no build-time protoc at the consumer. That mirrors exactly
// what protoc-gen-swift-codable does for the Swift provider (plain Codable, no
// SwiftProtobuf). prost would be a heavier dependency speaking the wrong wire.
//
// Scope (deliberately narrow, like the Swift plugin): it generates only the packages the
// Rust consumer needs -- observability.v1 by default -- and only the field shapes that package
// actually uses: string, uint32, proto3 `optional uint32`, enum, singular message, and the
// google.protobuf.Timestamp well-known type (mapped to an RFC3339 String, protojson's
// Timestamp form). It errors loudly on anything else -- repeated, map, other scalars,
// other well-known types, nested types -- rather than emit something subtly wrong; teach
// the emitter the new shape when a real need arrives. (buf runs every plugin over the whole
// module, so the package filter, like protoc-gen-fsm's enum filter, is how it stays scoped.)
//
// The whole crate is generated -- Cargo.toml, the lib.rs module tree, the bindings, and a
// #[cfg(test)] protojson conformance module per package -- so the consumable artifact under
// gen/rust is fully reproducible from the contracts with nothing hand-edited; the drift gate
// then guards the manifest too. The conformance tests run under `cargo test` (gated in CI):
// they lock the enum vocabulary and tolerant decode, the lowerCamel keys, and the
// presence/omission of Option fields, so the wire shape cannot regress unnoticed.
//
// The crate name and the package allowlist are buf opt: params (`crate_name` and `packages`;
// see this module's buf.gen.yaml and the constants below), defaulting to this repo's values.
// That is how another repo runs this SAME plugin binary unforked: delightd generates its
// registry.v1 crate with `crate_name=delightd-contracts,packages=registry.v1`, and the two
// crates coexist in one consumer's dependency graph. Version, edition, and the serde
// dependency stay constants -- edit them below and regenerate.
//
// protojson conventions baked in:
//   - JSON keys are lowerCamelCase of the proto field name; the Rust field stays snake_case
//     (idiomatic, warning-free) and carries an explicit #[serde(rename = "...")] to the
//     protojson key, so the mapping is exact and self-documenting rather than relying on a
//     rename_all heuristic matching protobuf's algorithm.
//   - enums serialize as their value NAME (the protojson default form, e.g.
//     "HEALTH_STATE_GREEN", not the bare "GREEN"). Every enum also carries a #[serde(other)]
//     Unknown catch-all, so a value added to the contract after this crate was generated
//     decodes to Unknown rather than failing the parse -- a contract addition can never panic
//     a consumer. Re-encoding Unknown is lossy (it emits "Unknown"); producers must not rely
//     on round-tripping it.
//   - proto3 omits default-valued fields, so a field may be absent on the wire; the structs
//     carry #[serde(default)] so an absent field decodes to its proto3 default. Singular
//     messages and proto3-`optional` scalars have no proto3 default, so they are Option<T>
//     and are omitted on encode when None (skip_serializing_if), matching the Swift plugin's
//     tolerant-decode / presence-aware-encode behavior.
package main

import (
	"flag"
	"fmt"
	"sort"
	"strings"

	"google.golang.org/protobuf/compiler/protogen"
	"google.golang.org/protobuf/reflect/protoreflect"
)

// Crate identity. The whole crate is generated, so these live here rather than in a
// hand-written Cargo.toml. The Cargo package name and the package allowlist are overridable
// via the `crate_name` and `packages` buf opt: params (wired in main); these are the defaults,
// keeping this repo's own generation unchanged when no opt is passed. defaultCrateName is
// repo-scoped: blm owns these packages, and another repo's run of this same plugin --
// delightd's registry.v1 -- passes crate_name=delightd-contracts to emit a differently-named
// crate, so the two coexist in one consumer's dependency graph. Cargo maps the hyphens to
// underscores for the lib path, so a consumer writes
// `use big_little_mesh_contracts::observability::v1::ServiceHealthHeartbeat;`.
const (
	defaultCrateName = "big-little-mesh-contracts"
	defaultPackages  = "observability.v1"
	crateVersion     = "0.1.0"
	crateEdition     = "2021"
	serdeVersion     = "1"
	serdeJSONVersion = "1"
)

// crateName is the Cargo package name, set in main from the -crate_name opt (default
// defaultCrateName).
var crateName = defaultCrateName

// crateLibName is the crate's library path: Cargo replaces hyphens with underscores.
func crateLibName() string { return strings.ReplaceAll(crateName, "-", "_") }

// rustPackages are the contract packages the Rust consumer speaks, set in main from the
// -packages opt (comma-separated, default defaultPackages). Every other package in the module
// is skipped, exactly as protoc-gen-swift-codable filters to the Swift packages.
var rustPackages = parsePackages(defaultPackages)

// parsePackages splits the `packages` opt into the allowlist set, trimming surrounding
// whitespace and dropping empty entries. It accepts BOTH ',' and ';' as separators: the in-Go
// default uses commas, but buf splits a plugin opt string on commas before the plugin sees it,
// so multiple packages passed via `buf opt:` MUST be ';'-separated (e.g. packages=a.v1;b.v1).
func parsePackages(spec string) map[string]bool {
	out := map[string]bool{}
	for _, p := range strings.FieldsFunc(spec, func(r rune) bool { return r == ',' || r == ';' }) {
		if p = strings.TrimSpace(p); p != "" {
			out[p] = true
		}
	}
	return out
}

// timestampFullName is the one well-known type observability.v1 uses; it maps to an RFC3339
// String (protojson's Timestamp form). Any other WKT is an error -- teach the emitter.
const timestampFullName protoreflect.FullName = "google.protobuf.Timestamp"

func main() {
	// crate_name and packages are buf opt: params, parsed via the standard protoc-plugin
	// flag.FlagSet wired through protogen's ParamFunc. They default to this repo's values, so
	// behavior is unchanged when no opt is passed; delightd passes its own to run this same
	// binary unforked (see the package doc and buf.gen.yaml).
	var flags flag.FlagSet
	crateNameOpt := flags.String("crate_name", defaultCrateName,
		"Cargo package name for the generated crate (hyphens map to the underscore lib path)")
	packagesOpt := flags.String("packages", defaultPackages,
		"proto package allowlist the Rust consumer speaks (others skipped); under buf opt separate multiple with ';' (buf splits ',')")
	protogen.Options{ParamFunc: flags.Set}.Run(func(gen *protogen.Plugin) error {
		gen.SupportedFeatures = uint64(1) // FEATURE_PROTO3_OPTIONAL
		crateName = *crateNameOpt
		rustPackages = parsePackages(*packagesOpt)

		// Group the files we generate for by their proto package, so a package that spans
		// multiple files lands in one Rust module. (observability.v1 is a single file today.)
		filesByPkg := map[string][]*protogen.File{}
		for _, f := range gen.Files {
			if !f.Generate || !rustPackages[string(f.Desc.Package())] {
				continue
			}
			pkg := string(f.Desc.Package())
			filesByPkg[pkg] = append(filesByPkg[pkg], f)
		}
		if len(filesByPkg) == 0 {
			return nil // nothing in this per-directory invocation is in scope; emit nothing.
		}

		// Emit the per-package binding modules and collect their slash-form paths
		// (observability.v1 -> observability/v1) to build the module tree and the manifest.
		var pkgPaths []string
		for pkg, files := range filesByPkg {
			sort.Slice(files, func(i, j int) bool { return files[i].Desc.Path() < files[j].Desc.Path() })
			path := strings.ReplaceAll(pkg, ".", "/")
			pkgPaths = append(pkgPaths, path)
			if err := genPackage(gen, files); err != nil {
				return err
			}
		}
		sort.Strings(pkgPaths)

		if err := genModuleTree(gen, pkgPaths); err != nil {
			return err
		}
		genCargoToml(gen)
		return nil
	})
}

// genCargoToml writes the crate manifest. serde with `derive` is the only dependency; the
// crate is consumed via a git/path dependency, so it is marked publish = false.
func genCargoToml(gen *protogen.Plugin) {
	g := gen.NewGeneratedFile("Cargo.toml", "")
	g.P("# Code generated by protoc-gen-rust-serde. DO NOT EDIT.")
	g.P("#")
	g.P("# The generated ", crateName, " crate: plain serde bindings for the contracts that")
	g.P("# speak protojson. A separate repo (the observability floater) depends on this crate")
	g.P("# across the repo boundary via a git or path dependency.")
	g.P()
	g.P("[package]")
	g.P(`name = "`, crateName, `"`)
	g.P(`version = "`, crateVersion, `"`)
	g.P(`edition = "`, crateEdition, `"`)
	g.P("publish = false")
	g.P()
	g.P("[dependencies]")
	g.P(`serde = { version = "`, serdeVersion, `", features = ["derive"] }`)
	g.P()
	// serde_json backs the generated #[cfg(test)] protojson conformance module only; a
	// consumer that just builds the crate never pulls it.
	g.P("[dev-dependencies]")
	g.P(`serde_json = "`, serdeJSONVersion, `"`)
}

// genModuleTree writes src/lib.rs and the intermediate `pub mod` stubs that connect the
// crate root to each binding module. It is built from the set of generated package paths,
// so adding a package to rustPackages grows the tree with no further changes here.
func genModuleTree(gen *protogen.Plugin, pkgPaths []string) error {
	// children[parent] is the set of immediate child module names; isPkg marks a node that
	// is itself a generated package (its binding module is written by genPackage). The root
	// is the empty path "" and maps to src/lib.rs.
	children := map[string]map[string]bool{"": {}}
	isPkg := map[string]bool{}
	for _, p := range pkgPaths {
		parent := ""
		for _, seg := range strings.Split(p, "/") {
			if children[parent] == nil {
				children[parent] = map[string]bool{}
			}
			children[parent][seg] = true
			if parent == "" {
				parent = seg
			} else {
				parent = parent + "/" + seg
			}
		}
		isPkg[p] = true
	}

	// A package's binding module is written by genPackage and holds only its types -- it does
	// NOT declare child modules. So a node that is BOTH a generated package AND an ancestor of
	// another generated package (e.g. both `foo` and `foo.bar` are generated) would orphan the
	// child: nothing would emit `pub mod bar;` and the crate would not compile. That cannot
	// happen today -- every contract package is an `x.vN` leaf -- so rather than silently emit a
	// broken tree, error loudly if it ever appears; teach genPackage to fold child decls into
	// the package file then.
	var nodes []string
	for n := range children {
		nodes = append(nodes, n)
	}
	sort.Strings(nodes)

	for _, n := range nodes {
		if n == "" {
			genLibRoot(gen, sortedKeys(children[""]))
			continue
		}
		if isPkg[n] {
			if len(children[n]) > 0 {
				return fmt.Errorf("package %q is also an ancestor of another generated package; "+
					"nested-package module trees are not supported (teach the emitter)", n)
			}
			continue // a leaf package's own file (from genPackage) needs no child decls.
		}
		g := gen.NewGeneratedFile("src/"+n+".rs", "")
		g.P("// Code generated by protoc-gen-rust-serde. DO NOT EDIT.")
		g.P()
		for _, c := range sortedKeys(children[n]) {
			g.P("pub mod ", c, ";")
		}
	}
	return nil
}

// genLibRoot writes src/lib.rs: the crate doc plus the top-level `pub mod` declarations.
func genLibRoot(gen *protogen.Plugin, roots []string) {
	g := gen.NewGeneratedFile("src/lib.rs", "")
	g.P("// Code generated by protoc-gen-rust-serde. DO NOT EDIT.")
	g.P()
	g.P("//! Generated serde bindings for the Big Little Mesh contracts.")
	g.P("//!")
	g.P("//! These types speak protojson -- protobuf's JSON form -- with serde, and carry no")
	g.P("//! prost and no protobuf runtime. This crate is generated from the .proto contracts")
	g.P("//! and MUST NOT be edited by hand; change the contracts and regenerate. Consumers")
	g.P("//! take a git or path dependency on this crate and `use ", crateLibName(), "::...`.")
	g.P()
	for _, r := range roots {
		g.P("pub mod ", r, ";")
	}
}

// genPackage writes one binding module (e.g. src/observability/v1.rs) holding the enums and
// structs for every file in the package: enums first, then messages, matching the Swift
// plugin's ordering.
func genPackage(gen *protogen.Plugin, files []*protogen.File) error {
	pkg := string(files[0].Desc.Package())
	path := strings.ReplaceAll(pkg, ".", "/")
	g := gen.NewGeneratedFile("src/"+path+".rs", "")

	g.P("// Code generated by protoc-gen-rust-serde. DO NOT EDIT.")
	for _, f := range files {
		g.P("// source: ", f.Desc.Path())
	}
	g.P()
	g.P("use serde::{Deserialize, Serialize};")
	g.P()

	var enums []enumInfo
	for _, f := range files {
		for _, e := range f.Enums {
			enums = append(enums, genEnum(g, e))
		}
	}
	var msgs []msgInfo
	for _, f := range files {
		for _, m := range f.Messages {
			mi, err := genMessage(g, m)
			if err != nil {
				return err
			}
			msgs = append(msgs, mi)
		}
	}
	genTests(g, enums, msgs)
	return nil
}

// genTests emits a #[cfg(test)] module that locks the protojson contract reproducibly (it
// runs under `cargo test`, gated in CI): enum vocabulary + tolerant decode of an unknown
// value, lowerCamel keys, Option fields omitted when None and present when Some, and tolerant
// decode of an all-absent ("{}") payload. It is generated from the same metadata as the
// types, so it cannot rot out of sync and grows automatically with new packages.
func genTests(g *protogen.GeneratedFile, enums []enumInfo, msgs []msgInfo) {
	g.P("#[cfg(test)]")
	g.P("mod protojson_tests {")
	g.P("    use super::*;")
	g.P()
	for _, e := range enums {
		g.P("    #[test]")
		g.P("    fn ", snakeFromPascal(e.name), "_vocab_and_tolerance() {")
		g.P("        // serializes as the protojson-standard value name (not the bare vocabulary).")
		g.P("        assert_eq!(")
		g.P("            serde_json::to_string(&", e.name, "::", e.knownIdent, ").unwrap(),")
		g.P("            \"\\\"", e.knownValue, "\\\"\"")
		g.P("        );")
		g.P("        // an unrecognized protojson value decodes to Unknown, never failing the parse.")
		g.P("        assert_eq!(")
		g.P("            serde_json::from_str::<", e.name, ">(\"\\\"__big_little_mesh_unknown__\\\"\").unwrap(),")
		g.P("            ", e.name, "::Unknown")
		g.P("        );")
		g.P("    }")
		g.P()
	}
	for _, m := range msgs {
		g.P("    #[test]")
		g.P("    fn ", snakeFromPascal(m.name), "_protojson() {")
		g.P("        let d = ", m.name, "::default();")
		g.P("        // proto3 omits defaults: every field absent on the wire decodes to the default.")
		g.P("        assert_eq!(serde_json::from_str::<", m.name, ">(\"{}\").unwrap(), d);")
		hasFields := len(m.fields) > 0
		hasOptional := false
		for _, rf := range m.fields {
			if rf.optional {
				hasOptional = true
			}
		}
		if hasFields {
			g.P("        let jd = serde_json::to_value(&d).unwrap();")
			for _, rf := range m.fields {
				if rf.optional {
					g.P("        // an unset Option (message / timestamp / proto3-optional) is omitted on encode.")
					g.P("        assert!(jd.get(\"", rf.jsonKey, "\").is_none());")
				} else {
					g.P("        // carries its lowerCamel protojson key.")
					g.P("        assert!(jd.get(\"", rf.jsonKey, "\").is_some());")
				}
			}
		}
		if hasOptional {
			g.P("        // a present Option serializes under its protojson key (Timestamp rides as a string).")
			g.P("        let mut p = d.clone();")
			for _, rf := range m.fields {
				if rf.optional {
					g.P("        p.", rf.name, " = Some(Default::default());")
				}
			}
			g.P("        let jp = serde_json::to_value(&p).unwrap();")
			for _, rf := range m.fields {
				if rf.optional {
					g.P("        assert!(jp.get(\"", rf.jsonKey, "\").is_some());")
				}
			}
		}
		g.P("    }")
		g.P()
	}
	g.P("}")
}

// enumInfo is what the generated conformance test needs about one enum: the type name and a
// known variant with its protojson value, to assert the vocabulary and tolerant decode.
type enumInfo struct {
	name       string
	knownIdent string
	knownValue string
}

// msgInfo is what the generated conformance test needs about one message: the type name and
// its resolved fields (protojson keys and which are Option-wrapped).
type msgInfo struct {
	name   string
	fields []rustField
}

func genEnum(g *protogen.GeneratedFile, e *protogen.Enum) enumInfo {
	name := string(e.Desc.Name())
	g.P("#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]")
	g.P("pub enum ", name, " {")
	// Mark the proto3 zero value as #[default]; it is the value used when the field is
	// absent on the wire. proto3's first enum value is required to be 0.
	defaulted := false
	for _, v := range e.Values {
		vn := string(v.Desc.Name())
		if !defaulted && v.Desc.Number() == 0 {
			g.P("    #[default]")
			defaulted = true
		}
		g.P("    #[serde(rename = \"", vn, "\")]")
		g.P("    ", pascalCase(vn), ",")
	}
	if !defaulted {
		// No zero value (not valid proto3, but stay correct): default to the first variant.
		g.P("    // note: no value 0; #[default] could not be assigned to the zero value.")
	}
	// Forward-compat catch-all: a protojson value this build does not recognize (e.g. a
	// value added to the enum after this crate was generated) decodes here via #[serde(other)]
	// instead of failing the whole struct parse -- so a contract addition can never panic a
	// consumer (the floater's documented invariant). Re-encoding Unknown is LOSSY: it emits
	// "Unknown", not the original string. That is acceptable for consumers; a producer MUST
	// NOT rely on round-tripping an Unknown.
	g.P("    #[serde(other)]")
	g.P("    Unknown,")
	g.P("}")
	g.P()
	// Use the first value (the proto3 zero) as the known sample in the conformance test.
	first := e.Values[0]
	return enumInfo{
		name:       name,
		knownIdent: pascalCase(string(first.Desc.Name())),
		knownValue: string(first.Desc.Name()),
	}
}

// rustField is one resolved struct field: its Rust field name, the protojson JSON key, the
// Rust type as written, and whether it is wrapped in Option (a singular message, the
// Timestamp WKT, or a proto3-`optional` scalar) -- which decides skip_serializing_if.
type rustField struct {
	name     string
	jsonKey  string
	typ      string
	optional bool
}

func genMessage(g *protogen.GeneratedFile, m *protogen.Message) (msgInfo, error) {
	name := string(m.Desc.Name())
	// Stay as narrow as the Swift plugin: no nested types today. Error loudly rather than
	// silently drop a type a field might reference.
	if len(m.Messages) > 0 || len(m.Enums) > 0 {
		return msgInfo{}, fmt.Errorf("%s: nested messages/enums are not supported (teach the emitter)", name)
	}

	var fields []rustField
	for _, field := range m.Fields {
		rf, err := mapField(field)
		if err != nil {
			return msgInfo{}, fmt.Errorf("%s.%s: %w", name, field.Desc.Name(), err)
		}
		fields = append(fields, rf)
	}

	// #[serde(default)] on the struct fills any field absent on the wire from Default, which
	// is the proto3 default -- the tolerant decode. Encoding emits present fields; Option
	// fields are skipped when None so an unset message/optional/timestamp is omitted.
	g.P("#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]")
	g.P("#[serde(default)]")
	g.P("pub struct ", name, " {")
	for _, rf := range fields {
		if rf.optional {
			g.P("    #[serde(rename = \"", rf.jsonKey, "\", skip_serializing_if = \"Option::is_none\")]")
		} else {
			g.P("    #[serde(rename = \"", rf.jsonKey, "\")]")
		}
		g.P("    pub ", rf.name, ": ", rf.typ, ",")
	}
	g.P("}")
	g.P()
	return msgInfo{name: name, fields: fields}, nil
}

func mapField(field *protogen.Field) (rustField, error) {
	name := rustIdent(string(field.Desc.Name()))
	jsonKey := lowerCamel(string(field.Desc.Name()))

	if field.Desc.IsMap() {
		return rustField{}, fmt.Errorf("map fields are not supported (teach the emitter)")
	}
	if field.Desc.IsList() {
		return rustField{}, fmt.Errorf("repeated fields are not supported (teach the emitter)")
	}

	switch field.Desc.Kind() {
	case protoreflect.StringKind:
		return wrapOptional(field, rustField{name: name, jsonKey: jsonKey, typ: "String"}), nil
	case protoreflect.Uint32Kind:
		return wrapOptional(field, rustField{name: name, jsonKey: jsonKey, typ: "u32"}), nil
	case protoreflect.EnumKind:
		return wrapOptional(field, rustField{name: name, jsonKey: jsonKey, typ: string(field.Enum.Desc.Name())}), nil
	case protoreflect.MessageKind:
		// google.protobuf.Timestamp rides as an RFC3339 String; any other message is a
		// nested struct in this same module. A singular message has no proto3 default, so
		// it is Option<T> and omitted when absent.
		if field.Message.Desc.FullName() == timestampFullName {
			return rustField{name: name, jsonKey: jsonKey, typ: "Option<String>", optional: true}, nil
		}
		return rustField{name: name, jsonKey: jsonKey, typ: "Option<" + string(field.Message.Desc.Name()) + ">", optional: true}, nil
	default:
		return rustField{}, fmt.Errorf("unsupported field kind %q (teach the emitter; note: 64-bit ints are protojson strings)", field.Desc.Kind())
	}
}

// wrapOptional turns a scalar/enum field into Option<T> when it carries proto3's explicit
// `optional` keyword (tracked presence). Plain singular scalars keep their proto3 default.
func wrapOptional(field *protogen.Field, rf rustField) rustField {
	if field.Desc.HasOptionalKeyword() {
		rf.typ = "Option<" + rf.typ + ">"
		rf.optional = true
	}
	return rf
}

// lowerCamel converts a proto snake_case name to lowerCamelCase (service_name -> serviceName),
// the protojson JSON key form.
func lowerCamel(s string) string {
	var b strings.Builder
	for i, part := range strings.Split(s, "_") {
		if part == "" {
			continue
		}
		part = strings.ToLower(part)
		if i == 0 {
			b.WriteString(part)
		} else {
			b.WriteString(strings.ToUpper(part[:1]))
			b.WriteString(part[1:])
		}
	}
	return b.String()
}

// pascalCase converts a proto SCREAMING_SNAKE enum value name to PascalCase
// (HEALTH_STATE_GREEN -> HealthStateGreen), the Rust variant identifier. The protojson wire
// value (the original name) is carried by an explicit #[serde(rename)], so this does not
// strip the enum-name prefix -- mirroring the Swift plugin's non-stripping choice.
func pascalCase(s string) string {
	var b strings.Builder
	for _, part := range strings.Split(s, "_") {
		if part == "" {
			continue
		}
		part = strings.ToLower(part)
		b.WriteString(strings.ToUpper(part[:1]))
		b.WriteString(part[1:])
	}
	return b.String()
}

// snakeFromPascal converts a PascalCase type name to snake_case for a test function name
// (ServiceHealthHeartbeat -> service_health_heartbeat, HealthState -> health_state).
func snakeFromPascal(s string) string {
	var b strings.Builder
	for i, r := range s {
		if i > 0 && r >= 'A' && r <= 'Z' {
			b.WriteByte('_')
		}
		if r >= 'A' && r <= 'Z' {
			r += 'a' - 'A'
		}
		b.WriteRune(r)
	}
	return b.String()
}

// rustIdent escapes a proto field name that collides with a Rust keyword. Most keywords take
// the raw-identifier form (r#type); the few that cannot be raw identifiers get a trailing
// underscore. Proto field names are already snake_case, so no case conversion is needed.
func rustIdent(name string) string {
	if rawUnsafeKeywords[name] {
		return name + "_"
	}
	if rustKeywords[name] {
		return "r#" + name
	}
	return name
}

// rawUnsafeKeywords cannot be written as raw identifiers, so they are suffixed instead.
var rawUnsafeKeywords = map[string]bool{
	"crate": true, "self": true, "super": true, "Self": true,
}

var rustKeywords = map[string]bool{
	"as": true, "break": true, "const": true, "continue": true, "dyn": true,
	"else": true, "enum": true, "extern": true, "false": true, "fn": true,
	"for": true, "if": true, "impl": true, "in": true, "let": true, "loop": true,
	"match": true, "mod": true, "move": true, "mut": true, "pub": true, "ref": true,
	"return": true, "static": true, "struct": true, "trait": true, "true": true,
	"type": true, "unsafe": true, "use": true, "where": true, "while": true,
	"async": true, "await": true, "abstract": true, "become": true, "box": true,
	"do": true, "final": true, "macro": true, "override": true, "priv": true,
	"typeof": true, "unsized": true, "virtual": true, "yield": true, "try": true,
	"union": true,
}

func sortedKeys(m map[string]bool) []string {
	var out []string
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}
