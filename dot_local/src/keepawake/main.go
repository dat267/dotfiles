package main

import (
	"flag"
	"fmt"
	"math/rand"
	"os"
	"os/signal"
	"runtime"
	"syscall"
	"time"
)

var version = "dev"

func main() {
	// Setup console environment (hide window if double-clicked on Windows, no-op elsewhere)
	setupConsole()

	versionFlag := flag.Bool("version", false, "Print version")
	systemOnlyFlag := flag.Bool("system-only", false, "Prevent system sleep but allow the display to turn off (Windows/macOS only)")
	timeoutFlag := flag.String("timeout", "", "Exit after specified duration (e.g. 2h30m, 45m, 15s)")
	shutdownFlag := flag.Bool("shutdown", false, "Shutdown the system after the timeout expires (gives 60s warning to react)")

	flag.Usage = func() {
		fmt.Fprintf(flag.CommandLine.Output(), "KeepAwake v%s - Keep computers active with random periodic interactions.\n\n", version)
		fmt.Fprintf(flag.CommandLine.Output(), "Usage:\n")
		fmt.Fprintf(flag.CommandLine.Output(), "  keepawake [flags]\n\n")
		fmt.Fprintf(flag.CommandLine.Output(), "Flags:\n")
		flag.PrintDefaults()
		fmt.Fprintf(flag.CommandLine.Output(), "\nExamples:\n")
		fmt.Fprintf(flag.CommandLine.Output(), "  keepawake -timeout 2h\n")
		fmt.Fprintf(flag.CommandLine.Output(), "      Keep active for 2 hours, then exit.\n\n")
		fmt.Fprintf(flag.CommandLine.Output(), "  keepawake -timeout 45m -shutdown\n")
		fmt.Fprintf(flag.CommandLine.Output(), "      Keep active for 45 minutes, then trigger a shutdown with 60s cancellation warning.\n\n")
		fmt.Fprintf(flag.CommandLine.Output(), "  keepawake -system-only\n")
		fmt.Fprintf(flag.CommandLine.Output(), "      Prevent system sleep, but let the screen turn off (Windows/macOS only).\n\n")
		fmt.Fprintf(flag.CommandLine.Output(), "Platforms & Simulation Actions:\n")
		fmt.Fprintf(flag.CommandLine.Output(), "  - Windows: Uses SetThreadExecutionState and user32 key events (VK_F15 / VK_SCROLL).\n")
		fmt.Fprintf(flag.CommandLine.Output(), "  - macOS:   Uses caffeinate and osascript simulated key codes.\n")
		fmt.Fprintf(flag.CommandLine.Output(), "  - Linux:   Uses systemd-inhibit, xdotool, or wtype key simulation.\n")
	}

	flag.Parse()

	if *versionFlag {
		fmt.Println(version)
		return
	}

	var timeoutChan <-chan time.Time
	if *timeoutFlag != "" {
		dur, err := time.ParseDuration(*timeoutFlag)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error: Invalid timeout duration %q: %v\n", *timeoutFlag, err)
			return
		}
		timeoutChan = time.After(dur)
	}

	rand.Seed(time.Now().UnixNano())

	display := !*systemOnlyFlag
	assertion := startPowerAssertion(display)
	defer assertion.restore()

	// Intercept signals for graceful termination
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	fmt.Printf("[*] Starting keep-awake (System: %s, Display Keep-Alive: %v)\n", runtime.GOOS, display)
	if *timeoutFlag != "" {
		fmt.Printf("[*] Timeout enabled: will run for %s\n", *timeoutFlag)
		if *shutdownFlag {
			fmt.Println("[*] Shutdown action enabled: will shut down the machine after timeout.")
		}
	}
	fmt.Printf("[*] Press Ctrl+C to stop and allow system to sleep normally.\n\n")

	startTime := time.Now()
	spinner := []string{"|", "/", "-", "\\"}
	spinnerIdx := 0

	lastPressTime := time.Now()
	nextPressDelay := time.Duration(rand.Intn(31)+30) * time.Second // Random delay between 30 and 60 seconds

	var lastKeySent string
	var lastKeySentTime time.Time

	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-sigChan:
			fmt.Println("\n\n[*] Stopping keep-awake...")
			return
		case <-timeoutChan:
			fmt.Println("\n\n[*] Timeout reached!")
			if *shutdownFlag {
				triggerShutdownCountdown(sigChan)
			}
			return
		case <-ticker.C:
			currentTime := time.Now()

			// Check if we need to send key press
			if currentTime.Sub(lastPressTime) >= nextPressDelay {
				sentKey := pressSafeKey()
				if sentKey != "" {
					lastKeySent = sentKey
					lastKeySentTime = currentTime
				}
				lastPressTime = currentTime
				nextPressDelay = time.Duration(rand.Intn(31)+30) * time.Second
			}

			// Format elapsed time
			elapsed := currentTime.Sub(startTime)
			hours := int(elapsed.Hours())
			minutes := int(elapsed.Minutes()) % 60
			seconds := int(elapsed.Seconds()) % 60

			keyStatus := ""
			if lastKeySent != "" && currentTime.Sub(lastKeySentTime) < 5*time.Second {
				keyStatus = fmt.Sprintf(" (sent %s)", lastKeySent)
			}

			// Output status in-place
			fmt.Printf("\r\033[K[ %s ] Active%s | Elapsed time: %02d:%02d:%02d",
				spinner[spinnerIdx%len(spinner)], keyStatus, hours, minutes, seconds)
			spinnerIdx++
		}
	}
}

func triggerShutdownCountdown(sigChan chan os.Signal) {
	fmt.Println("\n\n[!] WARNING: Keep-awake timeout reached! System shutdown has been triggered.")
	fmt.Println("[!] Press Ctrl+C within 60 seconds to cancel the shutdown and keep system active.")

	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for i := 60; i > 0; i-- {
		select {
		case <-sigChan:
			fmt.Println("\n\n[*] Shutdown cancelled by user.")
			return
		case <-ticker.C:
			fmt.Printf("\r\033[KShutting down in %d seconds...", i)
		}
	}

	fmt.Println("\n[*] Shutting down now...")
	executeShutdown()
}
