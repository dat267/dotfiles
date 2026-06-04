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
	// Try to attach to parent console (Windows specific, no-op elsewhere)
	attachConsole()

	versionFlag := flag.Bool("version", false, "Print version")
	systemOnlyFlag := flag.Bool("system-only", false, "Prevent system sleep but allow the display to turn off (Windows/macOS only)")
	timeoutFlag := flag.String("timeout", "", "Exit after specified duration (e.g. 2h30m, 45m, 15s)")
	shutdownFlag := flag.Bool("shutdown", false, "Shutdown the system after the timeout expires (gives 60s warning to react)")
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
	fmt.Println("[*] Press Ctrl+C to stop and allow system to sleep normally.\n")

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
