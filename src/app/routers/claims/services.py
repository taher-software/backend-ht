from openai import OpenAI

client = OpenAI()


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
