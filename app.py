from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, flash, get_flashed_messages
import os
import logging
import json
import uuid
from werkzeug.utils import secure_filename
from langchain_helpers import load_documents_from_folder, preprocess_text, split_documents, setup_embeddings_and_vector_store
from flask_cors import CORS

# Assuming all previously defined functions are saved in a separate file named `langchain_helpers.py`
# and are imported here:
from langchain_helpers import setup_environment, load_documents_from_folder, preprocess_text, split_documents, setup_embeddings_and_vector_store, setup_langchain, format_docs

logging.basicConfig(level=logging.DEBUG)

DATA_DIR = 'data'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'csv'}

# Make sure the sessions folder exists
sessions_dir = "sessions"
if not os.path.exists(sessions_dir):
    os.makedirs(sessions_dir)

app = Flask(__name__)
CORS(app)
app.config['DATA_DIR'] = DATA_DIR
app.secret_key = 'cde'  # Set a secret key for session management

# Initialize the environment and load documents at startup
setup_environment()
documents = load_documents_from_folder("data")
for document in documents:
    document.page_content = preprocess_text(document.page_content)
docs = split_documents(documents)
qdrant = setup_embeddings_and_vector_store(docs)
llm_chain = setup_langchain()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def serve_chat_app():
    return send_from_directory('static', 'index.html')

# Loop over the session qhids to provide to the combobox
@app.route('/sessions', methods=['GET'])
def list_sessions():
    qhids = [f.split('.')[0] for f in os.listdir(sessions_dir) if os.path.isfile(os.path.join(sessions_dir, f))]
    return jsonify(qhids)

@app.route('/session/<qhid>', methods=['GET'])
def get_session_history(qhid):
    session_file_path = os.path.join(sessions_dir, f"{qhid}.json")
    if os.path.exists(session_file_path):
        with open(session_file_path, 'r') as file:
            session_history = json.load(file)
        return jsonify(session_history)
    else:
        return jsonify({"error": "Session not found"}), 404

@app.route('/files')
def files():
    files = os.listdir(app.config['DATA_DIR'])
    return render_template('file_management.html', files=files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['DATA_DIR'], filename))
        return redirect(url_for('files'))

@app.route('/delete/<filename>')
def delete_file(filename):
    file_path = os.path.join(app.config['DATA_DIR'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    return redirect(url_for('files'))

@app.route('/query', methods=['POST'])
def process_query():
    data = request.json
    query = data.get('query')
    qhid = data.get('qhid')  # Query History ID

    if not query:
        return jsonify({"error": "No query provided"}), 400

    if not qhid:
        qhid = str(uuid.uuid4())

    session_file_path = os.path.join(sessions_dir, f"{qhid}.json")

    # Initialize or load session history
    if os.path.exists(session_file_path):
        with open(session_file_path, 'r') as file:
            session_history = json.load(file)
    else:
        session_history = {"qhid": qhid, "interactions": []}

    # Build historical context from session history
    historical_context = ""
    for interaction in session_history["interactions"]:
        historical_context += "Q: " + interaction["query"] + " A: " + interaction["response"] + " "

    # Generate RAG context for the current query
    rag_context = format_docs(qdrant, query)

    # Combine historical context with RAG context
    combined_context = historical_context + " " + rag_context

    try:
        response = llm_chain.invoke(input={"question": query, "context": combined_context})

        # Append the new query-response pair to session history
        session_history["interactions"].append({"query": query, "response": response['text']})

        # Save the updated session history
        with open(session_file_path, 'w') as file:
            json.dump(session_history, file)

        return jsonify({"response": response['text'], "qhid": qhid})
    except Exception as e:
        logging.error(f"Error processing query: {e}")
        return jsonify({"error": "Failed to process query"}), 500
    
@app.route('/reprocess', methods=['POST'])
def reprocess_files():
    try:
        # Indicate start of processing
        flash("Processing started. Please wait...")

        # Execute the processing steps as described
        documents = load_documents_from_folder("data")
        for document in documents:
            document.page_content = preprocess_text(document.page_content)
        docs = split_documents(documents)
        flash("Processing started. Please wait for completion.", 'info')
        global qdrant  # Assuming qdrant is used elsewhere in your app and should be updated globally
        qdrant = setup_embeddings_and_vector_store(docs)
        flash("Processing completed successfully.", 'info')
    except Exception as e:
        flash(f"An error occurred: {str(e)}", 'error')

    return redirect(url_for('processing_status'))

@app.route('/processing_status')
def processing_status():
    return render_template('processing_status.html')

@app.route('/config', methods=['GET', 'POST'])
def config_page():
    if request.method == 'POST':
        # Update the config.json based on the selection
        new_config = request.json
        update_config(new_config)
        return jsonify({"success": True})
    elif request.headers.get('Accept') == 'application/json':
        # Return the config as JSON for AJAX calls
        return jsonify(load_config())
    else:
        # Serve the config.html template for direct navigations
        return render_template('config.html', config=load_config())

def load_config():
    with open('config.json', 'r') as file:
        config = json.load(file)
    return config

def update_config(new_config):
    with open('config.json', 'w') as file:
        json.dump(new_config, file, indent=4)

if __name__ == "__main__":
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    app.run(debug=True, host='0.0.0.0', port=5000)
