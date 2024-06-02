document.addEventListener('DOMContentLoaded', () => {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();

    const fileInputMezcla = document.getElementById('mezcla');
    const playButtonMezcla = document.getElementById('play-button');
    const volumeSliderMezcla = document.getElementById('volume-slider-1');
    const filterTypeSelect = document.getElementById('filter-type');
    const cutoffFrequency1Input = document.getElementById('cutoff-frequency1');
    const cutoffFrequency2Input = document.getElementById('cutoff-frequency2');
    const filterOrderInput = document.getElementById('filter-order');
    const applyFilterButton = document.getElementById('apply-filter-button');
    const playFilteredButton = document.getElementById('play-filtered-button');
    const saveFilteredButton = document.getElementById('save-filtered-button');

    let audioBufferMezcla;
    let filteredAudioBuffer;
    let gainNodes = {};

    fileInputMezcla.addEventListener('change', () => {
        handleFileChange(fileInputMezcla);
    });

    playButtonMezcla.addEventListener('click', () => {
        if (audioBufferMezcla) {
            audioContext.resume().then(() => {
                playAudioBuffer(audioBufferMezcla, 'mezcla');
            });
        } else {
            alert('Primero debes cargar un archivo de audio.');
        }
    });

    volumeSliderMezcla.addEventListener('input', () => adjustVolume('mezcla'));

    applyFilterButton.addEventListener('click', async () => {
        const filterType = filterTypeSelect.value;
        const cutoffFrequency1 = parseFloat(cutoffFrequency1Input.value);
        const cutoffFrequency2 = (filterType === 'bandpass' || filterType === 'bandstop')
            ? parseFloat(cutoffFrequency2Input.value)
            : null;
        const filterOrder = parseInt(filterOrderInput.value, 10);

        const cutoffFrequency = cutoffFrequency2 ? [cutoffFrequency1, cutoffFrequency2] : [cutoffFrequency1];

        const response = await fetch('/apply_filter', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                filterType,
                cutoffFrequency,
                filterOrder
            })
        });

        const result = await response.json();

        if (result.error) {
            alert(result.error);
            return;
        }

        const { graph_urls_filtered } = result;

        displayGraphs(graph_urls_filtered, 'filtered');
        playFilteredButton.disabled = false;
        saveFilteredButton.disabled = false;
    });

    playFilteredButton.addEventListener('click', async () => {
        const response = await fetch('/get_filtered_audio');
        if (!response.ok) {
            alert('No se pudo obtener el audio filtrado.');
            return;
        }
        const arrayBuffer = await response.arrayBuffer();
        audioContext.decodeAudioData(arrayBuffer, (buffer) => {
            filteredAudioBuffer = buffer;
            playAudioBuffer(filteredAudioBuffer, 'filtered');
        });
    });

    saveFilteredButton.addEventListener('click', () => {
        window.location.href = '/get_filtered_audio';
    });

    function handleFileChange(input) {
        if (input.files.length > 0) {
            const file = input.files[0];
            readAudioFile(file, (buffer) => {
                audioBufferMezcla = buffer;
                playButtonMezcla.disabled = false;
                volumeSliderMezcla.disabled = false;
                // Enviar el archivo al servidor para almacenarlo en la carpeta temporal
                const formData = new FormData();
                formData.append('audio', file);

                fetch('/upload_audio', {
                    method: 'POST',
                    body: formData
                }).then(response => response.json())
                  .then(data => {
                      if (data.error) {
                          alert(data.error);
                      } else {
                          console.log('Audio cargado y almacenado en la carpeta temporal.');
                      }
                  });
            });
        }
    }

    filterTypeSelect.addEventListener('change', () => {
        const filterType = filterTypeSelect.value;
        cutoffFrequency2Input.parentElement.style.display = 
            (filterType === 'bandpass' || filterType === 'bandstop') ? 'block' : 'none';
        document.getElementById('cutoff-help').style.display = 
            (filterType === 'bandpass' || filterType === 'bandstop') ? 'block' : 'none';
    });

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
        const volumeSlider = document.getElementById(`volume-slider-1`);
        if (volumeSlider) {
            const volume = volumeSlider.value / 100;
            if (gainNodes[fileId]) {
                gainNodes[fileId].gain.value = volume;
            }
        }
    }

    function displayGraphs(graphUrls, prefix) {
        const graphContainer = document.getElementById(`graphs-${prefix}`);

        graphContainer.innerHTML = '';

        Object.keys(graphUrls).forEach(key => {
            const img = document.createElement('img');
            img.src = graphUrls[key];
            img.alt = key;
            img.style.width = 'calc(50% - 10px)';
            img.style.marginBottom = '10px';
            graphContainer.appendChild(img);
        });

        // Mostrar el gráfico de respuesta en frecuencia
        const filterResponsePlot = document.getElementById('graph-filtered-response');
        filterResponsePlot.src = graphUrls['filter_response'];
    }

    function saveAudioBuffer(buffer, filename) {
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

        setUint32(0x46464952);
        setUint32(length - 8);
        setUint32(0x45564157);

        setUint32(0x20746d66);
        setUint32(16);
        setUint16(1);
        setUint16(numOfChan);
        setUint32(buffer.sampleRate);
        setUint32(buffer.sampleRate * 2 * numOfChan);
        setUint16(numOfChan * 2);
        setUint16(16);

        setUint32(0x61746164);
        setUint32(length - pos - 4);

        for (let i = 0; i < buffer.numberOfChannels; i++)
            channels.push(buffer.getChannelData(i));

        while (pos < length) {
            for (let i = 0; i < numOfChan; i++) {
                let sample = Math.max(-1, Math.min(1, channels[i][offset]));
                sample = (0.5 + sample < 0 ? sample * 32768 : sample * 32767) | 0;
                view.setInt16(pos, sample, true);
                pos += 2;
            }
            offset++;
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
