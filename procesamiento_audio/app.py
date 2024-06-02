import numpy as np
import matplotlib
matplotlib.use('Agg')  # Usar el backend Agg
import matplotlib.pyplot as plt
from pydub import AudioSegment
from scipy import signal
import io
from scipy.io import wavfile
from flask import Flask, render_template, request, jsonify, session, send_file, url_for
import os
import time

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'

# Funciones de procesamiento de audio
def load_audio(file_data):
    audio = AudioSegment.from_file(io.BytesIO(file_data))
    audio_array = np.array(audio.get_array_of_samples(), dtype=np.float32)
    if audio.channels == 2:
        audio_array = audio_array.reshape((-1, 2)).mean(axis=1)
    audio_array /= np.max(np.abs(audio_array))  # Normalizar
    print(f"Loaded audio with {len(audio_array)} samples.")
    return audio_array, audio.frame_rate


def adjust_volume(audio_array, gain_db):
    factor = 10 ** (gain_db / 20)
    return np.clip(audio_array * factor, -1.0, 1.0)

def mix_audios(audio_array1, audio_array2):
    max_length = max(len(audio_array1), len(audio_array2))
    audio_array1 = np.pad(audio_array1, (0, max_length - len(audio_array1)), mode='constant')
    audio_array2 = np.pad(audio_array2, (0, max_length - len(audio_array2)), mode='constant')
    mixed_audio = audio_array1 + audio_array2
    max_amplitude = np.max(np.abs(mixed_audio))  # Encontrar la amplitud máxima
    if max_amplitude > 1.0:
        mixed_audio /= max_amplitude  # Normalizar si es necesario
    return mixed_audio

def apply_butterworth_filter(audio_array, fs, filter_type, cutoff_freq, order):
    nyquist = 0.5 * fs
    normalized_cutoff = np.array(cutoff_freq) / nyquist

    if filter_type not in ['lowpass', 'highpass', 'bandpass', 'bandstop']:
        raise ValueError(f"Invalid filter type: {filter_type}")

    b, a = signal.butter(order, normalized_cutoff, btype=filter_type, analog=False)
    filtered_audio = signal.filtfilt(b, a, audio_array)
    return filtered_audio, b, a

# Funciones para calcular y guardar gráficos
def save_plot(fig, filename):
    fig.savefig(filename)
    print(f"Guardado gráfico en {filename}")  # Mensaje de depuración
    plt.close(fig)

def plot_time_domain(audio_array, fs, title="Señal de Audio en el Dominio del Tiempo"):
    fig, ax = plt.subplots()
    t = np.linspace(0, len(audio_array) / fs, num=len(audio_array))
    ax.plot(t, audio_array)
    ax.set_title(title)
    ax.set_xlabel("Tiempo [s]")
    ax.set_ylabel("Amplitud")
    return fig

def plot_spectrogram(audio_array, fs, title="Espectrograma"):
    fig, ax = plt.subplots()
    nperseg = 1024
    noverlap = nperseg // 2
    nfft = 2048
    
    frequencies, times, Sxx = signal.spectrogram(audio_array, fs, nperseg=nperseg, noverlap=noverlap, nfft=nfft)
    Sxx = np.where(Sxx == 0, np.nan, Sxx)
    
    ax.pcolormesh(times, frequencies, 10 * np.log10(Sxx), shading='gouraud')
    ax.set_title(title)
    ax.set_ylabel("Frecuencia [Hz]")
    ax.set_xlabel("Tiempo [s]")
    ax.set_ylim(0, fs // 2)
    return fig

def plot_fft(audio_array, fs, title="Transformada de Fourier"):
    fig, ax = plt.subplots()
    fft_values = np.abs(np.fft.fft(audio_array))
    fft_frequencies = np.fft.fftfreq(len(audio_array), 1/fs)
    half_length = len(fft_values) // 2

    fft_values = fft_values[:half_length] / np.max(fft_values)
    fft_frequencies = fft_frequencies[:half_length]

    max_freq = 1500
    indices = fft_frequencies < max_freq

    ax.plot(fft_frequencies[indices], fft_values[indices])
    ax.set_title(title)
    ax.set_xlabel("Frecuencia [Hz]")
    ax.set_ylabel("Amplitud Normalizada")
    ax.set_xlim(0, max_freq)
    ax.set_ylim(0, 1)
    return fig

def plot_amplitude_histogram(audio_array, title="Histograma de Amplitud"):  # Eliminar el parámetro fs
    fig, ax = plt.subplots()
    bins = 100
    ax.hist(audio_array, bins=bins, color='blue', edgecolor='black', alpha=0.7)
    ax.set_title(title)
    ax.set_xlabel("Amplitud")
    ax.set_ylabel("Frecuencia")
    ax.set_yscale('log')
    ax.grid(True)
    return fig

def plot_cepstrum(audio_array, title="Cepstrum"):
    fig, ax = plt.subplots()
    complex_spectrum = np.fft.fft(audio_array)
    log_spectrum = np.log(np.abs(complex_spectrum) + np.finfo(float).eps)
    cepstrum = np.fft.ifft(log_spectrum).real
    ax.plot(cepstrum[:len(cepstrum)//2])
    ax.set_title(title)
    ax.set_xlabel("Quefrency")
    ax.set_ylabel("Amplitud")
    ax.set_xlim(0, 125)  # Limitar el eje x para mejor visualización
    ax.grid(True)
    return fig

# Función para calcular el histograma de amplitud
def calculate_amplitude_histogram(audio_array, bins=100):
    hist, bin_edges = np.histogram(audio_array, bins=bins)
    return hist.tolist(), bin_edges.tolist()

# Función para calcular el cepstrum
def calculate_cepstrum(audio_array):
    complex_spectrum = np.fft.fft(audio_array)
    log_spectrum = np.log(np.abs(complex_spectrum) + np.finfo(float).eps)
    cepstrum = np.fft.ifft(log_spectrum).real
    return cepstrum[:len(cepstrum)//2].tolist()

# Función para calcular el espectro de frecuencias
def calculate_frequency_spectrum(audio_array, fs):
    fft_values = np.abs(np.fft.fft(audio_array)) / len(audio_array)
    fft_frequencies = np.fft.fftfreq(len(audio_array), 1/fs)
    return fft_frequencies[:len(fft_frequencies)//2].tolist(), (fft_values[:len(fft_values)//2] * 2).tolist()


def plot_frequency_spectrum(audio_array, title="Espectro de Frecuencias"):  # Elimina el parámetro fs
    fig, ax = plt.subplots()
    fft_values = np.abs(np.fft.fft(audio_array))
    
    # Aquí debes calcular fft_frequencies sin usar fs, por ejemplo, asumiendo una frecuencia de muestreo estándar.
    # fft_frequencies = np.fft.fftfreq(len(audio_array), 1/fs) 
    sample_rate = 44100
    fft_frequencies = np.fft.fftfreq(len(audio_array), 1/sample_rate) 


    fft_values = fft_values / np.max(fft_values)
    ax.plot(fft_frequencies[:len(fft_frequencies)//2], fft_values[:len(fft_values)//2])
    ax.set_title(title)
    ax.set_xlabel("Frecuencia [Hz]")
    ax.set_ylabel("Amplitud")
    ax.set_xlim(0, 1100)
    ax.set_ylim(0, 1)
    ax.grid(True)
    return fig



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload')
def upload():
    return render_template('upload.html')


@app.route('/filter')
def filter():
    return render_template('filter.html')

def delete_previous_graphs(file_id):
    images_dir = os.path.join('static', 'images', 'upload', file_id)  # Ruta completa a la carpeta del audio

    for filename in os.listdir(images_dir):
        if filename.startswith(f"{file_id}_"):
            file_path = os.path.join(images_dir, filename)
            try:
                os.remove(file_path)
                print(f"Imagen eliminada: {file_path}")
            except FileNotFoundError:
                print(f"No se encontró la imagen: {file_path}")

# Rutas para procesar audio y generar gráficos
@app.route('/generate_graphs', methods=['POST'])
def generate_graphs():
    session.clear()  # Borrar la sesión al inicio de la función
    try:
        file_id = request.args.get('fileId')

        # Inicializar mixed_audio_data y fs
        mixed_audio_data = None
        fs = None

        if file_id == 'mixed':
            # Obtener los archivos originales para la mezcla
            file1 = request.files.get('file1')
            file2 = request.files.get('file2')
            print(f"Archivos recibidos: file1={file1}, file2={file2}")  # Verificar si se reciben los archivos

            if not file1 or not file2:
                return jsonify({'error': 'Faltan archivos para la mezcla'}), 400

            # Cargar y mezclar los audios
            audio_array1, fs1 = load_audio(file1.read())
            audio_array2, fs2 = load_audio(file2.read())

            

            # Verificar si las frecuencias de muestreo son iguales
            if fs1 != fs2:
                return jsonify({'error': 'Las frecuencias de muestreo de los archivos deben ser iguales'}), 400
            fs = fs1

            audio_array = mix_audios(audio_array1, audio_array2)

            # Convertir el arreglo NumPy a bytes y crear un AudioSegment a partir de ellos
            with io.BytesIO() as f:
                wavfile.write(f, fs, audio_array.astype(np.int16))
                f.seek(0)
                mixed_audio = AudioSegment.from_wav(f)  # Asignar mixed_audio aquí
                mixed_audio = mixed_audio.normalize()
            
            print(f"Longitud audio_array1: {len(audio_array1)}")  # Imprimir longitudes para verificar
            print(f"Longitud audio_array2: {len(audio_array2)}")

            print(f"audio_array: {audio_array}")  # Imprimir el arreglo mezclado

            # Guardar el audio mezclado como un archivo temporal
            mixed_audio_path = f'static/temp/mixed_audio.wav'
            mixed_audio.export(mixed_audio_path, format="wav")
            print(f"Audio mezclado guardado en: {mixed_audio_path}")  # Confirmar que se guardó

        else:
            # Obtener el archivo individual
            file = request.files.get(file_id)
            if not file:
                return jsonify({'error': f'Archivo {file_id} no encontrado.'}), 400

            file_data = file.read()
            audio_array, fs = load_audio(file_data)
        
        

        # Asignar la carpeta correcta según el file_id
        folder = file_id  # 'file1', 'file2' o 'mixed'

        # Generar nombres de archivo únicos con marca de tiempo y carpeta
        timestamp = int(time.time())
        filenames = {
            'time_domain': f'static/images/upload/{folder}/{file_id}_time_domain_{timestamp}.png',
            'spectrogram': f'static/images/upload/{folder}/{file_id}_spectrogram_{timestamp}.png',
            'fft': f'static/images/upload/{folder}/{file_id}_fft_{timestamp}.png',
            'amplitude_histogram': f'static/images/upload/{folder}/{file_id}_amplitude_histogram_{timestamp}.png',
            'cepstrum': f'static/images/upload/{folder}/{file_id}_cepstrum_{timestamp}.png',
            'frequency_spectrum': f'static/images/upload/{folder}/{file_id}_frequency_spectrum_{timestamp}.png'
        }

        # Asegurarse de que la carpeta de imágenes exista
        images_dir = os.path.join('static', 'images', 'upload', folder)
        os.makedirs(images_dir, exist_ok=True)

        # Eliminar gráficos anteriores del archivo en la carpeta correspondiente
        delete_previous_graphs(file_id)

        # Guardar todos los gráficos, verificando si las funciones existen
        for graph_type, filename in filenames.items():
            plot_function_name = f'plot_{graph_type}'
            if plot_function_name in globals():
                plot_function = globals()[plot_function_name]
                if graph_type in ['amplitude_histogram', 'cepstrum', 'frequency_spectrum']:
                    save_plot(plot_function(audio_array), filename)
                else:
                    save_plot(plot_function(audio_array, fs), filename)
            else:
                print(f"Error: la función {plot_function_name} no está definida.")

        # Construir URLs completas para los gráficos
        graph_urls = {
            graph_type: url_for('static', filename=filename.replace('static/', ''))
            for graph_type, filename in filenames.items()
        }

        return jsonify({
            'graph_urls': graph_urls,
            'mixed_audio_path': mixed_audio_path if file_id == 'mixed' else None
        })

    except Exception as e:
        print(f"Error en generate_graphs: {e}")
        return jsonify({'error': str(e)}), 500
    

@app.route('/mix_audios', methods=['POST'])
def mix_audios_route():
    try:
        file1 = request.files['audio1']
        file2 = request.files['audio2']

        audio_array1, fs1 = load_audio(file1.read())
        audio_array2, fs2 = load_audio(file2.read())

        print(f"Audio 1: {len(audio_array1)} samples, Audio 2: {len(audio_array2)} samples")

        if fs1 != fs2:
            return jsonify({'error': 'Las frecuencias de muestreo de los archivos deben ser iguales'}), 400

        mixed_audio_array = mix_audios(audio_array1, audio_array2)

        print(f"Mixed audio has {len(mixed_audio_array)} samples.")

        # Convertir el arreglo NumPy a bytes y crear un AudioSegment a partir de ellos
        with io.BytesIO() as f:
            wavfile.write(f, fs1, mixed_audio_array.astype(np.int16))
            f.seek(0)
            mixed_audio = AudioSegment.from_wav(f)
            mixed_audio = mixed_audio.normalize()
            mixed_audio_path = f'static/temp/mixed_audio.wav'
            mixed_audio.export(mixed_audio_path, format="wav")

        return jsonify({'mixed_audio_path': mixed_audio_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

@app.route('/generate_filtered_graphs', methods=['POST'])
def generate_filtered_graphs():
    try:
        filtered_audio_data = session.get('filtered_audio_data')
        mixed_fs = session.get('mixed_fs')

        if filtered_audio_data is None or mixed_fs is None:
            return jsonify({'error': 'No hay datos de audio filtrado disponibles.'}), 400

        filtered_audio_array = np.frombuffer(filtered_audio_data, dtype=np.int16) / 32768.0

        timestamp = int(time.time())
        filenames_filtered = {
            'time_domain': f'static/images/filtro/filtered_time_domain_{timestamp}.png',
            'spectrogram': f'static/images/filtro/filtered_spectrogram_{timestamp}.png',
            'fft': f'static/images/filtro/filtered_fft_{timestamp}.png',
            'amplitude_histogram': f'static/images/filtro/filtered_amplitude_histogram_{timestamp}.png',
            'cepstrum': f'static/images/filtro/filtered_cepstrum_{timestamp}.png',
            'frequency_spectrum': f'static/images/filtro/filtered_frequency_spectrum_{timestamp}.png'
        }

        images_dir = os.path.join('static', 'images', 'filtro')
        os.makedirs(images_dir, exist_ok=True)

        save_plot(plot_time_domain(filtered_audio_array, mixed_fs), filenames_filtered['time_domain'])
        save_plot(plot_spectrogram(filtered_audio_array, mixed_fs), filenames_filtered['spectrogram'])
        save_plot(plot_fft(filtered_audio_array, mixed_fs), filenames_filtered['fft'])
        save_plot(plot_amplitude_histogram(filtered_audio_array), filenames_filtered['amplitude_histogram'])
        save_plot(plot_cepstrum(filtered_audio_array), filenames_filtered['cepstrum'])
        save_plot(plot_frequency_spectrum(filtered_audio_array, mixed_fs), filenames_filtered['frequency_spectrum'])

        graph_urls_filtered = {
            graph_type: url_for('static', filename=filename.replace('static/', ''))
            for graph_type, filename in filenames_filtered.items()
        }

        return jsonify({
            'graph_urls_filtered': graph_urls_filtered
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


    
@app.route('/delete_temp_audio')
def delete_temp_audio():
    try:
        temp_dir = os.path.join('static', 'temp')
        for filename in os.listdir(temp_dir):
            if filename.startswith('mixed_audio_'):
                os.remove(os.path.join(temp_dir, filename))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# ... (otras importaciones y funciones)
from pydub import AudioSegment
import io

@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    file = request.files['audio']
    if not file:
        return jsonify({'error': 'No se recibió ningún archivo.'}), 400
    
    temp_dir = os.path.join('static', 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    filename = f"uploaded_{int(time.time())}.wav"
    filepath = os.path.join(temp_dir, filename)
    
    file.save(filepath)
    
    session['audio_filepath'] = filepath
    
    return jsonify({'message': 'Audio cargado y almacenado en el servidor.', 'filepath': filepath})


@app.route('/apply_filter', methods=['POST'])
def apply_filter():
    try:
        data = request.json
        filter_type = data.get('filterType')
        cutoff_freq = data.get('cutoffFrequency')
        order = data.get('filterOrder')

        audio_filepath = session.get('audio_filepath')

        if not audio_filepath or not os.path.exists(audio_filepath):
            return jsonify({'error': 'No hay datos de audio mezclado disponibles para filtrar'}), 400

        mixed_audio = AudioSegment.from_file(audio_filepath, format="wav")
        mixed_audio_array = np.array(mixed_audio.get_array_of_samples()) / 32768.0

        mixed_fs = mixed_audio.frame_rate
        filtered_audio_array, b, a = apply_butterworth_filter(mixed_audio_array, mixed_fs, filter_type, cutoff_freq, order)

        w, h = signal.freqz(b, a, worN=2000)

        timestamp = int(time.time())
        filenames_filtered = {
            'time_domain': f'static/images/upload/filtro/filtered_time_domain_{timestamp}.png',
            'spectrogram': f'static/images/upload/filtro/filtered_spectrogram_{timestamp}.png',
            'fft': f'static/images/upload/filtro/filtered_fft_{timestamp}.png',
            'amplitude_histogram': f'static/images/upload/filtro/filtered_amplitude_histogram_{timestamp}.png',
            'cepstrum': f'static/images/upload/filtro/filtered_cepstrum_{timestamp}.png',
            'frequency_spectrum': f'static/images/upload/filtro/filtered_frequency_spectrum_{timestamp}.png',
            'filter_response': f'static/images/upload/filtro/filter_response_{timestamp}.png'
        }

        images_dir = os.path.join('static', 'images', 'upload', 'filtro')
        os.makedirs(images_dir, exist_ok=True)

        # Eliminar gráficos anteriores
        for filename in os.listdir(images_dir):
            file_path = os.path.join(images_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"No se pudo eliminar {file_path}. Razón: {e}")

        save_plot(plot_time_domain(filtered_audio_array, mixed_fs), filenames_filtered['time_domain'])
        save_plot(plot_spectrogram(filtered_audio_array, mixed_fs), filenames_filtered['spectrogram'])
        save_plot(plot_fft(filtered_audio_array, mixed_fs), filenames_filtered['fft'])
        save_plot(plot_amplitude_histogram(filtered_audio_array), filenames_filtered['amplitude_histogram'])
        save_plot(plot_cepstrum(filtered_audio_array), filenames_filtered['cepstrum'])
        save_plot(plot_frequency_spectrum(filtered_audio_array, mixed_fs), filenames_filtered['frequency_spectrum'])

        # Graficar la respuesta en frecuencia del filtro
        fig, ax = plt.subplots(figsize=(8, 4))
        w, h = signal.freqz(b, a, worN=2000)
        ax.plot(0.5 * mixed_fs * w / np.pi, np.abs(h), 'b')
        ax.set_title(f"Respuesta en Frecuencia del Filtro Butterworth - {filter_type.capitalize()} (Corte: {cutoff_freq}, Orden: {order})")
        ax.set_xlabel("Frecuencia [Hz]")
        ax.set_ylabel("Ganancia")
        ax.grid()
        save_plot(fig, filenames_filtered['filter_response'])

        graph_urls_filtered = {
            graph_type: url_for('static', filename=filename.replace('static/', ''))
            for graph_type, filename in filenames_filtered.items()
        }

        # Guardar el audio filtrado como un archivo temporal
        filtered_audio_path = f'static/temp/filtered_audio_{timestamp}.wav'
        wavfile.write(filtered_audio_path, mixed_fs, (filtered_audio_array * 32767).astype(np.int16))
        session['filtered_audio_path'] = filtered_audio_path

        # Convertir arrays a listas
        filter_response_freqs = (0.5 * mixed_fs * w / np.pi).tolist()
        filter_response_mags = np.abs(h).tolist()

        return jsonify({
            'filterResponse': [filter_response_freqs, filter_response_mags],
            'graph_urls_filtered': graph_urls_filtered
        })

    except Exception as e:
        print(f"Error en apply_filter: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/get_filtered_audio')
def get_filtered_audio():
    filtered_audio_path = session.get('filtered_audio_path')
    if not filtered_audio_path or not os.path.exists(filtered_audio_path):
        return jsonify({'error': 'No hay audio filtrado disponible.'}), 404

    return send_file(filtered_audio_path, mimetype='audio/wav', as_attachment=True, download_name="audio_filtrado.wav")




@app.route('/save_mixed_audio')
def save_mixed_audio():
    try:
        mixed_audio_data = np.array(session.get('mixed_audio_data'))
        mixed_fs = session.get('mixed_fs')

        if mixed_audio_data is None or mixed_fs == 0:
            return jsonify({'error': 'No hay audio mezclado para guardar.'}), 400

        mixed_audio_data = (mixed_audio_data * 32767).astype(np.int16)
        file_obj = io.BytesIO()
        wavfile.write(file_obj, mixed_fs, mixed_audio_data)
        file_obj.seek(0)

        return send_file(file_obj, mimetype="audio/wav", as_attachment=True, download_name="mezcla.wav")
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    
@app.route('/get_mixed_audio')
def get_mixed_audio():
    mixed_audio_path = 'static/temp/mixed_audio.wav'  # Ruta del archivo temporal
    if not os.path.exists(mixed_audio_path):
        return jsonify({'error': 'No hay audio mezclado disponible.'}), 404

    # Lee el contenido del archivo en bytes
    with open(mixed_audio_path, 'rb') as f:
        mixed_audio_data = f.read()

    return send_file(io.BytesIO(mixed_audio_data), mimetype='audio/wav')


if __name__ == '__main__':
    app.run(debug=True)
