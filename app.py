import os
import sqlite3
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # Límite de 50MB

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS entrevistas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rut TEXT NOT NULL,
            nombre_entrevistado TEXT,
            audio_path TEXT,
            transcripcion TEXT,
            informe TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_audio():
    rut = request.form.get('rut')
    if not rut:
        return jsonify({'error': 'El RUT es obligatorio'}), 400

    if 'audio' not in request.files:
        return jsonify({'error': 'No se subió ningún archivo de audio'}), 400

    file = request.files['audio']
    if file.filename == '':
        return jsonify({'error': 'Archivo sin nombre'}), 400

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    try:
        with open(file_path, "rb") as audio_file:
            transcript_obj = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        transcripcion = transcript_obj.text

        prompt = f"""
        Analiza la siguiente transcripción de una entrevista. 
        Genera un informe estructurado que contenga:
        1. Nombre estimado del entrevistado.
        2. Resumen ejecutivo.
        3. Puntos clave y temas tratados.
        4. Evaluación del perfil del entrevistado.

        Transcripción:
        {transcripcion}
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        informe = response.choices[0].message.content

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO entrevistas (rut, nombre_entrevistado, audio_path, transcripcion, informe)
            VALUES (?, ?, ?, ?, ?)
        ''', (rut, "Entrevistado", file_path, transcripcion, informe))
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'rut': rut, 'informe': informe})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/buscar', methods=['GET'])
def buscar_por_rut():
    rut = request.args.get('rut', '').strip()
    if not rut:
        return jsonify({'error': 'Debe ingresar un RUT'}), 400

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT rut, nombre_entrevistado, transcripcion, informe, fecha FROM entrevistas WHERE rut LIKE ?', (f'%{rut}%',))
    rows = cursor.fetchall()
    conn.close()

    resultados = []
    for row in rows:
        resultados.append({
            'rut': row[0],
            'nombre': row[1],
            'transcripcion': row[2],
            'informe': row[3],
            'fecha': row[4]
        })

    return jsonify({'resultados': resultados})

if __name__ == '__main__':
    app.run(debug=True)