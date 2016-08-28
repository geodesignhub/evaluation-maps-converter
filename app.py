from flask import Flask, url_for
from functools import wraps
from flask import request, Response
import json, geojson, requests
import random,os,sys
import config
from flask import render_template
from werkzeug.utils import secure_filename
import EvaluationConverter

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = 'input'
ALLOWED_EXTENSIONS = set(['zip'])

app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid. Please change it to one
    suitable for your service.
    """
    return username == 'uploads' and password == 'secretpassword'

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.route('/', methods = ['GET'])
def api_root():
    return render_template('home.html')

@app.route('/upload', methods = ['POST'])
@requires_auth
def upload_file():
    op = {}
    if request.method == 'POST':
        if 'file' not in request.files:
            op['msg'] = 'No file part'
        file = request.files['file']

        if file.filename == '':
            op['msg']="No File Selected"

        if not allowed_file(file.filename):
            op['msg']="Incorrect file Extension"
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            op['msg']="File Uploaded successfully"
            
            myEvalConverter = EvaluationConverter.ConvertEvaluation()
            gj, status = myEvalConverter.convert()
            op['gj'] = gj
            op['status'] = status
            myEvalConverter.cleanDirectories()

    return Response(json.dumps(op), status=200, mimetype='application/json')

if __name__ == '__main__':
    app.debug = True
    port = int(os.environ.get("PORT", 5001))
    app.run(port =5001)
