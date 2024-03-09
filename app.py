import json
import os
from openai import OpenAI
from flask import Flask, request, send_file, render_template
from dotenv import load_dotenv


def calculate_total_price(**kwargs):
    products_with_quantities = kwargs.get("products_with_quantities", [])
    total_price = 0
    for product in products_with_quantities:
        product_name = product["name"].lower()
        if product_name in fastfood_prices:
            total_price += fastfood_prices[product_name] * product["quantity"]
        else:
            print(
                f"Product not found or not available in the requested variant: {product['name']}"
            )
    return total_price


fastfood_prices = {
    "coke": 1.99,
    "fries": 2.49,
    "hamburger": 3.99,
    "cheeseburger": 4.49,
    "chicken nuggets": 4.99,
    "ice cream sundae": 2.99,
    "salad": 3.99,
    "fishburger": 4.99,
    "hot dog": 3.49,
    "milkshake": 2.99,
}
product_names_string = ", ".join(fastfood_prices.keys())


tools = [
    {
        "type": "function",
        "function": {
            "name": "calculate_total_price",
            "description": "Calculates the total price for a list of products with specified quantities, based on a predefined price list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "products_with_quantities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "The name of the product.",
                                },
                                "quantity": {
                                    "type": "integer",
                                    "description": "The quantity of the product.",
                                },
                            },
                            "required": ["name", "quantity"],
                        },
                        "description": "A list of products with their names and quantities. Each item is an object with 'name' and 'quantity' properties.",
                    }
                },
                "required": ["products_with_quantities"],
            },
        },
    }
]


class OpenAIClient:
    def __init__(self):
        load_dotenv()
        self.client = OpenAI()

    def transcribe_audio(self, file_path):
        with open(file_path, "rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1", file=audio_file
            )
        return transcript.text

    def process_order(self, text, product_names_string):
        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": f"You are an assistant to reformulate textinut of a user. He orders products. You identify the following products {product_names_string} in the request and rename it if there is an error. Example: 'hat dog' -> 'Hot Dog' Also reformulate or create numbers from the request. Example: 'A Hot Dog' -> '1 Hot Dog'. Make sure you remove any made up arguments like product size, color or anything. Double check the new message only contains the exact naming of the products and remove it if necessary",
                },
                {"role": "user", "content": text},
            ],
        )
        return completion.choices[0].message.content

    def generate_response(self, final_price):
        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": f"Please tell me customer the following: <<<<Thank you so much for your order! Please drive to the next window to pay {(final_price)}€. We're excited to have you try our delicious offerings! Thank you once again for choosing Mac AI. We hope to see you again soon!>>>>",
                },
            ],
        )
        return completion.choices[0].message.content

    def text_to_speech(self, text, file_path):
        response = self.client.audio.speech.create(
            model="tts-1", voice="onyx", input=text
        )
        response.stream_to_file(file_path)

    def calculate_and_respond(self, transcript):
        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": transcript},
            ],
            tools=tools,
        )

        return completion.choices[0].message

    def handle_input(self, audio_file_path):
        transcript = self.transcribe_audio(audio_file_path)

        processed_transcript = self.process_order(transcript, product_names_string)

        order_response = self.calculate_and_respond(processed_transcript)

        if order_response.tool_calls:
            tool_call = order_response.tool_calls[0]
            tool_call_arguments = json.loads(tool_call.function.arguments)

            for product in tool_call_arguments["products_with_quantities"]:
                product["name"] = product["name"].lower()


            final_price = calculate_total_price(**tool_call_arguments)

            response = self.generate_response(final_price)
            response_audio_path = os.path.join(os.getcwd(), "order_response.mp3")
            self.text_to_speech(response, response_audio_path)

            return response_audio_path
        else:
            return "Error: No tool calls found in order response."




app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_audio', methods=['POST'])
def process_audio():
    if 'audio' not in request.files:
        return "Audio file is missing", 400

    audio_file = request.files['audio']
    audio_file_path = "uploaded_audio.mp3"
    audio_file.save(audio_file_path)

    response_audio_path = openai_client.handle_input(audio_file_path)

    if response_audio_path.startswith("Error"):
        return response_audio_path, 500

    return send_file(response_audio_path, as_attachment=True)


if __name__ == "__main__":
    openai_client = OpenAIClient()
    app.run(debug=True, port=5577)
