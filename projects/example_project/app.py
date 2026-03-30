"""Simple Flask API — example project for CrewAI Command Center demo."""

from flask import Flask, jsonify, request

app = Flask(__name__)

# In-memory storage (for demo purposes)
tasks = []
next_id = 1


@app.route("/tasks", methods=["GET"])
def get_tasks():
    return jsonify(tasks)


@app.route("/tasks", methods=["POST"])
def create_task():
    global next_id
    data = request.json
    if not data or "title" not in data:
        return jsonify({"error": "Field 'title' is required"}), 400
    task = {"id": next_id, "title": data["title"], "done": False}
    tasks.append(task)
    next_id += 1
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        return jsonify({"error": "Not found"}), 404
    data = request.json
    task.update(data)
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    global tasks
    tasks = [t for t in tasks if t["id"] != task_id]
    return "", 204


if __name__ == "__main__":
    app.run(debug=True)
