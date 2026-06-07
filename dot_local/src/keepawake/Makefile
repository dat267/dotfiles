BINARY  := keepawake
VERSION ?= dev

# Detect Host Operating System
ifeq ($(OS),Windows_NT)
    HOST_OS   := windows
    RM        := del /f /q
    FIX_PATH   = $(subst /,\\,$(1))
    BINARY_EXT := .exe
else
    HOST_OS   := linux
    RM        := rm -f
    FIX_PATH   = $(1)
    BINARY_EXT :=
endif

GOOS    ?= $(HOST_OS)
GOARCH  ?= amd64
OUT     ?= ~/.local/bin/$(BINARY)$(BINARY_EXT)

LDFLAGS := -s -w -X main.version=$(VERSION)

# Export variables directly to the compiler's environment
export GOOS
export GOARCH

.PHONY: build run clean

build:
	go build -ldflags="$(LDFLAGS)" -o "$(OUT)" .

run: build
	$(call FIX_PATH,$(OUT))

clean:
	$(RM) $(call FIX_PATH,$(OUT))