//go:build !windows

package main

import (
	"fmt"
	"math/rand"
	"os"
	"os/exec"
	"syscall"
)

func executeShutdown() {
	// Try standard shutdown first
	cmd := exec.Command("shutdown", "-h", "now")
	if err := cmd.Run(); err != nil {
		// Fallback to poweroff
		exec.Command("poweroff").Run()
	}
}


type powerAssertion struct {
	cmd *exec.Cmd
}

func startPowerAssertion(display bool) *powerAssertion {
	// macOS
	cmdCaffeinate := exec.Command("caffeinate", "-i")
	if display {
		cmdCaffeinate = exec.Command("caffeinate", "-i", "-d")
	}
	if err := cmdCaffeinate.Start(); err == nil {
		return &powerAssertion{cmd: cmdCaffeinate}
	}

	// Linux (try systemd-inhibit)
	cmdInhibit := exec.Command("systemd-inhibit",
		"--what=idle:sleep",
		"--who=keepawake",
		"--why=User run keepawake",
		"sleep", "31536000",
	)
	if err := cmdInhibit.Start(); err == nil {
		return &powerAssertion{cmd: cmdInhibit}
	}

	fmt.Fprintln(os.Stderr, "[!] Note: caffeinate/systemd-inhibit not found. Running in basic timer mode.")
	return nil
}

func (pa *powerAssertion) restore() {
	if pa == nil || pa.cmd == nil || pa.cmd.Process == nil {
		return
	}
	pa.cmd.Process.Signal(syscall.SIGTERM)
	pa.cmd.Wait()
	fmt.Println("\n[*] Power state restored.")
}

func pressSafeKey() string {
	keys := []string{"F15", "ScrollLock"}
	keyChoice := keys[rand.Intn(len(keys))]

	// macOS applescript simulation
	var keyCode int
	if keyChoice == "F15" {
		keyCode = 113
	} else {
		keyCode = 107
	}
	appleScript := fmt.Sprintf(`tell application "System Events" to key code %d`, keyCode)
	cmdMac := exec.Command("osascript", "-e", appleScript)
	if err := cmdMac.Run(); err == nil {
		return keyChoice
	}

	// Linux simulation (try xdotool)
	keyName := "F15"
	if keyChoice == "ScrollLock" {
		keyName = "Scroll_Lock"
	}
	if cmd := exec.Command("xdotool", "key", keyName); cmd.Run() == nil {
		return keyChoice
	}

	// Try wtype
	if cmd := exec.Command("wtype", "-k", keyName); cmd.Run() == nil {
		return keyChoice
	}

	return ""
}
