//go:build windows

package main

import (
	"fmt"
	"math/rand"
	"os"
	"os/exec"
	"syscall"
)

func executeShutdown() {
	cmd := exec.Command("shutdown", "/s", "/f", "/t", "0")
	cmd.Run()
}

var (
	procSetThreadExecutionState = modkernel32.NewProc("SetThreadExecutionState")
	moduser32                   = syscall.NewLazyDLL("user32.dll")
	procKeybdEvent              = moduser32.NewProc("keybd_event")
)

const (
	esContinuous      = 0x80000000
	esSystemRequired  = 0x00000001
	esDisplayRequired = 0x00000002

	keyeventfKeyup = 0x0002
	vkF15          = 0x7E
	vkScroll       = 0x91
)

type powerAssertion struct{}

func startPowerAssertion(display bool) *powerAssertion {
	flags := esContinuous | esSystemRequired
	if display {
		flags |= esDisplayRequired
	}
	r, _, _ := procSetThreadExecutionState.Call(uintptr(flags))
	if r == 0 {
		fmt.Fprintln(os.Stderr, "[!] Warning: SetThreadExecutionState failed.")
	}
	return &powerAssertion{}
}

func (pa *powerAssertion) restore() {
	if pa == nil {
		return
	}
	procSetThreadExecutionState.Call(uintptr(esContinuous))
	fmt.Println("\n[*] Power state restored.")
}

func pressSafeKey() string {
	keys := []string{"F15", "ScrollLock"}
	keyChoice := keys[rand.Intn(len(keys))]

	var vk uintptr
	if keyChoice == "F15" {
		vk = vkF15
	} else {
		vk = vkScroll
	}
	procKeybdEvent.Call(vk, 0, 0, 0)
	procKeybdEvent.Call(vk, 0, keyeventfKeyup, 0)
	return keyChoice
}
