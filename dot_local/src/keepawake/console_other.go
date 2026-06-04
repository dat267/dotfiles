//go:build !windows

package main

import "os"

func setupConsole() {
	// No-op for Unix systems, as they attach automatically
}

func setCtrlCChan(ch chan<- os.Signal) {
	// No-op for Unix systems
}
