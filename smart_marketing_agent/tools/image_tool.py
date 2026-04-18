import os
from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig, ImageConfig

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

def generate_product_image(prompt: str) -> dict:
    """
    Generate marketing design image from prompt
    """
    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=prompt,
        config=GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=ImageConfig(
                aspect_ratio="1:1"
            )
        )
    )

    image_bytes = response.candidates[0].content.parts[0].inline_data.data

    return {
        "image_bytes": image_bytes
    }