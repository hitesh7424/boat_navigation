# autonomous_controller.py
# Central controller to orchestrate autonomous task sequences
# Exposes REST API to trigger predefined behaviors like dumping, cleaning, diagnostics

from flask import Flask, request, jsonify
import threading
import dumping_sequence
#import cleaning_cycle   # To be created
#import diagnostic_mode   # To be created

app = Flask(__name__)
PORT = 8010

# Task registry (can be extended)
TASKS = {
    "dump": dumping_sequence.run_sequence,
    #"clean": cleaning_cycle.run_sequence,
    #"diagnose": diagnostic_mode.run_sequence,
}

status = {
    "running": False,
    "last_task": None,
    "log": []
}

# Run task in background
def launch_task(name):
    def run():
        status["running"] = True
        status["last_task"] = name
        status["log"].append(f"Started: {name}")
        try:
            TASKS[name]()
            status["log"].append(f"Completed: {name}")
        except Exception as e:
            status["log"].append(f"Error in {name}: {str(e)}")
        status["running"] = False
    threading.Thread(target=run, daemon=True).start()

@app.route("/run/<task>", methods=["POST"])
def run_task(task):
    if task not in TASKS:
        return jsonify({"error": "Invalid task"}), 400
    if status["running"]:
        return jsonify({"error": "Task already running"}), 409
    launch_task(task)
    return jsonify({"message": f"Task {task} launched"})

@app.route("/status")
def get_status():
    return jsonify(status)

if __name__ == "__main__":
    print(f"🧠 Autonomous controller running at http://0.0.0.0:{PORT}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
