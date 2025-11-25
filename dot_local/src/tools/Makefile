# Build contract for CI — called as:
#   make build OUT=/absolute/path/to/binary GOOS=linux GOARCH=amd64 VERSION=tools/20260604-000000
#
# Local development:
#   make build                  # builds for current platform into ./tools
#   make run                    # build + run
#   make clean

BINARY  := tools
OUT     ?= ./$(BINARY)
VERSION ?= dev

.PHONY: build run clean

build:
	go build \
		-ldflags="-s -w -X main.version=$(VERSION)" \
		-o "$(OUT)" \
		.

run: build
	$(OUT)

clean:
	rm -f ./$(BINARY)
