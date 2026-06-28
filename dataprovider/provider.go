// Package dataprovider is the Go reference for the dataprovider.v1 contract: the
// DataProvider interface a consumer programs against, written over the generated message
// types. It is hand-written behavior on top of generated data -- the proto is the source
// of truth, this is how a descriptor-only contract is actually used in Go.
//
// There is no generated service stub: dataprovider.v1 is a descriptor-only interface that
// rides protojson-over-HTTP via the sidecar, not gRPC. So this interface is the Go seam --
// a transport client implements it, a consumer depends on it. See
// proto/dataprovider/v1/README.md.
package dataprovider

import (
	"context"

	dpv1 "github.com/janearc/blm/gen/go/dataprovider/v1"
)

// DataProvider is the Go view of the dataprovider.v1 contract: an append-only, immutable
// cell store. A read returns a cell and a found flag (a miss is found=false, not an
// error); a write is append-only and idempotent (the caller supplies ref_key). Every
// request carries opaque per-request credentials (auth.v1) -- the provider is stateless,
// so there is no login step and a credential rides each call; a transport implementation
// presents them and the provider validates per its policy.
type DataProvider interface {
	// Get returns one specific cell version. A miss is GetResponse.Found == false.
	Get(ctx context.Context, req *dpv1.GetRequest) (*dpv1.GetResponse, error)
	// GetLatest returns the highest-ref_key cell for (row_key, column). A miss is
	// GetLatestResponse.Found == false.
	GetLatest(ctx context.Context, req *dpv1.GetLatestRequest) (*dpv1.GetLatestResponse, error)
	// Put appends a cell. Idempotent: re-issuing the same (row_key, column, ref_key, body)
	// adds nothing.
	Put(ctx context.Context, req *dpv1.PutRequest) (*dpv1.PutResponse, error)
	// Query looks up cells by predicates over a secondary index (eventually consistent).
	Query(ctx context.Context, req *dpv1.QueryRequest) (*dpv1.QueryResponse, error)
}
