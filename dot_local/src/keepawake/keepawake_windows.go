//go:build windows

package main

import (
	"fmt"
	"math/rand"
	"syscall"
	"time"
)

const (
	esContinuous      = 0x80000000
	esSystemRequired  = 0x00000001
	esDisplayRequired = 0x00000002
)

func startInhibit() (func(), error) {
	kernel32 := syscall.NewLazyDLL("kernel32.dll")
	setThreadExecutionState := kernel32.NewProc("SetThreadExecutionState")

	ret, _, err := setThreadExecutionState.Call(uintptr(esContinuous | esSystemRequired | esDisplayRequired))
	if ret == 0 {
		return nil, fmt.Errorf("failed to set thread execution state: %w", err)
	}

	user32 := syscall.NewLazyDLL("user32.dll")
	keybdEvent := user32.NewProc("keybd_event")

	done := make(chan struct{})

	go func() {
		for {
			duration := time.Duration(30+rand.Intn(31)) * time.Second
			select {
			case <-time.After(duration):
				_, _, _ = keybdEvent.Call(0x7E, 0, 0, 0)
				_, _, _ = keybdEvent.Call(0x7E, 0, 2, 0)
			case <-done:
				return
			}
		}
	}()

	cleanup := func() {
		close(done)
		_, _, _ = setThreadExecutionState.Call(uintptr(esContinuous))
	}

	return cleanup, nil
}
