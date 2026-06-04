//go:build !windows

package main

func attachConsole() {
	// No-op for Unix systems, as they attach automatically
}
