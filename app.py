from flask import Flask, request, jsonify, render_template
import requests
import base64
from pydub import AudioSegment
from io import BytesIO
import os
from openai import OpenAI

app = Flask(__name__)
OPENAI_API_KEY = 'sk-proj-hCy1WDa6jE1MHyaUFoL6T3BlbkFJdKRSeOdZfjUDlk01AuMb'
client = OpenAI(api_key=OPENAI_API_KEY)

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
                    ],
                "pipelineRequestConfig": {"pipelineId": pipeline_id}
            },
            headers={'Content-Type': 'application/json', 'ulcaApiKey': api_key, 'userID': user_id}
        )

        if response.status_code != 200:
            print(f"Pipeline request failed: {response.status_code} - {response.text}")
            return jsonify({'error': 'Failed to get pipeline details'}), 500

        pipeline_response = response.json()
        #print(f"Pipeline Response: {response.json()}")
        callback_url = pipeline_response['pipelineInferenceAPIEndPoint']['callbackUrl']
        asr_service_id = pipeline_response['pipelineResponseConfig'][0]['config'][0]['serviceId']

        compute_authorization_key = pipeline_response['pipelineInferenceAPIEndPoint']['inferenceApiKey']['name']
        compute_call_authorization_value = pipeline_response['pipelineInferenceAPIEndPoint']['inferenceApiKey']['value']
        print(asr_service_id)
        print(f"Callback URL: {callback_url}")
        print(f"Authorization Key: {compute_authorization_key}, Authorization Value: {compute_call_authorization_value}")

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


        response = requests.post(
            callback_url,
            json=payload,
            headers={'Content-Type': 'application/json', 'ulcaApiKey': api_key, 'userID': user_id, compute_authorization_key: compute_call_authorization_value}
        )
        print(f"Response: {response.json()}")

        if response.status_code != 200:
            print(f"Audio processing failed: {response.status_code} - {response.text}")
            return jsonify({'error': 'Failed to process audio'}), 500
        
        transcribed_audio = response.json()['pipelineResponse'][0]['output'][0]['source']
        chat_reply = chat(transcribed_audio)
        processed_audio = tts(chat_reply, source_lang)
        print(f"User: {transcribed_audio}")
        print(f"Assistant: {chat_reply}")
        #print(f"Audio: {processed_audio}")
        return jsonify({'transcription': transcribed_audio, 'assistant':chat_reply, 'audio':processed_audio})

    except Exception as e:
        print(f"Exception occurred: {str(e)}")
        return jsonify({'error': 'An error occurred while processing audio'}), 500

def chat(prompt):
    try:
        completion = client.chat.completions.create(
            model = 'gpt-4o',
            messages = [
                {"role": "system", "content": "you are a helpful chat assistant. you always give replies in the same language as user asks you"},
                {"role": "user", "content":prompt}
            ]
        )
        #print(completion)
    except Exception as e:
        print(f"Exception occurred in chat: {str(e)}")
        return 'An error occurred while processing audio'
    return completion.choices[0].message.content


def tts(prompt, source_lang):
    try:

        # Step 1: Send request to get pipeline details
        response = requests.post(
            model_pipeline_endpoint,
            json={
                "pipelineTasks": [
                    {"taskType": "tts", "config": {"language": {"sourceLanguage": source_lang}}},
                    ],
                "pipelineRequestConfig": {"pipelineId": pipeline_id}
            },
            headers={'Content-Type': 'application/json', 'ulcaApiKey': api_key, 'userID': user_id}
        )

        if response.status_code != 200:
            print(f"TTS Pipeline request failed: {response.status_code} - {response.text}")
            return jsonify({'error': 'Failed to get tts pipeline details'}), 500

        pipeline_response = response.json()
        #print(f"TTS Pipeline Response: {response.json()}")
        callback_url = pipeline_response['pipelineInferenceAPIEndPoint']['callbackUrl']
        tts_service_id = pipeline_response['pipelineResponseConfig'][0]['config'][0]['serviceId']

        compute_authorization_key = pipeline_response['pipelineInferenceAPIEndPoint']['inferenceApiKey']['name']
        compute_call_authorization_value = pipeline_response['pipelineInferenceAPIEndPoint']['inferenceApiKey']['value']
        print(tts_service_id)
        print(f"Callback URL: {callback_url}")
        print(f"Authorization Key: {compute_authorization_key}, Authorization Value: {compute_call_authorization_value}")

        # Step 2: Send chat data for processing
        payload = {
        "pipelineTasks": [
            {
                "taskType": "tts",
                "config": {
                    "language": {
                        "sourceLanguage": source_lang
                    },
                    "serviceId": tts_service_id,
                    "gender": "female",
                    "samplingRate": 16000
                }
            }
        ],
        "inputData": {
            "input": [
                {
                    "source": prompt
                }
            ]
        }
    }


        response = requests.post(
            callback_url,
            json=payload,
            headers={'Content-Type': 'application/json', 'ulcaApiKey': api_key, 'userID': user_id, compute_authorization_key: compute_call_authorization_value}
        )
        #print(f"tts Response: {response.json()}")

        if response.status_code != 200:
            print(f"Audio processing failed: {response.status_code} - {response.text}")
            return jsonify({'error': 'Failed to process audio'}), 500
        
        processed_audio_base64 = response.json()['pipelineResponse'][0]['audio'][0]['audioContent']

        return processed_audio_base64

    except Exception as e:
        print(f"Exception occurred: {str(e)}")
        return jsonify({'error': 'An error occurred while processing audio'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)

