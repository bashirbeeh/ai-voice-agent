from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
import openai
import os

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

    except Exception as e:
        print("Error:", e)
        reply_text = "Sorry, I had trouble processing that."

    # Say the AI's reply
    response.say(reply_text, voice="Polly.Joanna")

    # 🧠 End call if user said goodbye
    if any(phrase in speech_text.lower() for phrase in ["no", "thank you", "i'm good", "bye", "goodbye"]):
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
