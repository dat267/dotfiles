package main

import (
	"errors"
	"flag"
	"fmt"
	"math/rand/v2"
	"os"
	"os/exec"
	"runtime"
	"time"

	"github.com/go-vgo/robotgo"
)

const (
	minBaseDelay   = 30
	randomRange    = 45
	shortDelayMin  = 5
	shortDelayMax  = 15
	longDelayMin   = 75
	longDelayMax   = 60
	scrollLockWait = 50 * time.Millisecond
)

func nextInterval() time.Duration {
	base := minBaseDelay + rand.IntN(randomRange)
	if rand.Float64() < 0.15 {
		base = shortDelayMin + rand.IntN(shortDelayMax)
	} else if rand.Float64() > 0.85 {
		base = longDelayMin + rand.IntN(longDelayMax)
	}
	return time.Duration(base) * time.Second
}

func executeInteraction() string {
	if rand.Float64() < 0.35 {
		robotgo.KeyTap("scroll_lock")
		time.Sleep(scrollLockWait)
		robotgo.KeyTap("scroll_lock")
		return " (sent ScrollLock x2)"
	}
	robotgo.KeyTap("f15")
	return " (sent F15)"
}

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, "Error:", err)
		os.Exit(1)
	}
}

func run(args []string) error {
	fs := flag.NewFlagSet("keepawake", flag.ContinueOnError)
	timeoutFlag := fs.String("t", "", "Exit after specified duration (e.g. 2h, 45m, 15s)")
	shutdownFlag := fs.Bool("s", false, "Shutdown the system after the timeout expires")

	if err := fs.Parse(args); err != nil {
		return err
	}

	if *shutdownFlag && *timeoutFlag == "" {
		return errors.New("cannot use -s (shutdown) without specifying a timeout duration via -t")
	}

	startTime := time.Now()
	var timeoutChan <-chan time.Time

	if *timeoutFlag != "" {
		dur, err := time.ParseDuration(*timeoutFlag)
		if err != nil {
			return fmt.Errorf("invalid timeout %q", *timeoutFlag)
		}
		timeoutChan = time.After(dur)

		stopTime := startTime.Add(dur).Format("15:04:05")
		if *shutdownFlag {
			fmt.Printf("Keep-awake active until %s (with system shutdown).\nPress Ctrl+C to stop.\n", stopTime)
		} else {
			fmt.Printf("Keep-awake active until %s.\nPress Ctrl+C to stop.\n", stopTime)
		}
	} else {
		fmt.Println("Keep-awake active indefinitely.\nPress Ctrl+C to stop.")
	}

	lastPressTime := time.Now()
	nextPressDelay := nextInterval()

	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	var keyStatus string

	for {
		select {
		case <-timeoutChan:
			fmt.Println("\nTimeout reached.")
			if *shutdownFlag {
				return triggerShutdownCountdown()
			}
			return nil
		case <-ticker.C:
			currentTime := time.Now()

			if currentTime.Sub(lastPressTime) >= nextPressDelay {
				keyStatus = executeInteraction()
				lastPressTime = currentTime
				nextPressDelay = nextInterval()
			}

			elapsed := currentTime.Sub(startTime)
			hours := int(elapsed.Hours())
			minutes := int(elapsed.Minutes()) % 60
			seconds := int(elapsed.Seconds()) % 60

			fmt.Printf("\rElapsed: %02d:%02d:%02d%s\033[K", hours, minutes, seconds, keyStatus)
		}
	}
}

func triggerShutdownCountdown() error {
	fmt.Println("\nWARNING: Shutdown triggered. Press Ctrl+C to cancel.")

	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for i := 60; i > 0; i-- {
		<-ticker.C
		fmt.Printf("\rShutting down in %d seconds...\033[K", i)
	}

	fmt.Println("\nShutting down now...")
	var cmd *exec.Cmd
	if runtime.GOOS == "windows" {
		cmd = exec.Command("shutdown", "/s", "/t", "0")
	} else {
		cmd = exec.Command("shutdown", "-h", "now")
	}
	return cmd.Run()
}
