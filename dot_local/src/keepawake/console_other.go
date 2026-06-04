//go:build !windows

package main

func setupConsole() {
	// No-op for Unix systems, as they attach automatically
}
