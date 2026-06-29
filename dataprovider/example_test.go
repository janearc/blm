package dataprovider_test

import (
	"context"

	"github.com/janearc/big-little-mesh/dataprovider"
	authv1 "github.com/janearc/big-little-mesh/gen/go/auth/v1"
	dpv1 "github.com/janearc/big-little-mesh/gen/go/dataprovider/v1"
)

// Example shows a consumer reading a cell from a DataProvider. It is written to stand on
// its own -- you should not need the README to follow it.
//
// (There is no Output: line, so this documents the call shape; it is compiled, not run.)
func Example() {
	ctx := context.Background()

	// A concrete provider is a transport client -- the contract is descriptor-only and
	// rides protojson-over-HTTP to the sidecar, so a real one wraps an HTTP client. It is
	// nil here because this example shows how the contract is called, not a live call.
	var provider dataprovider.DataProvider

	// A cell is addressed by three coordinates: row_key (a UUID), column (the field within
	// that row), and ref_key (the version -- higher is newer). This asks for one specific
	// version. To get the newest instead, you would use GetLatest with no ref_key.
	req := &dpv1.GetRequest{
		Namespace: "paling", // the logical store / keyspace
		RowKey:    "8f14e45f-ceea-467d-9d5f-fed6ad4f1f3a",
		Column:    "adapter",
		RefKey:    7,

		// The provider is stateless: there is no login step, so a credential rides every
		// request. It is opaque -- we attach a token and say nothing about what it means;
		// `type` is only a routing hint that tells the provider which validator to use.
		Credentials: []*authv1.AuthPayload{{
			Type:    authv1.AuthPayloadType_AUTH_PAYLOAD_TYPE_BEARER,
			Payload: []byte("<opaque token bytes>"),
		}},
	}

	resp, err := provider.Get(ctx, req)
	if err != nil {
		// An error is a transport or policy failure (surfaced as an HTTP status). A cell
		// that simply does not exist is NOT an error -- see resp.Found below.
		return
	}
	if !resp.Found {
		// No cell at these coordinates. A successful call that found nothing.
		return
	}

	// resp.Cell is the cell; resp.Cell.Body is its JSON object (the fields Query indexes).
	_ = resp.Cell
}
