package system

import (
	"log"
	"os/exec"
	"strings"
	"time"
)

// stopVerifyTimeout caps how long we wait for hermes-server to actually leave the active state after `systemctl stop`.
const stopVerifyTimeout = 5 * time.Second

// isServiceActive returns true if `systemctl is-active <unit>` exits 0 (active). All other states (inactive, failed, unknown, activating) are treated as "not active" — safe to wipe.
func isServiceActive(unit string) bool {
	return exec.Command("systemctl", "is-active", "--quiet", unit).Run() == nil
}

// waitForServiceStop polls is-active until the unit is no longer active or the timeout elapses. Returns true if the service is confirmed stopped within the window.
func waitForServiceStop(unit string, timeout time.Duration) bool {
	deadline := time.Now().Add(timeout)
	for {
		if !isServiceActive(unit) {
			return true
		}
		if time.Now().After(deadline) {
			return false
		}
		time.Sleep(200 * time.Millisecond)
	}
}

// hermesWipeDirs are Hermes state dirs we recursively remove on factory reset.
// Surgical wipe (per design): `~/.hermes/` root is preserved except for the
// files in hermesWipeFiles + DB triples — `.env` and `config.yaml` stay so the
// next boot has working defaults after `hermes setup --reset` regenerates them.
var hermesWipeDirs = []string{
	"/root/.hermes/sessions",    // conversation session state
	"/root/.hermes/memories",    // semantic memory store
	"/root/.hermes/tasks",       // background task runs
	"/root/.hermes/subagents",   // subagent history
	"/root/.hermes/checkpoints", // run checkpoints
	"/root/.hermes/logs",        // runtime logs
	"/root/.hermes/.cache",      // cache dir
	"/root/.hermes/cron",        // scheduled jobs
}

// hermesWipeFiles are single files at `~/.hermes/` root we delete. Anything not
// in this list (notably `.env`, `config.yaml`) is preserved.
var hermesWipeFiles = []string{
	"/root/.hermes/SOUL.md",   // agent personality
	"/root/.hermes/auth.json", // auth state
}

// hermesDBBases enumerates SQLite database basenames at `~/.hermes/`. For each
// base, we remove `.db`, `.db-shm`, and `.db-wal` (SQLite WAL companion files
// — leaving them behind would let SQLite resurrect partial state on next open).
var hermesDBBases = []string{
	"/root/.hermes/state",          // gateway state
	"/root/.hermes/kanban",         // task board
	"/root/.hermes/response_store", // response cache for previous_response_id chains
}

// wipeHermesState runs the Hermes reset flow. Unlike openclaw, Hermes has no
// single "reset everything" CLI — flow is:
//  1. hermes setup --reset    (resets config.yaml + scrubs API keys in .env)
//  2. systemctl stop hermes-server  (graceful flush)
//  3. hermes gateway stop     (separate gateway process)
//  4. systemctl disable hermes-server  (no auto-start; SetupAgent re-enables)
//  5. surgical rm: enumerated dirs + files + DB triples (.db + .db-shm + .db-wal)
//
// `~/.hermes/.env` and `~/.hermes/config.yaml` are PRESERVED — `hermes setup
// --reset` resets them in place to defaults, no need to wipe.
func wipeHermesState() {
	// Step 1: hermes setup --reset — resets config.yaml to defaults and scrubs
	// API keys in .env. Run BEFORE stopping the service in case the CLI talks
	// to the running daemon (mirrors `openclaw reset` which expects daemon up).
	log.Printf("[factory-reset/hermes] step 1/5 — hermes setup --reset")
	if out, err := exec.Command("hermes", "setup", "--reset").CombinedOutput(); err != nil {
		log.Printf("[factory-reset/hermes] step 1/5 — hermes setup --reset error: %v — %s", err, strings.TrimSpace(string(out)))
	} else {
		log.Printf("[factory-reset/hermes] step 1/5 — hermes setup --reset done: %s", strings.TrimSpace(string(out)))
	}

	// Step 2: stop hermes-server systemd unit so the server flushes writes.
	log.Printf("[factory-reset/hermes] step 2/5 — systemctl stop hermes-server")
	if out, err := exec.Command("systemctl", "stop", "hermes-server").CombinedOutput(); err != nil {
		log.Printf("[factory-reset/hermes] step 2/5 — stop hermes-server error: %v — %s", err, strings.TrimSpace(string(out)))
	} else {
		log.Printf("[factory-reset/hermes] step 2/5 — hermes-server stop returned ok")
	}
	if waitForServiceStop("hermes-server", stopVerifyTimeout) {
		log.Printf("[factory-reset/hermes] step 2/5 — hermes-server confirmed inactive")
	} else {
		log.Printf("[factory-reset/hermes] step 2/5 — WARNING hermes-server still active after %s — SQLite wipe may race the running daemon",
			stopVerifyTimeout)
	}

	// Step 3: stop hermes gateway (separate process, controlled via hermes CLI
	// not systemctl — per hermes deployment model).
	log.Printf("[factory-reset/hermes] step 3/5 — hermes gateway stop")
	if out, err := exec.Command("hermes", "gateway", "stop").CombinedOutput(); err != nil {
		log.Printf("[factory-reset/hermes] step 3/5 — hermes gateway stop error: %v — %s", err, strings.TrimSpace(string(out)))
	} else {
		log.Printf("[factory-reset/hermes] step 3/5 — hermes gateway stopped")
	}

	// Step 4: disable so the service does NOT auto-start on reboot. SetupAgent
	// re-enables it after onboarding completes, same pattern as openclaw.
	log.Printf("[factory-reset/hermes] step 4/5 — systemctl disable hermes-server")
	if out, err := exec.Command("systemctl", "disable", "hermes-server").CombinedOutput(); err != nil {
		log.Printf("[factory-reset/hermes] step 4/5 — disable hermes-server error: %v — %s", err, strings.TrimSpace(string(out)))
	} else {
		log.Printf("[factory-reset/hermes] step 4/5 — hermes-server disabled")
	}

	// Step 5: surgical wipe. Three buckets — dirs (rm -rf), single files, and
	// SQLite DB triples (.db + .db-shm + .db-wal).
	log.Printf("[factory-reset/hermes] step 5/5 — wiping %d dirs + %d files + %d db triples",
		len(hermesWipeDirs), len(hermesWipeFiles), len(hermesDBBases))

	for _, d := range hermesWipeDirs {
		wipePath("[factory-reset/hermes]", d)
	}

	for _, f := range hermesWipeFiles {
		wipePath("[factory-reset/hermes]", f)
	}

	// SQLite leaves -shm (shared memory) and -wal (write-ahead log) sidecar
	// files. Removing only the .db while leaving -wal lets SQLite reconstruct
	// state on next open, so wipe all three per database.
	for _, base := range hermesDBBases {
		for _, suffix := range []string{".db", ".db-shm", ".db-wal"} {
			wipePath("[factory-reset/hermes]", base+suffix)
		}
	}
}
