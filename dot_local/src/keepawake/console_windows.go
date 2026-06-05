//go:build windows

package main

import (
	"os"
	"syscall"
)

var (
	modkernel32               = syscall.NewLazyDLL("kernel32.dll")
	procAttachConsole         = modkernel32.NewProc("AttachConsole")
	procSetConsoleCtrlHandler = modkernel32.NewProc("SetConsoleCtrlHandler")
)

const attachParentProcess = 0xFFFFFFFF

// Global channel to notify main loop of Ctrl+C
var (
	ctrlCChan  chan<- os.Signal
	ctrlCCount int
)

func consoleCtrlHandler(ctrlType uintptr) uintptr {
	switch ctrlType {
	case 0, 1: // CTRL_C_EVENT, CTRL_BREAK_EVENT
		ctrlCCount++
		if ctrlCCount > 1 {
			// On subsequent Ctrl+C, let the OS handle it (terminates immediately)
			return 0
		}
		if ctrlCChan != nil {
			select {
			case ctrlCChan <- os.Interrupt:
				// Sent successfully
			default:
				// Channel full, do not block
			}
		}
		return 1 // Handled (gives the app a chance to clean up gracefully)
	}
	return 0 // Not handled
}

func setupConsole() {
	// Try to attach to parent console (if run from a terminal)
	r, _, _ := procAttachConsole.Call(uintptr(attachParentProcess))
	if r != 0 {
		// Redirect standard input, output, and error handles to the attached console
		if h, err := syscall.GetStdHandle(syscall.STD_OUTPUT_HANDLE); err == nil {
			os.Stdout = os.NewFile(uintptr(h), "/dev/stdout")
		}
		if h, err := syscall.GetStdHandle(syscall.STD_ERROR_HANDLE); err == nil {
			os.Stderr = os.NewFile(uintptr(h), "/dev/stderr")
		}
		if h, err := syscall.GetStdHandle(syscall.STD_INPUT_HANDLE); err == nil {
			os.Stdin = os.NewFile(uintptr(h), "/dev/stdin")
		}

		// Register control handler so Ctrl+C works for GUI application attached to console
		cb := syscall.NewCallback(consoleCtrlHandler)
		procSetConsoleCtrlHandler.Call(cb, 1)
	}
}

func setCtrlCChan(ch chan<- os.Signal) {
	ctrlCChan = ch
}
