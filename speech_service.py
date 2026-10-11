import os

import azure.cognitiveservices.speech as speechsdk


class SpeechServiceError(Exception):
    pass


def _get_credentials():
    key = os.environ.get("AZURE_SPEECH_KEY")
    region = os.environ.get("AZURE_SPEECH_REGION")
    if not key or not region:
        raise SpeechServiceError(
            "Azure Speech credentials are not configured on the server. "
            "Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION environment variables."
        )
    return key, region


def transcribe_audio_file(file_path: str) -> str:
    key, region = _get_credentials()

    try:
        speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
        speech_config.speech_recognition_language = os.environ.get(
            "AZURE_SPEECH_LANGUAGE", "en-US"
        )

        audio_config = speechsdk.audio.AudioConfig(filename=file_path)
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config, audio_config=audio_config
        )

        result = recognizer.recognize_once()

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            return result.text

        if result.reason == speechsdk.ResultReason.NoMatch:
            return ""

        if result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            raise SpeechServiceError(
                f"Speech recognition was canceled: {cancellation.reason}. "
                f"{cancellation.error_details or ''}".strip()
            )

        raise SpeechServiceError("Unknown speech recognition result reason.")

    except SpeechServiceError:
        raise
    except Exception as exc:
        raise SpeechServiceError(f"Speech recognition failed: {exc}") from exc
