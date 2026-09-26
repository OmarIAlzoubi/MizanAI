from app.infrastructure.messaging.voice_media_store import (
    VoiceMediaStore,
)


store = VoiceMediaStore()

print("\n[S3 Voice Test]")
print("Uploading...")

key = store.upload_audio(
    file_path="tmp/grok_voice_test.mp3",
)

print("Uploaded key:")
print(key)


url = store.create_presigned_url(
    key=key,
    expires_in=900,
)

print("\nPresigned URL:")
print(url)

print("\nOpen the URL in your browser.")
print("The audio should play or download correctly.")