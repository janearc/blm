# Stage 1: build the static dummy binary.
#
# Unlike the consumer repos (delightd, paling) that gitignore gen/ and regenerate
# bindings at build, Big Little Mesh COMMITS its generated bindings (gen/ is tracked, so
# consumers can `go get` them). The dummy therefore compiles with just the module
# cache and a static `go build` -- no buf, no codegen toolchain in the image.
FROM golang:1.26-alpine AS builder
RUN apk add --no-cache git
WORKDIR /src

# Cache module downloads as their own layer.
COPY go.mod go.sum ./
RUN go mod download

COPY . .

# CGO_ENABLED=0 yields a purely static binary (no libc), so it runs on scratch
# and as a non-root user without any runtime dependencies. -ldflags="-s -w"
# strips the debug info and symbol table -- ~30% off (19.6MB -> 13.5MB) for a
# service this small, with no runtime effect.
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o dummy ./cmd/dummy

# Stage 2: scratch runtime. The dummy is a pure worker -- inbox watcher + Kafka
# emit + heartbeat -- with no HTTP surface, so there is nothing to EXPOSE.
FROM scratch
COPY --from=builder /src/dummy /usr/local/bin/dummy
ENTRYPOINT ["/usr/local/bin/dummy"]
