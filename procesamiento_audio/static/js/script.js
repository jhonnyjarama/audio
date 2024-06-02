const audioContext = new (window.AudioContext || window.webkitAudioContext)();
document.addEventListener('DOMContentLoaded', () => {

    const fileInput1 = document.getElementById('file1');
    const playButton1 = document.getElementById('play-button-1');
    const volumeSlider1 = document.getElementById('volume-slider-1');

    const fileInput2 = document.getElementById('file2');
    const playButton2 = document.getElementById('play-button-2');
    const volumeSlider2 = document.getElementById('volume-slider-2');

    const mixButton = document.getElementById('mix-button');
    const playMixedButton = document.getElementById('play-mixed-button');
    const mixedVolumeSlider = document.getElementById('volume-slider-mixed');
    const saveButtonMixed = document.getElementById('save-mixed-button');

    let audioBuffer1, audioBuffer2, mixedAudioBuffer;
    let gainNodes = { file1: null, file2: null, mixed: null };

    fileInput1.addEventListener('change', () => {
        readAudioFile(fileInput1.files[0], (buffer) => {
            audioBuffer1 = buffer;
            playButton1.disabled = false;
            volumeSlider1.disabled = false;
            handleFileChange(fileInput1, 'file1');
        });
    });

    fileInput2.addEventListener('change', () => {
        readAudioFile(fileInput2.files[0], (buffer) => {
            audioBuffer2 = buffer;
            playButton2.disabled = false;
            volumeSlider2.disabled = false;
            handleFileChange(fileInput2, 'file2');
        });
    });

    playButton1.addEventListener('click', () => {
        if (audioBuffer1) {
            playAudioBuffer(audioBuffer1, 'file1');
        } else {
            alert('Primero debes cargar un archivo de audio.');
        }
    });

    playButton2.addEventListener('click', () => {
        if (audioBuffer2) {
            playAudioBuffer(audioBuffer2, 'file2');
        } else {
            alert('Primero debes cargar un archivo de audio.');
        }
    });

    playMixedButton.addEventListener('click', () => {
        if (mixedAudioBuffer) {
            mixedAudioBuffer=mixAudioBuffers(audioBuffer1, audioBuffer2);
            playAudioBuffer(mixedAudioBuffer, 'mixed');
        } else {
            alert('Primero debes mezclar los archivos de audio.');
        }
    });

   

    volumeSlider1.addEventListener('input', () => adjustVolume('file1'));
    volumeSlider2.addEventListener('input', () => adjustVolume('file2'));
    mixedVolumeSlider.addEventListener('input', () => adjustVolume('mixed'));

    mixButton.addEventListener('click', () => {
        if (audioBuffer1 && audioBuffer2) {
            mixedAudioBuffer=mixAudioBuffers(audioBuffer1, audioBuffer2);
            /*playAudioBuffer(mixedAudioBuffer, 'mixed');*/
            handleMix();
        }
    });

    saveButtonMixed.addEventListener('click', () => {
        if (mixedAudioBuffer) {
            saveAudioBuffer(mixedAudioBuffer, 'mezcla.wav');
        } else {
            alert('Primero debes mezclar los archivos de audio.');
        }
    });

    function handleFileChange(input, fileId) {
        if (input.files.length > 0) {
            readAudioFile(input.files[0], (buffer) => {
                if (fileId === 'file1') {
                    audioBuffer1 = buffer;
                    playButton1.disabled = false;
                    volumeSlider1.disabled = false;
                } else {
                    audioBuffer2 = buffer;
                    playButton2.disabled = false;
                    volumeSlider2.disabled = false;
                }
    
                // Borrar gráficos anteriores
                clearGraphs(fileId);
    
                const formData = new FormData();
                formData.append(fileId, input.files[0]);
    
                // Eliminar el audio temporal al cargar un nuevo archivo (en cualquier input)
                fetch('/delete_temp_audio', { method: 'GET' }) // Realiza una solicitud GET para eliminar el audio temporal
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            console.log('Audio temporal eliminado');
                        } else {
                            console.error('Error al eliminar audio temporal:', data.error);
                        }
                    })
                    .catch(error => console.error('Error en la solicitud de eliminación:', error))
                    .finally(() => {
                        // Enviar la solicitud para generar los gráficos después de eliminar el audio temporal
                        fetch(`/generate_graphs?fileId=${fileId}`, { method: 'POST', body: formData })
                            .then(response => response.json())
                            .then(data => {
                                if (data.error) {
                                    console.error('Error generando gráficos:', data.error);
                                } else {
                                    clearGraphs(fileId);
                                    displayGraphs(data, fileId);
                                }
                            })
                            .catch(error => console.error('Error generando gráficos:', error));
                    });
            });
        }
    }
    

    


    const filtro = document.getElementById('filter-button');


    function handleMix() {
        if (audioBuffer1 && audioBuffer2) {
            // Deshabilitar controles de mezcla mientras se procesa
            playMixedButton.disabled = true;
            mixedVolumeSlider.disabled = true;
            saveButtonMixed.disabled = true;
    
            // Borrar gráficos anteriores de la mezcla
            clearGraphs('mixed');
    
            const formData = new FormData();
             // Convertir los AudioBuffers a WAV y agregarlos al FormData
             formData.append('file1', fileInput1.files[0]);
             formData.append('file2', fileInput2.files[0]);
             
             console.log('Datos enviados al servidor:', formData.get('file1'), formData.get('file2')); // Imprime los archivos
    
            fetch('/generate_graphs?fileId=mixed', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error('Error generando gráficos:', data.error);
                } else {
                    console.log('Gráficos de mezcla generados:', data);
                    displayGraphs(data, 'mixed');
    
                    // Cargar el audio mezclado desde el archivo temporal si la ruta está presente
                    if (data.mixed_audio_path) {
                        loadMixedAudio(data.mixed_audio_path); 
                    }
                    filtro.disabled = false;
                }
    
                // Habilitar botones después de procesar (incluso si hay error)
                playMixedButton.disabled = false;
                mixedVolumeSlider.disabled = false;
                saveButtonMixed.disabled = false;
                filtro.disabled = false;
            })
            .catch(error => {
                console.error('Error generando gráficos:', error);
                // Habilitar controles en caso de error
                playMixedButton.disabled = false;
                mixedVolumeSlider.disabled = false;
                saveButtonMixed.disabled = false;
                filtro.disabled = false;
            });
        } else {
            alert('Primero debes cargar ambos archivos de audio.');
        }
        
    }

    // Nueva función para cargar el audio mezclado desde el archivo
    function loadMixedAudio(audioPath) {
        fetch(audioPath)
            .then(response => response.arrayBuffer())
            .then(arrayBuffer => {
                audioContext.decodeAudioData(arrayBuffer, (buffer) => {
                    mixedAudioBuffer = buffer;
                    playMixedButton.disabled = false;
                    mixedVolumeSlider.disabled = false;
                    saveButtonMixed.disabled = false;
                });
            })
            .catch(error => console.error('Error al cargar audio mezclado:', error));
    }
    
    
    
    
    function clearGraphs(fileId) {
        const graphContainerId = fileId === 'mixed' ? 'graphs-mixed' : `graphs-audio${fileId.replace('file', '')}`;
        const graphContainer = document.getElementById(graphContainerId);
        if (graphContainer) {
            while (graphContainer.firstChild) {
                graphContainer.removeChild(graphContainer.firstChild);
            }
        }
    }
    
    
    function displayGraphs(data, fileId) {
        const graphContainerId = fileId === 'mixed' ? 'graphs-mixed' : `graphs-audio${fileId.replace('file', '')}`;
        const graphContainer = document.getElementById(graphContainerId);
    
        // Limpiar gráficos anteriores
        while (graphContainer.firstChild) {
            graphContainer.removeChild(graphContainer.firstChild);
        }
    
        // Crear y mostrar los nuevos gráficos
        for (const graphType in data.graph_urls) { // Iterar sobre graph_urls
            const imgElement = document.createElement('img');
            imgElement.src = data.graph_urls[graphType] + '?t=' + Date.now(); // Usar el valor de graph_urls[graphType] como URL
            imgElement.alt = graphType;
            imgElement.style.width = 'calc(50% - 10px)'; 
            imgElement.style.height = 'auto';
            imgElement.style.marginBottom = '10px'; 
            graphContainer.appendChild(imgElement);
        }
    }
    
    


    function readAudioFile(file, callback) {
        const reader = new FileReader();
        reader.readAsArrayBuffer(file);
        reader.onloadend = () => {
            audioContext.decodeAudioData(reader.result, callback);
        };
    }


    function playAudioBuffer(buffer, fileId) {
        const source = audioContext.createBufferSource();
        const gainNode = audioContext.createGain();
        source.buffer = buffer;
        gainNodes[fileId] = gainNode;

        adjustVolume(fileId);
        
        source.connect(gainNode);
        gainNode.connect(audioContext.destination);
        source.start(0);
    }

    
    function adjustVolume(fileId) {
        const volume = document.getElementById(`volume-slider-${fileId === 'file1' ? '1' : fileId === 'file2' ? '2' : 'mixed'}`).value / 100;
        if (gainNodes[fileId]) {
            gainNodes[fileId].gain.value = volume;
        }
    }

    function mixAudioBuffers(buffer1, buffer2) {
        const outputBuffer = audioContext.createBuffer(1, Math.max(buffer1.length, buffer2.length), buffer1.sampleRate);
        const outputData = outputBuffer.getChannelData(0);
        const inputData1 = buffer1.getChannelData(0);
        const inputData2 = buffer2.getChannelData(0);

        for (let i = 0; i < inputData1.length; i++) {
            outputData[i] = inputData1[i];
        }
        for (let i = 0; i < inputData2.length; i++) {
            outputData[i] += inputData2[i];
        }

        return outputBuffer;
    }

    function saveAudioBuffer(buffer, filename) {
        const context = new (window.AudioContext || window.webkitAudioContext)();
        const wavData = audioBufferToWav(buffer);
        const blob = new Blob([wavData], { type: 'audio/wav' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }

    function audioBufferToWav(buffer) {
        const numOfChan = buffer.numberOfChannels;
        const length = buffer.length * numOfChan * 2 + 44;
        const bufferArray = new ArrayBuffer(length);
        const view = new DataView(bufferArray);
        const channels = [];
        let offset = 0;
        let pos = 0;
    
        // Escribir el encabezado WAVE
        setUint32(0x46464952); // "RIFF"
        setUint32(length - 8); // longitud del archivo - 8
        setUint32(0x45564157); // "WAVE"
    
        setUint32(0x20746d66); // chunk "fmt "
        setUint32(16); // longitud = 16
        setUint16(1); // PCM (no comprimido)
        setUint16(numOfChan);
        setUint32(buffer.sampleRate);
        setUint32(buffer.sampleRate * 2 * numOfChan); // bytes promedio por segundo
        setUint16(numOfChan * 2); // align del bloque
        setUint16(16); // 16 bits (hardcoded en este demo)
    
        setUint32(0x61746164); // chunk "data"
        setUint32(length - pos - 4); // longitud del chunk
    
        // Escribir los datos intercalados
        for (let i = 0; i < buffer.numberOfChannels; i++)
            channels.push(buffer.getChannelData(i));
    
        while (pos < length) {
            for (let i = 0; i < numOfChan; i++) {
                // intercalar canales
                let sample = Math.max(-1, Math.min(1, channels[i][offset])); // clamp
                sample = (0.5 + sample < 0 ? sample * 32768 : sample * 32767) | 0; // escalar a int de 16 bits
                view.setInt16(pos, sample, true); // escribir muestra de 16 bits
                pos += 2;
            }
            offset++; // siguiente muestra de origen
        }
    
        function setUint16(data) {
            view.setUint16(pos, data, true);
            pos += 2;
        }
    
        function setUint32(data) {
            view.setUint32(pos, data, true);
            pos += 4;
        }
    
        return bufferArray;
    }


});
