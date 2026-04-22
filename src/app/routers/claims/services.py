from dotmap import DotMap
from .modelsIn import ClaimIn
import os
from src.app.resourcesController import (
    claim_controller,
    namespace_controller,
    chatRoom_controller,
)
from src.app.globals.notification import send_push_notification
from src.app.globals.schema_models import role_categ_assoc, ClaimStatus
from src.app.globals.enum import ClaimCriticality, CLAIM_DEDUCTIONS
from src.app.globals.satisfaction import check_and_trigger_satisfaction_alert
from src.app.resourcesController import settings_controller
from src.app.db.models import Users, Stay, Room, Guest
from src.app.db.models.claims import Claim
from src.app.gcp.gcs import storage_client
from fastapi import UploadFile, HTTPException, status
from sqlalchemy import asc, desc, and_, or_, func
from sqlalchemy.orm import selectinload
from src.app.globals.decorators import transactional
import tempfile
from src.settings import client
from functools import lru_cache
from src.app.globals.utils import transcript_audio, transcribe_audio_from_gcs_link
from datetime import datetime
from typing import Literal
import backoff
import openai
import logging

logger_claim = logging.getLogger(__name__)


def _make_giveup_handler(agent: str, location: Literal["title", "body"]):
    def _on_giveup(details):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"[{agent}] Failed to generate notification {location} after {details['tries']} retries",
        )
    return _on_giveup


@lru_cache
@backoff.on_exception(backoff.expo, openai.APIError, max_tries=3, on_giveup=_make_giveup_handler("guest_claim_update", "title"))
def define_guest_claim_update_title(language: str, claim_title: str, action: Literal["acknowledge", "resolve"]) -> str:
    action_update = "acknowledged" if action == "acknowledge" else "resolved"
    completion = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are an AI assistant. Generate a push notification title in {language} "
                    f"for a hotel claim that was {action_update} by hotel staff.\n\n"
                    f'Example: "🔔 Claim ({claim_title}) {action_update} by the hotel staff"'
                ),
            },
            {
                "role": "user",
                "content": f"Generate a notification title for claim '{claim_title}' ({action_update}) in {language}",
            },
        ],
    )
    return completion.choices[0].message.content


@lru_cache
@backoff.on_exception(backoff.expo, openai.APIError, max_tries=3, on_giveup=_make_giveup_handler("guest_claim_update", "body"))
def define_guest_claim_update_body(language: str, claim_title: str, action: Literal["acknowledge", "resolve"]) -> str:
    action_update = "acknowledged" if action == "acknowledge" else "resolved"
    completion = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are an AI assistant. Generate a short push notification body in {language} "
                    f"to inform a hotel guest that their claim has been {action_update} by hotel staff.\n\n"
                    f"Instructions:\n"
                    f"- Address the guest directly\n"
                    f"- Mention the claim title\n"
                    f"- Keep it to one sentence\n"
                    f"- Return only the notification body text\n\n"
                    f'Example: "Your claim \"{claim_title}\" has been {action_update} by our hotel staff. We appreciate your patience."'
                ),
            },
            {
                "role": "user",
                "content": f"Generate a notification body for claim '{claim_title}' ({action_update}) in {language}",
            },
        ],
    )
    return completion.choices[0].message.content


@lru_cache
@backoff.on_exception(backoff.expo, openai.APIError, max_tries=3, on_giveup=_make_giveup_handler("employee_claim_reject", "title"))
def define_employee_claim_reject_title(language: str, claim_title: str, room_number: str | int) -> str:
    completion = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are an AI assistant. Generate a short push notification title in {language} "
                    f"to alert a hotel employee that a guest has rejected the resolution of their claim.\n\n"
                    f'Example: "⚠️ Claim Resolution Rejected – Room {room_number}"'
                ),
            },
            {
                "role": "user",
                "content": f"Generate a notification title for claim '{claim_title}' from room {room_number} whose resolution was rejected by the guest, in {language}",
            },
        ],
    )
    return completion.choices[0].message.content


@lru_cache
@backoff.on_exception(backoff.expo, openai.APIError, max_tries=3, on_giveup=_make_giveup_handler("employee_claim_reject", "body"))
def define_employee_claim_reject_body(language: str, claim_title: str, room_number: str | int) -> str:
    completion = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are an AI assistant. Generate a short push notification body in {language} "
                    f"to inform a hotel employee that the guest in room {room_number} has rejected "
                    f"the resolution of their claim.\n\n"
                    f"Instructions:\n"
                    f"- Mention the room number\n"
                    f"- Mention the claim title\n"
                    f"- Keep it to one or two sentences\n"
                    f"- Return only the notification body text\n\n"
                    f'Example: "The guest in Room {room_number} has rejected the resolution of their claim \"{claim_title}\". Please follow up with the guest."'
                ),
            },
            {
                "role": "user",
                "content": f"Generate a notification body for claim '{claim_title}' from room {room_number} whose resolution was rejected by the guest, in {language}",
            },
        ],
    )
    return completion.choices[0].message.content


@lru_cache
def detect_language(text: str) -> str:
    completion = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": "You are an AI language detection system. Given a text input, your goal is to accurately identify its language. Even if the text contains some errors , you should be able guess the language. If you are uncertain about the language, respond with 'unknown.' Be concise, and return only the name of the language or 'unknown' with no extra text.",
            },
            {"role": "user", "content": text},
        ],
    )
    return completion.choices[0].message.content


@lru_cache
def define_category(claim_text: str) -> str:
    completion = client.chat.completions.create(
        model="gpt-5-mini",
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


@lru_cache
def translate_text(origin_language: str, target_language: str, text: str) -> str:
    completion = client.chat.completions.create(
        model="gpt-5-mini",
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


@lru_cache
def create_body_notif(text: str, language: str, room_number: int | str):
    completion = client.chat.completions.create(
        model="gpt-5-mini",
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


@lru_cache
def create_title_notif(language: str):
    completion = client.chat.completions.create(
        model="gpt-5-mini",
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


@lru_cache
def country_mother_language(country: str):
    completion = client.chat.completions.create(
        model="gpt-5-mini",
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


@lru_cache
def create_claim_title(claim_text: str, language: str):
    completion = client.chat.completions.create(
        model="gpt-5-mini",
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


@lru_cache
@backoff.on_exception(backoff.expo, openai.APIError, max_tries=3)
def _classify_claim_criticality(title: str, text: str) -> ClaimCriticality:
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You classify hotel guest claims by criticality. "
                        "Return exactly one word from this set: "
                        "'high', 'medium', or 'low'. "
                        "High = safety, health, or severe service failure. "
                        "Medium = meaningful impact but not urgent. "
                        "Low = minor inconvenience. Output only the word."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Title: {title or ''}\nText: {text or ''}"
                    ),
                },
            ],
        )
        value = (completion.choices[0].message.content or "").strip().lower()
        if value in {"high", "medium", "low"}:
            return ClaimCriticality(value)
        logger_claim.error(
            f"Unexpected criticality value from LLM: {value!r}"
        )
    except Exception as e:
        logger_claim.error(f"Failed to classify claim criticality: {e}")
    return ClaimCriticality.medium


@lru_cache
def create_resume_claim(
    claim_text: str,
    voice_url: str,
    target_language: str,
) -> str:
    """
    Create a resume/summary of a claim by downloading the voice file from GCS,
    transcribing it, and generating a summary in the target language.

    Args:
        claim_text: The text content of the claim
        voice_url: The Google Cloud Storage URL of the voice file
        target_language: The language to generate the resume in

    Returns:
        A summary/resume of the claim in the target language
    """
    if voice_url:
        transcribed_text = transcribe_audio_from_gcs_link(voice_url)

    prompt_engineering = f"""
    # Role and Objective
- The AI assistant generates concise summaries of hotel guest claims for hotel agents.
# Instructions
- Create a brief summary (2-3 sentences) in `{target_language}` using the provided claim text and transcribed voice text.
- The summary must:
- Highlight the main issue
- Include key details
- Maintain a professional tone
- The summary should deliver a clear message that helps the hotel agent understand the guest's claim.
- Return only the summary text, with no extra commentary or formatting.
# Context
- Claim Text: `{claim_text if claim_text else 'N/A'}`
- Transcribed Voice Text: `{transcribed_text if voice_url else 'N/A'}`
# Output Format
- Provide only the summary as plain text in `{target_language}`.
- Output Verbosity: Limit the summary to a maximum of 3 sentences. Do not exceed this cap.
- Prioritize complete, actionable summaries within this length limit. Do not increase length to restate politeness.
# Stop Conditions
- Complete when the summary is generated following the guidelines above.
    """
    response = client.responses.create(model="gpt-5-nano", input=prompt_engineering)

    return response.output_text


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
                    "image_claim_files",
                    destination_file,
                    img.filename,
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
                "video_claim_files",
                destination_file,
                vid_file.filename,
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
                "voice_claim_files",
                destination_file,
                voice_file.filename,
            )

        claim_dict.update(
            dict(
                claim_voice_url=voice_url,
                claim_category=claim_category,
                claim_language=claim_language,
                claim_voice_duration=payload.voice_duration,
            )
        )

    claim_title = create_claim_title(
        claim_text,
        claim_language,
    )
    claim_dict.update(dict(claim_title=claim_title))

    criticality = _classify_claim_criticality(claim_title, claim_text)
    claim_dict.update(dict(criticality=criticality.value))

    stay = (
        db.query(Stay)
        .options(selectinload(Stay.room))
        .filter(Stay.guest_id == guest.phone_number)
        .order_by(desc(Stay.start_date))
        .first()
    )

    claim_dict.update(dict(namespace_id=stay.namespace_id))
    claim_dict.update(dict(stay_id=stay.id))

    claim_controller.create(claim_dict, commit=False, db=db)

    # Apply satisfaction deduction; alert publication is deferred to the end
    # of the function so it only fires after notifications have been sent.
    pending_alert = None
    deduction = CLAIM_DEDUCTIONS.get(criticality, 0.0)
    if deduction > 0 and stay is not None:
        old_score = stay.guest_satisfaction or 1.0
        new_score = max(0.0, old_score - deduction)
        stay.guest_satisfaction = new_score
        db.add(stay)
        db.flush()

        ns_settings = settings_controller.find_by_field(
            "namespace_id", stay.namespace_id
        )
        threshold = (
            ns_settings.get("satisfaction_threshold", 0.5)
            if ns_settings
            else 0.5
        )
        pending_alert = {
            "old_score": old_score,
            "new_score": new_score,
            "threshold": threshold,
            "namespace_id": stay.namespace_id,
            "stay_id": stay.id,
            "guest_id": guest.phone_number,
        }

    role = [key for key, vl in role_categ_assoc.items() if claim_category in vl]

    role = role[0]
    employees = (
        db.query(Users)
        .filter(
            and_(
                Users.namespace_id == stay.namespace_id,
                or_(
                    Users.role.contains([role]),
                    Users.role.contains(["supervisor"]),
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
    notif_body = create_body_notif(
        claim_text, namespace_language, stay.room.room_number
    )
    print(f"notif title: {notif_body}")

    # review the case with unknown type
    for emp in employees:

        send_push_notification(emp.current_device_token, notif_title, notif_body,"claim")

    if pending_alert is not None:
        check_and_trigger_satisfaction_alert(**pending_alert)


@transactional
def update_claim_status(
    action: Literal["approve", "reject", "acknowledge", "resolve"],
    claim_id: int,
    current_user: dict,
    db=None,
):
    """
    Update claim status based on action.

    Args:
        action: The action to perform (approve, reject, acknowledge, resolve)
        claim_id: ID of the claim to update
        current_user: Current authenticated user or guest
        db: Database session

    Returns:
        str: Success message

    Raises:
        HTTPException: If validation fails
    """
    action_map_assoc = {
        "approve": ClaimStatus.closed.value,
        "reject": ClaimStatus.rejected.value,
        "acknowledge": ClaimStatus.processing.value,
        "resolve": ClaimStatus.resolved.value,
    }
    payload = {"status": action_map_assoc[action]}
    claim = claim_controller.find_by_id(claim_id)

    if not claim:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Claim with id {claim_id} not found",
        )

    if action in ["acknowledge", "resolve"]:
        if "id" not in current_user:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Only authenticated users can acknowledge or resolve claims",
            )
        # Get allowed categories for user's role
        allowed_categories = []
        for role in current_user.get("role", []):
            allowed_categories.extend(role_categ_assoc.get(role, []))
        if claim["claim_category"] not in allowed_categories:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"User with role {current_user['role']} is not allowed to {action} claims in category {claim['claim_category']}",
            )

    if action in ["approve", "reject"]:
        if "id" in current_user:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Only authenticated guests can approve or reject their claims",
            )
        if claim["guest_id"] != current_user["phone_number"]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Only the guest who created the claim can approve or reject it",
            )

    if action == "approve" or action == "reject":
        if claim["status"] != ClaimStatus.resolved.value:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Claim can only be approved or rejected if it is in resolved status",
            )
        if action == "approve":
            payload["approve_claim_time"] = datetime.now()
            # Deactivate chat room associated with this claim
            chat_room = chatRoom_controller.find_by_field("claim_id", claim_id)
            if chat_room:
                chatRoom_controller.update(
                    chat_room["id"], {"active": False}, commit=False, db=db
                )
        if action == "reject":
            payload["reject_claim_time"] = datetime.now()

    if action == "acknowledge":
        if claim["status"] != ClaimStatus.pending.value:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Claim can only be acknowledged if it is in pending status",
            )
        payload["acknowledged_employee_id"] = current_user["id"]
        payload["acknowledged_claim_time"] = datetime.now()

    if action == "resolve":
        if claim["status"] != ClaimStatus.processing.value:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Claim can only be resolved if it is in processing status",
            )
        payload["resolver_employee_id"] = current_user["id"]
        payload["resolve_claim_time"] = datetime.now()

    claim_controller.update(claim_id, payload, db=db, commit=False)

    if action in ["acknowledge", "resolve"]:
        guest = db.query(Guest).filter(Guest.phone_number == claim["guest_id"]).first()
        if guest and guest.current_device_token:
            language = guest.pref_language or claim["claim_language"]
            notif_title = define_guest_claim_update_title(language, claim["claim_title"], action)
            notif_body = define_guest_claim_update_body(language, claim["claim_title"], action)
            send_push_notification(guest.current_device_token, notif_title, notif_body)

    if action == "reject":
        resolver = db.query(Users).filter(Users.id == claim["resolver_employee_id"]).first()
        if resolver and resolver.current_device_token:
            stay = db.query(Stay).options(selectinload(Stay.room)).filter(Stay.id == claim["stay_id"]).first()
            room_number = stay.room.room_number if stay and stay.room else "N/A"
            language = resolver.pref_language or claim["claim_language"]
            notif_title = define_employee_claim_reject_title(language, claim["claim_title"], room_number)
            notif_body = define_employee_claim_reject_body(language, claim["claim_title"], room_number)
            send_push_notification(resolver.current_device_token, notif_title, notif_body)

    return "Claim updated successfully"


@transactional
def close_guest_claim(claim_id: int, current_guest: dict, db=None):
    claim = claim_controller.find_by_id(claim_id)

    if not claim:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Claim with id {claim_id} not found",
        )

    if claim["guest_id"] != current_guest["phone_number"]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the guest who created this claim can close it",
        )

    if claim["status"] != ClaimStatus.pending.value:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Claim can only be closed if it is in pending status",
        )

    claim_controller.update(claim_id, {"status": ClaimStatus.closed.value}, db=db, commit=False)
    return "Claim closed successfully"


def get_current_employee_claims(
    current_user: dict,
    page: int = 1,
    page_size: int = 10,
    room_number: int | None = None,
    created_at_sort: str = "desc",
    updated_at_sort: str = "desc",
    claim_status: ClaimStatus | None = None,
    db=None,
):
    query = (
        db.query(Claim)
        .options(selectinload(Claim.stay).selectinload(Stay.room), selectinload(Claim.guest))
        .filter(Claim.namespace_id == current_user["namespace_id"])
    )

    if room_number is not None:
        query = query.join(Claim.stay).join(Stay.room).filter(
            Room.room_number == str(room_number)
        )

    if claim_status is not None:
        query = query.filter(Claim.status == claim_status.value)

    created_at_order = asc(Claim.created_at) if created_at_sort == "asc" else desc(Claim.created_at)
    updated_at_order = asc(Claim.updated_at) if updated_at_sort == "asc" else desc(Claim.updated_at)
    query = query.order_by(created_at_order, updated_at_order)

    total = query.count()
    claims = query.offset((page - 1) * page_size).limit(page_size).all()

    return claims, total
