package consume

import (
	"bytes"
	"encoding/binary"
	"testing"
)

// frame builds a Confluent SR frame: magic, big-endian schema id, the given
// message-index bytes, then payload -- the layout emit.encode produces.
func frame(id uint32, index, payload []byte) []byte {
	var b bytes.Buffer
	b.WriteByte(0x00)
	var idb [4]byte
	binary.BigEndian.PutUint32(idb[:], id)
	b.Write(idb[:])
	b.Write(index)
	b.Write(payload)
	return b.Bytes()
}

// TestStripFrame_FirstMessage covers the 0x00 single-byte index optimization
// (the common case): the payload comes back untouched.
func TestStripFrame_FirstMessage(t *testing.T) {
	payload := []byte("hello-protobuf")
	got, err := StripFrame(frame(7, []byte{0x00}, payload))
	if err != nil {
		t.Fatalf("StripFrame: %v", err)
	}
	if !bytes.Equal(got, payload) {
		t.Errorf("payload = %q, want %q", got, payload)
	}
}

// TestStripFrame_SecondMessage covers the general varint message-index path:
// count=1 (zig-zag 0x02), index=1 (zig-zag 0x02) -- the inverse of the sharp
// edge emit guards on the write side.
func TestStripFrame_SecondMessage(t *testing.T) {
	payload := []byte("second-message-body")
	got, err := StripFrame(frame(9, []byte{0x02, 0x02}, payload))
	if err != nil {
		t.Fatalf("StripFrame: %v", err)
	}
	if !bytes.Equal(got, payload) {
		t.Errorf("payload = %q, want %q", got, payload)
	}
}

// TestStripFrame_Rejects covers the malformed cases that must error rather than
// hand back garbage: too short, and a non-zero magic byte.
func TestStripFrame_Rejects(t *testing.T) {
	if _, err := StripFrame([]byte{0x00, 0x01}); err == nil {
		t.Error("expected error for too-short frame")
	}
	if _, err := StripFrame([]byte{0x01, 0, 0, 0, 7, 0x00}); err == nil {
		t.Error("expected error for bad magic byte")
	}
}
