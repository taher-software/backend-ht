from src.app.globals.enum import MealPlan
from src.settings import client
from src.app.gcp.gcs import storage_client
import logging
import tempfile
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

LANG_MAP = {
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "ar": "Arabic",
    "ru": "Russian",
    "zh": "Chinese",
    "it": "Italian",
    "pt": "Portuguese",
    "hi": "Hindi",
    "ja": "Japanese",
    "ko": "Korean",
    "tr": "Turkish",
    "nl": "Dutch",
    "pl": "Polish",
    "th": "Thai",
    "fa": "Persian",
    "bn": "Bengali",
    "ur": "Urdu",
}

room_guest_satis_questions = [
    "How satisfied are you with the cleanliness of the floors, furniture, and bathroom?",
    "How satisfied are you with the freshness and arrangement of the linens, towels, and toiletries?",
    "How satisfied are you with the absence of dust or dirt?",
    "How satisfied are you with the friendliness and responsiveness of the housekeeping staff?",
]

room_reception_questions = [
    "How satisfied are you with the functionality of all electronic devices (TV, remote, air conditioning, lights)?",
    "How satisfied are you with the water pressure and temperature in the shower?",
    "How satisfied are you with the presence and functionality of the refrigerator?",
    "How satisfied are you with the overall cleanliness of the room, including the bathroom and bedding?",
]

restaurant_exp_questions = [
    "How satisfied are you with the friendliness and professionalism of the restaurant staff?",
    "How satisfied are you with the cleanliness of the dining area and table settings?",
    "How satisfied are you with the presentation and overall quality of the food you experienced during your visit to our restaurant?",
    "Have you ever experienced a queue (waiting line) while you were in the restaurant?",
    "Please provide what factors contribute most to your waiting?",
]

queue_factors = [
    "Table availability",
    "Staff efficiency",
    "Waiting for fresh dishes to be prepared",
]

dishes_questions = [
    "Kindly select the main {} dishes you sampled.",
    "How would you rate the taste and flavor of the",
]

breakfast_eligible_plans = [
    MealPlan.bb.value,
    MealPlan.hb.value,
    MealPlan.fb.value,
    MealPlan.ais.value,
    MealPlan.ai.value,
]

lunch_eligible_plans = [
    MealPlan.hb.value,
    MealPlan.fb.value,
    MealPlan.ais.value,
    MealPlan.ai.value,
]
dinner_eligible_plans = [
    MealPlan.fb.value,
    MealPlan.ais.value,
    MealPlan.ai.value,
]


def translate_text(text: str, target_language: str) -> str:
    """
    Translate text from any language to the target language using OpenAI.
    The function automatically detects the source language and translates to the target.

    Args:
        text: The text to translate
        target_language: The target language for translation (e.g., "english", "french", "arabic")

    Returns:
        str: Translated text

    Raises:
        Exception: If translation fails
    """
    try:
        logger.info(f"Translating text to {target_language}")

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are a professional translation assistant specializing in real-time chat communications.
Your task is to:
1. Automatically detect the language of the input text
2. Translate it to {target_language} while maintaining:
   - Natural conversational tone
   - Clarity and accuracy
   - Cultural appropriateness
   - Original meaning and intent

IMPORTANT: Return ONLY the translated text without any additional explanations, notes, language labels, or formatting.""",
                },
                {"role": "user", "content": text},
            ],
        )

        translated_text = completion.choices[0].message.content.strip()
        logger.info(f"Successfully translated text to {target_language}")

        return translated_text

    except Exception as e:
        logger.error(f"Translation failed: {str(e)}")
        raise Exception(f"Failed to translate text: {str(e)}")


@lru_cache
def transcript_audio(audio_path: str) -> str:
    """
    Transcribe audio file using OpenAI Whisper.

    Args:
        audio_path: Path to the audio file

    Returns:
        str: Transcribed text from the audio

    Raises:
        Exception: If transcription fails
    """
    try:
        logger.info(f"Transcribing audio from {audio_path}")
        audio_file = open(audio_path, "rb")
        transcription = client.audio.transcriptions.create(
            model="whisper-1", file=audio_file
        )
        logger.info("Audio transcription completed successfully")
        return transcription.text
    except Exception as e:
        logger.error(f"Audio transcription failed: {str(e)}")
        raise Exception(f"Failed to transcribe audio: {str(e)}")


def transcribe_audio_from_gcs_link(voice_url: str) -> str:
    """
    Transcribe audio from a Google Cloud Storage URL.

    Downloads the audio file from GCS, transcribes it using Whisper,
    and cleans up the temporary file.

    Args:
        voice_url: The Google Cloud Storage URL of the audio file
                  (format: https://storage.googleapis.com/{bucket_name}/{blob_name})

    Returns:
        str: Transcribed text from the audio

    Raises:
        ValueError: If the GCS URL format is invalid
        Exception: If download or transcription fails
    """
    try:
        logger.info(f"Processing audio transcription from GCS URL: {voice_url}")

        # Parse the GCS URL to extract bucket name and blob name
        url_parts = voice_url.replace("https://storage.googleapis.com/", "").split(
            "/", 1
        )
        if len(url_parts) != 2:
            raise ValueError(f"Invalid GCS URL format: {voice_url}")

        bucket_name = url_parts[0]
        blob_name = url_parts[1]

        # Create a temporary file to download the voice file
        with tempfile.NamedTemporaryFile(
            suffix=".wav", delete=False
        ) as temp_voice_file:
            temp_voice_path = temp_voice_file.name

            try:
                # Download the voice file from GCS to the temporary file
                logger.info(
                    f"Downloading audio from bucket: {bucket_name}, blob: {blob_name}"
                )
                storage_client.download_from_bucket(
                    bucket_name, blob_name, temp_voice_path
                )

                # Transcribe the audio
                transcribed_text = transcript_audio(temp_voice_path)

                logger.info("Successfully transcribed audio from GCS")
                return transcribed_text

            except Exception as e:
                logger.error(f"Error during GCS audio transcription: {str(e)}")
                raise
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_voice_path):
                    os.unlink(temp_voice_path)
                    logger.debug(f"Cleaned up temporary file: {temp_voice_path}")

    except Exception as e:
        logger.error(f"Failed to transcribe audio from GCS link: {str(e)}")
        raise
