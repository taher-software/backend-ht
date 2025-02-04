import requests
import logging


def send_push_notification(expo_push_token, title, message):
    url = "https://api.expo.dev/v2/push/send?useFcmV1=true"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
    }
    payload = {
        "to": expo_push_token,
        "sound": "default",  # Ensures an alert with sound
        "title": title,
        "body": message,
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
