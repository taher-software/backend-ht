from typing_extensions import Literal
import requests
import logging

notif_type = dict(
    urgent=dict(channelId="urgent", sound="notif.wav"),
    message=dict(channelId="message", sound="message_notif.wav"),
    claim=dict(channelId="new_claim", sound="claim_sound.wav"),
)


def send_push_notification(
    expo_push_token,
    title,
    message,
    notif_level: Literal["urgent", "message", "claim"] = "urgent",
):
    url = "https://api.expo.dev/v2/push/send?useFcmV1=true"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
    }
    payload = {
        "to": expo_push_token,
        "title": title,
        "body": message,
        **notif_type[notif_level],
    }
    print(f"expo_push_token: {expo_push_token}")
    logging.info(f"expo_push_token: {expo_push_token}")
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        print("Notification sent successfully")
        logging.info("Notification sent successfully")
    else:
        print(f"Failed to send notification: {response.text}")
        logging.debug(f"Failed to send notification: {response.text}")
