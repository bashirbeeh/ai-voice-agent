from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
import openai
import requests
import os
from datetime import datetime

def log_interaction(user_input, ai_reply):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open("logs.txt", "a") as f:
        f.write(f"{timestamp}\nCaller: {user_input}\nAI: {ai_reply}\n\n")
def generate_speech_with_elevenlabs(text, filename="response.mp3"):
    api_key = os.getenv("ELEVENLABS_API_KEY")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }

    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": 0.4,
            "similarity_boost": 0.75
        }
    }

    response = requests.post(url, json=data, headers=headers)

    if response.status_code == 200:
        # Save MP3 to the /static folder
        audio_path = os.path.join("static", filename)
        with open(audio_path, "wb") as f:
            f.write(response.content)
        return f"/static/{filename}"
    else:
        print("Error generating speech:", response.text)
        return None


app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "AI Voice Agent is running."

# 👋 Initial greeting route
@app.route("/voice", methods=["POST"])
def voice():
    print("Voice route hit!")
    response = VoiceResponse()
    gather = Gather(
        input="speech",
        timeout=10,
        speechTimeout="auto",
        action="/gpt",
        method="POST"
    )
    # Greeting only happens once here
    gather.say("Hello, thank you for calling Civil JACOON help desk. How can I help you today?", voice="Polly.Joanna")
    response.append(gather)
    response.say("I didn't catch that. Goodbye.", voice="Polly.Joanna")
    return str(response)

# 🧠 OpenAI handles the rest of the conversation
@app.route("/gpt", methods=["POST"])
def gpt():
    print("GPT route hit!")

    speech_text = request.form.get("SpeechResult")
    print(f"User said: {speech_text}")

    response = VoiceResponse()

    try:
        if not speech_text:
            raise ValueError("No speech input detected")

        # ✅ API key now pulled from environment
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        ai_reply = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You're a helpful, polite virtual receptionist. If the user says thank you or no, end the call by saying goodbye and hanging up."
                },
                {
                    "role": "user",
                    "content": speech_text
                }
            ],
            max_tokens=100
        )
        reply_text = ai_reply.choices[0].message.content
        print(f"AI reply: {reply_text}")

        # ✅ Log the interaction
        log_interaction(speech_text, reply_text)

    except Exception as e:
        print("Error:", e)
        reply_text = "Sorry, I had trouble processing that."

    # ✅ Generate ElevenLabs audio for AI reply
    audio_path = generate_speech_with_elevenlabs(reply_text, "response.mp3")
    if audio_path:
        response.play(audio_path)
    else:
        response.say("Sorry, I had trouble speaking the answer.", voice="Polly.Joanna")

    # 🧠 End call if user said goodbye
    if any(phrase in speech_text.lower() for phrase in ["no", "thank you", "i'm good", "bye", "goodbye"]):
        goodbye_path = generate_speech_with_elevenlabs("You're welcome. Goodbye!", "goodbye.mp3")
        if goodbye_path:
            response.play(goodbye_path)
        else:
            response.say("You're welcome. Goodbye!", voice="Polly.Joanna")
        response.hangup()
    else:
        # 👇 Smarter follow-up
        if reply_text.strip().endswith("?"):
            # AI already asked a question — just listen
            gather = Gather(
                input="speech",
                timeout=15,
                speechTimeout="auto",
                action="/gpt",
                method="POST"
            )
            response.append(gather)
        else:
            # Add a fallback prompt if the AI didn’t prompt user
            gather = Gather(
                input="speech",
                timeout=15,
                speechTimeout="auto",
                action="/gpt",
                method="POST"
            )
            gather.say("Can I help you with anything else?", voice="Polly.Joanna")
            response.append(gather)

    return str(response)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
