# app.py
from flask import Flask, render_template, request
from pipeline import process_plate

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def index():
    table_html = None
    error = None

    if request.method == "POST":
        uploaded = request.files.get("dataset")

        if not uploaded or uploaded.filename == "":
            error = "Please choose an .xlsx file first."
        else:
            try:
                # Run the pipeline directly on the uploaded file
                df_results = process_plate(uploaded, reference_well=None)
                table_html = df_results.to_html(
                    classes="table table-striped table-sm",
                    index=False,
                    float_format=lambda x: f"{x:.4f}"
                )
            except Exception as e:
                error = f"Error processing file: {e}"

    return render_template("index.html", table_html=table_html, error=error)


if __name__ == "__main__":
    # Start local web server
    app.run(debug=True)
