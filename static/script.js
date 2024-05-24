const recordButton = document.getElementById('recordButton');
        const status = document.getElementById('status');
        const audioPlayback = document.getElementById('audioPlayback');
        const you = document.getElementById('you');
        const assistant = document.getElementById('assistant');

        recordButton.addEventListener('click', async () => {
            const sourceLang = document.getElementById('sourceLang').value;
            const targetLang = document.getElementById('targetLang').value;

            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                alert('Your browser does not support audio recording.');
                return;
            }

            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 44100 });
            const source = audioContext.createMediaStreamSource(stream);
            const recorder = audioContext.createScriptProcessor(4096, 1, 1);

            let audioData = [];
            recorder.onaudioprocess = event => {
                const channelData = event.inputBuffer.getChannelData(0);
                const buffer = new Int16Array(channelData.length);
                for (let i = 0; i < channelData.length; i++) {
                    buffer[i] = Math.min(1, channelData[i]) * 0x7FFF;
                }
                audioData.push(...buffer);
            };

            source.connect(recorder);
            recorder.connect(audioContext.destination);

            setTimeout(() => {
                recorder.disconnect();
                source.disconnect();

                const wavBuffer = createWavFile(audioData, audioContext.sampleRate);
                const wavBlob = new Blob([wavBuffer], { type: 'audio/wav' });
                const audioUrl = URL.createObjectURL(wavBlob);
                audioPlayback.src = audioUrl;

                const reader = new FileReader();
                reader.readAsDataURL(wavBlob);
                reader.onloadend = () => {
                    const base64String = reader.result.split(',')[1];

                    // Send base64 string to the server
                    fetch('/process_audio', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ audio: base64String, sourceLang, })
                    })
                    .then(response => response.json())
                    .then(data => {
                       
                        if (data.transcription) {
                            const audioUrl = `data:audio/wav;base64,${data.audio}`;
                            audioPlayback.src = audioUrl;
                            audioPlayback.play();
                            status.textContent = 'Recording processed and played back.';
                            you.textContent = data.transcription;
                            assistant.textContent = data.assistant;

                        } else {
                            status.textContent = 'Error processing recording.';
                        }
                        
                    })
                    .catch(error => {
                        console.error('Error processing audio:', error);
                        status.textContent = 'Error processing recording.';
                    });
                };

                stream.getTracks().forEach(track => track.stop());
                status.textContent = 'Recording stopped.';
            }, 5000);

            status.textContent = 'Recording...';
        });

        function createWavFile(audioData, sampleRate) {
            const header = new ArrayBuffer(44);
            const view = new DataView(header);

            const writeString = (view, offset, string) => {
                for (let i = 0; i < string.length; i++) {
                    view.setUint8(offset + i, string.charCodeAt(i));
                }
            };

            writeString(view, 0, 'RIFF');
            view.setUint32(4, 36 + audioData.length * 2, true);
            writeString(view, 8, 'WAVE');
            writeString(view, 12, 'fmt ');
            view.setUint32(16, 16, true);
            view.setUint16(20, 1, true);
            view.setUint16(22, 1, true);
            view.setUint32(24, sampleRate, true);
            view.setUint32(28, sampleRate * 2, true);
            view.setUint16(32, 2, true);
            view.setUint16(34, 16, true);
            writeString(view, 36, 'data');
            view.setUint32(40, audioData.length * 2, true);

            const pcm = new Int16Array(header.byteLength + audioData.length * 2);
            pcm.set(new Int16Array(header), 0);
            pcm.set(audioData, 44 / 2);

            return pcm.buffer;
        }