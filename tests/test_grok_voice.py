from app.ai.grok_voice import (
    GrokVoice,
)


voice = GrokVoice()

text = (
    "تم تسجيل دفعة بقيمة "
    "خمسة وعشرين ريال "
    "في ستاربكس بنجاح"
)


print("\n[TTS]")
print("Generating Arabic voice...")


audio_path = voice.synthesize(
    text=text,
    output_path="tmp/grok_voice_test.mp3",
)


print(
    "Saved:",
    audio_path,
)


print("\n[STT]")
print("Transcribing generated audio...")


result = voice.transcribe(
    audio_path=audio_path,
)


print(
    "Language:",
    result.language,
)

print(
    "Duration:",
    result.duration,
)

print(
    "Transcript:",
    result.text,
) 