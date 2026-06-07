BINARY  := keepawake
OUT     ?= ./$(BINARY)
VERSION ?= dev
GOOS    ?= linux
GOARCH  ?= amd64

LDFLAGS := -s -w -X main.version=$(VERSION)

.PHONY: build run clean

build:
	GOOS=$(GOOS) GOARCH=$(GOARCH) go build -ldflags="$(LDFLAGS)" -o "$(OUT)" .

run: build
	$(OUT)

clean:
	rm -f ./$(BINARY)
