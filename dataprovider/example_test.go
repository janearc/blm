package dataprovider_test

import (
	"context"

	"github.com/janearc/blm/dataprovider"
	authv1 "github.com/janearc/blm/gen/go/auth/v1"
	dpv1 "github.com/janearc/blm/gen/go/dataprovider/v1"
)

// Example shows a consumer reading a cell while presenting an OAuth credential. The
// provider is stateless -- no session, no login step -- so the credential rides the
// request itself. (No Output: line, so this documents the call shape; it is compiled,
// not run.)
func Example() {
	ctx := context.Background()

	// a concrete provider is a transport client (protojson-over-HTTP to the sidecar).
	// nil here because this example documents how the contract is called, not a live call.
	var provider dataprovider.DataProvider

	req := &dpv1.GetRequest{
		Namespace: "paling",
		RowKey:    "8f14e45f-ceea-467d-9d5f-fed6ad4f1f3a",
		Column:    "adapter",
		RefKey:    7,
		// OAUTH proves the caller may make the request; an implementer may require further
		// payloads for finer access. The payload is opaque -- the provider interprets it.
		Credentials: []*authv1.AuthPayload{{
			Type:    authv1.AuthPayloadType_AUTH_PAYLOAD_TYPE_OAUTH,
			Payload: []byte("<oauth token bytes>"),
		}},
	}

	resp, err := provider.Get(ctx, req)
	if err != nil {
		// a transport or policy failure (an HTTP status). a missing cell is NOT an error.
		return
	}
	if !resp.Found {
		// no cell at these coordinates.
		return
	}
	_ = resp.Cell // the cell; its JSON value is resp.Cell.Body
}
