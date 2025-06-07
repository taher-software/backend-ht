from openai import OpenAI
from dotmap import DotMap
from .modelsIn import ClaimIn
import os
from src.app.resourcesController import claim_controller, namespace_controller
from src.app.globals.notification import send_push_notification
from src.app.globals.schema_models import role_categ_assoc
from src.app.db.models import Users, Stay
from src.app.gcp.gcs import storage_client
from fastapi import UploadFile
from sqlalchemy import desc, and_, or_
from src.app.globals.decorators import transactional
from pathlib import Path
import tempfile
from src.settings import client


def detect_language(text: str) -> str:
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are an AI language detection system. Given a text input, your goal is to accurately identify its language. Even if the text contains some errors , you should be able guess the language. If you are uncertain about the language, respond with 'unknown.' Be concise, and return only the name of the language or 'unknown' with no extra text.",
            },
            {"role": "user", "content": text},
        ],
    )
    return completion.choices[0].message.content


def define_category(claim_text: str) -> str:
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """You are an AI tasked with categorizing claims made by hotel guests. Each claim should be assigned one of the following categories:
                    Housekeeping: Issues related to room cleanliness, bedding, toiletries, or other housekeeping services.
                    Maintenance: Issues related to room repairs, equipment, plumbing, lighting, or any physical repairs needed.
                    Guest Relations: Issues related to staff interactions, complaints about service, check-in/check-out issues, or general guest concerns.
                    Dining: Issues related to food quality, restaurant service, dining area cleanliness, or any problems with meals.
                    If you cannot confidently determine the category, respond with 'unknown.' Return only the category name or 'unknown' with no extra text.""",
            },
            {"role": "user", "content": claim_text},
        ],
    )
    return completion.choices[0].message.content


def transcript_audio(audio_path: str) -> str:
    audio_file = open(audio_path, "rb")
    transcription = client.audio.transcriptions.create(
        model="whisper-1", file=audio_file
    )
    return transcription.text


def translate_text(origin_language: str, target_language: str, text: str) -> str:
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"""You are an AI translation assistant. Your task is to translate a given text accurately from {origin_language} language to the {target_language}. Follow these guidelines:
                              - Keep the original meaning and tone of the text intact.
                              - If there are idioms or expressions, translate them into equivalent expressions in the target language where possible.
                              - Avoid translating proper names, brand names, or technical terms unless they have standard equivalents in the target language.
                              - Return only the translated text with no additional information or explanations.""",
            },
            {"role": "user", "content": text},
        ],
    )
    return completion.choices[0].message.content


def create_body_notif(text: str, language: str, room_number: int | str):
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"""You are an AI assistant. Your task is to generate a notification template based on the provided text and language. Use the structure from the following example, adjusting it to reflect the specific issue and urgency level of the claim.

                                Example template: "Guest in Room {room_number} has submitted a claim regarding [Issue Type, e.g., 'Air Conditioning' or 'Room Cleanliness']. Please review the details and take action as soon as possible. Urgency Level: [Urgency Level, e.g., 'High']."

                                Instructions:

                                Extract the specific issue type from {text}.
                                Estimate the urgency level based on keywords or urgency indicators (e.g., "immediately," "critical").
                                Construct the notification in the given {language}.
                                Use the template language style and structure provided in the example, and adjust details based on {text}, {room_number}, and {language}.""",
            },
            {"role": "user", "content": text},
        ],
    )
    return completion.choices[0].message.content


def create_title_notif(language: str):
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"""You are an AI assistant. Your task is to generate a notification title  based on the template provided as example and in the language {language} . 

                                Example template: "🔔 New Claim Submitted by Guest - Immediate Attention Required"

                        """,
            },
            {"role": "user", "content": language},
        ],
    )
    return completion.choices[0].message.content


def country_mother_language(country: str):
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"""You are an AI assistant. Your task is to give the mother language of the given country {country} in one word.
                    Instructions:
                    - provide only the most used language in one word.
                    - don't add any details. Provide only the language used widely in this country.
                """,
            },
            {"role": "user", "content": country},
        ],
    )
    return completion.choices[0].message.content


def create_claim_title(claim_text: str, language: str):
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"""You are an AI assistant. Your task is to generate a concise title, with a maximum of two words, for the given claim text in the language {language}.
                """,
            },
            {"role": "user", "content": claim_text},
        ],
    )
    return completion.choices[0].message.content


@transactional
def add_guest_claims(
    payload: ClaimIn | None,
    current_guest: dict,
    img_files: list,
    voice_file: UploadFile | None = None,
    vid_file: UploadFile | None = None,
    db=None,
):
    guest = DotMap(current_guest)
    claim_dict = dict(guest_id=guest.phone_number)

    if payload and payload.text:
        claim_text = payload.text
        claim_language = detect_language(claim_text)
        claim_category = define_category(claim_text)
        claim_dict.update(
            dict(
                claim_text=claim_text,
                claim_language=claim_language,
                claim_category=claim_category,
            )
        )
    if img_files:
        img_urls = []
        for img in img_files:
            with tempfile.TemporaryDirectory() as temp_dir:
                destination_file = os.path.join(temp_dir, img.filename)
                with open(destination_file, "wb") as f:
                    f.write(img.file.read())
                img_url = storage_client.upload_to_bucket(
                    "book-management-api-58a60.appspot.com",
                    destination_file,
                    f"image_claim_files/{img.filename}",
                )
                img_urls.append(img_url)
        claim_dict.update(dict(claim_images_url=img_urls))
    if vid_file:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination_file = os.path.join(temp_dir, vid_file.filename)
            print(f"vid_file: {vid_file.filename}")
            with open(destination_file, "wb") as f:
                f.write(vid_file.file.read())
            vid_url = storage_client.upload_to_bucket(
                "book-management-api-58a60.appspot.com",
                destination_file,
                f"video_claim_files/{vid_file.filename}",
            )
        claim_dict.update(dict(claim_video_url=vid_url))
    if voice_file:
        print("voice file received")
        with tempfile.TemporaryDirectory() as temp_dir:
            destination_file = os.path.join(temp_dir, voice_file.filename)
            with open(destination_file, "wb") as f:
                f.write(voice_file.file.read())

            claim_text = transcript_audio(destination_file)
            claim_language = detect_language(claim_text)
            claim_category = define_category(claim_text)
            voice_url = storage_client.upload_to_bucket(
                "book-management-api-58a60.appspot.com",
                destination_file,
                f"voice_claim_files/{voice_file.filename}",
            )

        claim_dict.update(
            dict(
                claim_voice_url=voice_url,
                claim_category=claim_category,
                claim_language=claim_language,
                claim_voice_duration=payload.voice_duration,
            )
        )
    else:
        print("no voice file received...")
    claim_title = create_claim_title(
        claim_text,
        claim_language,
    )
    claim_dict.update(dict(claim_title=claim_title))

    stay = (
        db.query(Stay)
        .filter(Stay.guest_id == guest.phone_number)
        .order_by(desc(Stay.start_date))
        .first()
    )

    claim_dict.update(dict(namespace_id=stay.namespace_id))
    claim_dict.update(dict(stay_id=stay.id))

    claim_controller.create(claim_dict, commit=True, db=db)

    role = [key for key, vl in role_categ_assoc.items() if claim_category in vl]

    role = role[0]
    employees = (
        db.query(Users)
        .filter(
            and_(
                Users.namespace_id == stay.namespace_id,
                or_(
                    Users.role.contains(role),
                    Users.role.contains("supervisor"),
                ),
            )
        )
        .all()
    )
    namespace = namespace_controller.find_by_id(stay.namespace_id)
    namespace = DotMap(namespace)
    country = namespace.country
    namespace_language = country_mother_language(country)
    print(f"namespace language: {namespace_language}")
    notif_title = create_title_notif(namespace_language)
    print(f"notif title: {notif_title}")
    notif_body = create_body_notif(claim_text, namespace_language, stay.stay_room)
    print(f"notif title: {notif_body}")

    # review the case with unknown type
    for emp in employees:

        send_push_notification(emp.current_device_token, notif_title, notif_body)
