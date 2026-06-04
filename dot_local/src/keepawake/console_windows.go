//go:build windows

package main

import (
	"syscall"
	"unsafe"
)

var (
	modkernel32               = syscall.NewLazyDLL("kernel32.dll")
	procGetConsoleProcessList = modkernel32.NewProc("GetConsoleProcessList")
	procGetConsoleWindow      = modkernel32.NewProc("GetConsoleWindow")

	moduser32      = syscall.NewLazyDLL("user32.dll")
	procShowWindow = moduser32.NewProc("ShowWindow")
)

const swHide = 0

func setupConsole() {
	// Check if we were double-clicked (only us in the console process list)
	var list [2]uint32
	r, _, _ := procGetConsoleProcessList.Call(uintptr(unsafe.Pointer(&list[0])), 2)
	if r == 1 {
		// Only 1 process in the console (us). Hide the spawned console window.
		hwnd, _, _ := procGetConsoleWindow.Call()
		if hwnd != 0 {
			procShowWindow.Call(hwnd, uintptr(swHide))
		}
	}
}
