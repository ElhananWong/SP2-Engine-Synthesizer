from flask import Flask, request, render_template
import subprocess
import os
import sys
import uuid

app = Flask(__name__)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(SCRIPT_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    file = request.files["midi_file"]
    loop = "loop" in request.form
    normalize = "normalize" in request.form

    filename = f"{uuid.uuid4()}.mid"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    command = [sys.executable, "generator.py", filepath]
    if loop:
        command.append("--loop")
    if normalize:
        command.append("--normalize")

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=SCRIPT_DIR
    )

    return render_template(
        "results.html",
        output=result.stdout,
        errors=result.stderr,
        loop=loop,
        normalize=normalize,
        success=result.returncode == 0
    )
