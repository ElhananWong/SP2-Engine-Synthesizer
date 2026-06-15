from flask import Flask, request, render_template
import subprocess
import os
import uuid

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/process", methods=["POST"])
def process():
    file = request.files["midi_file"]

    filename = f"{uuid.uuid4()}.mid"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    result = subprocess.run(
        ["python", "generator.py", filepath],
        capture_output=True,
        text=True
    )

    return f"<pre>{result.stdout}</pre><pre>{result.stderr}</pre>"