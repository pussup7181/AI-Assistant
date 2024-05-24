from flask import Flask, request, jsonify, render_template
import requests
import base64
from pydub import AudioSegment
from io import BytesIO
import os
import logging

app = Flask(__name__)

# Configuration variables
ulca_base_url = 'https://meity-auth.ulcacontrib.org'
model_pipeline_endpoint = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
user_id = 'cfae7f756a424bfeaaaa00ba44a98ae7'
api_key = '398316fb83-444f-4fd5-801b-4e69221c1d12'
pipeline_id = '64392f96daac500b55c543cd'

# Function to convert base64 string back to audio file
def base64_to_audio(base64_string):
    audio_data = base64.b64decode(base64_string)
    audio = AudioSegment.from_file(BytesIO(audio_data), format="wav")
    return audio

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_audio', methods=['POST'])
def process_audio():
    try:
        data = request.json
        audio_base64 = data['audio']
        source_lang = data['sourceLang']
        target_lang = data['targetLang']

        # Convert base64 audio to AudioSegment
        audio = base64_to_audio(audio_base64)
        audio_path = 'uploads/input_audio.wav'
        audio.export(audio_path, format='wav')

        # Convert audio file to base64
        with open(audio_path, 'rb') as f:
            audio_base64 = base64.b64encode(f.read()).decode('utf-8')

        # Step 1: Send request to get pipeline details
        response = requests.post(
            model_pipeline_endpoint,
            json={
                "pipelineTasks": [
                    {"taskType": "asr", "config": {"language": {"sourceLanguage": source_lang}}},
                    {"taskType": "translation", "config": {"language": {"sourceLanguage": source_lang, "targetLanguage": target_lang}}},
                    {"taskType": "tts", "config": {"language": {"sourceLanguage": target_lang}}}
                ],
                "pipelineRequestConfig": {"pipelineId": pipeline_id}
            },
            headers={'Content-Type': 'application/json', 'ulcaApiKey': api_key, 'userID': user_id}
        )

        if response.status_code != 200:
            app.logger.error(f"Pipeline request failed: {response.status_code} - {response.text}")
            return jsonify({'error': 'Failed to get pipeline details'}), 500

        pipeline_response = response.json()
        app.logger.debug(f"Pipeline Response: {response.json()}")
        callback_url = pipeline_response['pipelineInferenceAPIEndPoint']['callbackUrl']
        asr_service_id = pipeline_response['pipelineResponseConfig'][0]['config'][0]['serviceId']
        nmt_service_id = pipeline_response['pipelineResponseConfig'][1]['config'][0]['serviceId']
        tts_service_id = pipeline_response['pipelineResponseConfig'][2]['config'][0]['serviceId']

        compute_authorization_key = pipeline_response['pipelineInferenceAPIEndPoint']['inferenceApiKey']['name']
        compute_call_authorization_value = pipeline_response['pipelineInferenceAPIEndPoint']['inferenceApiKey']['value']
        app.logger.debug(asr_service_id)
        app.logger.debug(f"Callback URL: {callback_url}")
        app.logger.debug(f"Authorization Key: {compute_authorization_key}, Authorization Value: {compute_call_authorization_value}")

        # Step 2: Send audio data for processing
        payload = {
        "pipelineTasks": [
            {
                "taskType": "asr",
                "config": {
                    "language": {
                        "sourceLanguage": source_lang
                    },
                    "serviceId": asr_service_id,
                    "audioFormat": "wav",
                    "samplingRate": 16000
                }
            },
            {
                "taskType": "translation",
                "config": {
                    "language": {
                        "sourceLanguage": source_lang,
                        "targetLanguage": target_lang
                    },
                    "serviceId": nmt_service_id
                }
            },
            {
                "taskType": "tts",
                "config": {
                    "language": {
                        "sourceLanguage": target_lang
                    },
                    "serviceId": tts_service_id,
                    "gender": "female",
                    "samplingRate": 16000
                }
            }
        ],
        "inputData": {
            "audio": [
                {
                    "audioContent": audio_base64
                }
            ]
        }
    }

        app.logger.debug(f"Payload: {payload}")

        response = requests.post(
            callback_url,
            json=payload,
            headers={'Content-Type': 'application/json', 'ulcaApiKey': api_key, 'userID': user_id, compute_authorization_key: compute_call_authorization_value}
        )

        if response.status_code != 200:
            app.logger.error(f"Audio processing failed: {response.status_code} - {response.text}")
            return jsonify({'error': 'Failed to process audio'}), 500

        processed_audio_base64 = response.json()['pipelineResponse'][2]['audio'][0]['audioContent']
        return jsonify({'audio': processed_audio_base64})

    except Exception as e:
        app.logger.error(f"Exception occurred: {str(e)}")
        return jsonify({'error': 'An error occurred while processing audio'}), 500


if __name__ == '__main__':
    # Set up logging
    logging.basicConfig(filename='app.log', level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')
    app.run(debug=True)
