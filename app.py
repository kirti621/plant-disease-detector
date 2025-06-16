from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, session, url_for, make_response, flash
from PIL import Image
from flask_cors import CORS
import sqlite3

import json
import datetime
import os
import speech_recognition as sr
from gtts import gTTS
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.vgg16 import preprocess_input
import numpy as np
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import requests
import datetime
import uuid



# === INITIAL SETUP ===
app = Flask(__name__)
app.secret_key = "kisan_ai_saathi_2025_secret_key_123"  

CORS(app)
# Load the model once
model = load_model('plant_disease_model.h5')  
model.summary()  
class_names = ['Apple___Apple_scab', 'Apple___Black_rot','Apple___Cedar_apple_rust' ,'Apple___healthy'] 

# === DATABASE SETUP ===
def init_user_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')
    conn.commit()
    conn.close()

def init_feedbacks_db():
   conn = sqlite3.connect('feedback.db')
   cursor = conn.cursor()
   cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedbacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            text TEXT,
            audio_path TEXT,
            date TEXT
        )
    ''')
   conn.commit()
   conn.close()


# Initialize all databases
init_user_db()
init_feedbacks_db()


# === HOME ===
@app.route('/')
def home():
    return render_template('home.html')



# Upload route
# Load class labels
with open('class_indices.json', 'r') as f:
    class_indices = json.load(f)
    class_labels = {v: k for k, v in class_indices.items()}

# Load disease info
with open('disease_info.json', 'r', encoding='utf-8') as f:
    disease_info = json.load(f)

# Image preprocessing
def preprocess_image(img_path):
    img = image.load_img(img_path, target_size=(224, 224))
    img_array = image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0)
    img_array = img_array / 255.0
    return img_array

# Upload route
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'image' not in request.files:
            flash("कोई फ़ाइल नहीं मिली।", "error")
            return redirect(request.url)

        file = request.files['image']
        if file.filename == '':
            flash("कोई फ़ाइल चयनित नहीं की गई।", "error")
            return redirect(request.url)

        if file:
            filename = file.filename
            filepath = os.path.join('static', filename)
            file.save(filepath)

            img = preprocess_image(filepath)
            prediction = model.predict(img)
            predicted_index = np.argmax(prediction, axis=1)[0]
            confidence = round(float(np.max(prediction)) * 100, 2)
            predicted_class_name = class_labels[predicted_index]

            info = disease_info.get(predicted_class_name, {
                "description": "कोई जानकारी उपलब्ध नहीं।",
                "treatment": "N/A",
                "pesticide": "N/A"
            })

            return render_template('upload.html',
                                   image_path=filepath,
                                   disease_name=predicted_class_name,
                                   confidence=confidence,
                                   description=info["description"],
                                   treatment=info["treatment"],
                                   pesticide=info["pesticide"])

        flash("फ़ाइल अपलोड करते समय त्रुटि हुई।", "error")
        return redirect(request.url)

    return render_template('upload.html')

# === SIGNUP ===
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            flash("Signup successful!", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username already exists!", "error")
        conn.close()
    return render_template("signup.html")

# === LOGIN ===
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user'] = username
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials", "error")
    return render_template("login.html")

# === DASHBOARD ===
@app.route('/dashboard')
def dashboard():
    if 'user' in session:
        return render_template("dashboard.html", user=session['user'])
    return redirect(url_for('login'))

# === LOGOUT ===
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# === FEEDBACK PAGE (Short Text) ===
@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        name = request.form.get('name')
        text_feedback = request.form.get('text_feedback')
        voice_feedback = request.files.get('voice_feedback')  # Optional

        if name and text_feedback:
            conn = sqlite3.connect('feedback.db')
            cursor = conn.cursor()
            date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            audio_path = ''
            if voice_feedback and voice_feedback.filename != '':
                audio_folder = 'static/voice_feedbacks'
                os.makedirs(audio_folder, exist_ok=True)
                audio_path = os.path.join(audio_folder, voice_feedback.filename)
                voice_feedback.save(audio_path)

            cursor.execute(
                'INSERT INTO feedbacks (name, text, audio_path, date) VALUES (?, ?, ?, ?)',
                (name, text_feedback, audio_path, date)
            )
            conn.commit()
            conn.close()
            return render_template('thank_you.html')

        else:
            return render_template('feedback.html', error="कृपया नाम और संदेश दोनों भरें।")

    return render_template('feedback.html')

# for show feedback on the admin

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///feedback.db'
db = SQLAlchemy(app)

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    feedback_text = db.Column(db.Text)

# Run once in Python terminal to create the DB:
# >>> from app import db
# >>> db.create_all()
with app.app_context():
    db.create_all()

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    try:
        name = request.form.get('name')
        feedback_text = request.form.get('text')
        if not name or not feedback_text:
             return render_template('feedback.html', success=False, message="Please fill out all fields.")
  
        new_feedback = Feedback(name=name, feedback_text=feedback_text)
        db.session.add(new_feedback)
        db.session.commit()
        return render_template('feedback.html', success=True, message="Thank you for your feedback!")
    
    except Exception as e:
        print(f"Error: {e}")
        return render_template('feedback.html', success=False, message="Something went wrong.")

@app.route('/admin')
def admin_feedback():
    all_feedback = Feedback.query.all()
    return render_template('admin.html', feedbacks=all_feedback)

# === KRISHI CALENDAR ===
@app.route('/krishi-calendar')
def krishi_calendar():
    return render_template('krishi_calendar.html')

# === SERVE STATIC FILES ===#
@app.route('/static/<path:filename>')
def serve_static_file(filename):
    return send_from_directory('static', filename)

# === offline PWA support ===#
@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/static/service-worker.js')
def service_worker():
    return send_from_directory('static', 'service-worker.js')

# === THANK YOU PAGE ===
@app.route('/thank_you')
def thank_you():
    return "<h2>धन्यवाद! आपकी प्रतिक्रिया प्राप्त हो गई है।</h2>"

@app.route('/assistant')
def assistant():
    return render_template('assistant.html')





# === RUN APP ===
if __name__ == "__main__":
 os.makedirs("static/responses", exist_ok=True)
 app.run(debug=True)
