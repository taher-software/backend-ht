from functools import lru_cache
from google.cloud import storage


class GcsInteraction:

    @lru_cache
    def _initialize_gcp_storage_client(self):
        storage_client = storage.Client()
        return storage_client

    def create_gcp_bucket(self, bucket_name):

        storage_client = self._initialize_gcp_storage_client()

        bucket = storage_client.create_bucket(bucket_name)
        return

    def gcp_bucket_exists(self, bucket_name):
        storage_client = self._initialize_gcp_storage_client()
        bucket = storage_client.lookup_bucket(bucket_name)

        return bucket is not None

    def upload_to_bucket(
        self, bucket_name, source_file_name, destination_blob_name, **kwargs
    ):

        storage_client = self._initialize_gcp_storage_client()

        if not self.gcp_bucket_exists(bucket_name):
            self.create_gcp_bucket(bucket_name)

        bucket = storage_client.bucket(bucket_name)

        blob = bucket.blob(destination_blob_name)

        blob.upload_from_filename(source_file_name)

        blob.make_public()

        print(f"File {source_file_name} uploaded to {destination_blob_name}.")
        return f"https://storage.googleapis.com/{bucket_name}/{destination_blob_name}"


@lru_cache
def initialize_GcsInteraction():
    return GcsInteraction()


storage_client = initialize_GcsInteraction()
