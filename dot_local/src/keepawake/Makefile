# Build contract for CI — called as:
#   make build OUT=/absolute/path/to/binary GOOS=linux GOARCH=amd64 VERSION=tools/20260604-000000
#
# Local development:
#   make build                  # builds for current platform into ./keepawake
#   make run                    # build + run
#   make clean

BINARY  := keepawake
OUT     ?= ./$(BINARY)
VERSION ?= dev
GOOS    ?= linux
GOARCH  ?= amd64

LDFLAGS := -s -w -X main.version=$(VERSION)
ifeq ($(GOOS),windows)
	LDFLAGS += -H=windowsgui
endif

.PHONY: build run clean

build:
	CGO_ENABLED=0 GOOS=$(GOOS) GOARCH=$(GOARCH) go build \
		-ldflags="$(LDFLAGS)" \
		-o "$(OUT)" \
		.

run: build
	$(OUT)

clean:
	rm -f ./$(BINARY)
