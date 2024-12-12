import uvicorn
from config import start_app

# import google.cloud.logging

app = start_app()

# Instantiates a client
# client = google.cloud.logging.Client()
# client.setup_logging()


if __name__ == "__main__":
    uvicorn.run(app="main:app", host="127.0.0.0", port=8000, reload=True)
