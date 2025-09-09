from google.cloud import storage
import io


def download_blob_into_memory(bucket_name, blob_name):
    """Downloads a blob into memory."""
   
    storage_client = storage.Client()

    bucket = storage_client.bucket(bucket_name)

    # Construct a client side representation of a blob.
    # Note `Bucket.blob` differs from `Bucket.get_blob` as it doesn't retrieve
    # any content from Google Cloud Storage. As we don't need additional data,
    # using `Bucket.blob` is preferred here.
    blob = bucket.blob(blob_name)
    contents = blob.download_as_bytes()

    print(
        "Downloaded storage object {} from bucket {} as the following bytes object: {}.".format(
            blob_name, bucket_name, contents
        )
    )

    return contents

def download_blob_to_stream(bucket_name, source_blob_name, file_obj):
    """Downloads a blob to a stream or other file-like object."""

    # The stream or file (file-like object) to which the blob will be written
    # file_obj = io.BytesIO()

    storage_client = storage.Client()

    bucket = storage_client.bucket(bucket_name)

    # Construct a client-side representation of a blob.
    # Note `Bucket.blob` differs from `Bucket.get_blob` in that it doesn't
    # retrieve metadata from Google Cloud Storage. As we don't use metadata in
    # this example, using `Bucket.blob` is preferred here.
    blob = bucket.blob(source_blob_name)
    blob.download_to_file(file_obj)

    print(f"Downloaded blob {source_blob_name} to file-like object.")

    return file_obj
    # Before reading from file_obj, remember to rewind with file_obj.seek(0).

if __name__ == "__main__":
    bucket_name = "a2a-dpgt-p-buk-euwe4-arpa-liguria"
    source_blob_name = 'GRIB2/2019/06/molita15sfc_2019060100.grib2'

    # obj=download_blob_into_memory(bucket_name, source_blob_name)