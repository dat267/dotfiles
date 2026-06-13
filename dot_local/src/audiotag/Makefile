BINARY  := audiotag
VERSION ?= dev

# Detect Host Operating System and resolve Home Directory
ifeq ($(OS),Windows_NT)
    HOST_OS    := windows
    HOME_DIR   := $(USERPROFILE)
    RM         := del /f /q
    FIX_PATH    = $(subst /,\\,$(1))
    BINARY_EXT  := .exe
else
    HOST_OS    := linux
    HOME_DIR   := $(HOME)
    RM         := rm -f
    FIX_PATH    = $(1)
    BINARY_EXT  :=
endif

GOOS    ?= $(HOST_OS)
GOARCH  ?= amd64
OUT     ?= $(HOME_DIR)/.local/bin/$(BINARY)$(BINARY_EXT)

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
