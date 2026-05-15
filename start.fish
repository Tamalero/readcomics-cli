#!/usr/bin/env fish

set SCRIPT_DIR (dirname (realpath (status filename)))
cd $SCRIPT_DIR

set LOG_FILE $SCRIPT_DIR/readcomics.log
set VERBOSE 0
set NO_HEADLESS 0

for arg in $argv
    switch $arg
        case -v --verbose
            set VERBOSE 1
        case --no-headless
            set NO_HEADLESS 1
        case -h --help
            echo "Usage: start.fish [-v|--verbose] [--no-headless]"
            echo "  -v, --verbose    Show full install output and enable debug logging"
            echo "  --no-headless    Show the Playwright browser window (for debugging)"
            exit 0
    end
end

function log_msg
    set msg "["(date '+%Y-%m-%d %H:%M:%S')"] $argv"
    echo $msg | tee -a $LOG_FILE
end

log_msg "=== ReadComics startup (verbose=$VERBOSE) ==="

# ── Venv ──────────────────────────────────────────────────────────────────────

if not test -d venv
    log_msg "Creating virtual environment..."
    if test $VERBOSE -eq 1
        python3 -m venv venv 2>&1 | tee -a $LOG_FILE
    else
        python3 -m venv venv >> $LOG_FILE 2>&1
    end
    if test $status -ne 0
        log_msg "ERROR: Failed to create virtual environment."
        exit 1
    end
end

source venv/bin/activate.fish

# ── Requirements ──────────────────────────────────────────────────────────────

log_msg "Installing requirements..."
if test $VERBOSE -eq 1
    pip install -r requirements.txt 2>&1 | tee -a $LOG_FILE
else
    pip install -q -r requirements.txt >> $LOG_FILE 2>&1
end

if test $status -ne 0
    log_msg "ERROR: pip install failed — check $LOG_FILE for details."
    exit 1
end

# ── Playwright browser ────────────────────────────────────────────────────────

log_msg "Ensuring Playwright Firefox browser is installed..."
if test $VERBOSE -eq 1
    playwright install firefox 2>&1 | tee -a $LOG_FILE
else
    playwright install firefox >> $LOG_FILE 2>&1
end

# ── Launch GUI ────────────────────────────────────────────────────────────────

log_msg "Launching GUI..."

set GUI_ARGS
if test $VERBOSE -eq 1
    set GUI_ARGS $GUI_ARGS --verbose
end
if test $NO_HEADLESS -eq 1
    set GUI_ARGS $GUI_ARGS --no-headless
end

if test $VERBOSE -eq 1
    python gui.py $GUI_ARGS 2>&1 | tee -a $LOG_FILE
else
    python gui.py $GUI_ARGS 2>> $LOG_FILE
end

set EXIT_CODE $status
if test $EXIT_CODE -ne 0
    log_msg "ERROR: GUI exited with code $EXIT_CODE — check $LOG_FILE for details."
end
exit $EXIT_CODE
