import os
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import translate_v2 as translate
from google.cloud import texttospeech
from pytube import YouTube
import moviepy.editor as mp
import ffmpeg

# Set the environment variable for Google Cloud credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\Users\Asus\OneDrive\Desktop\Hackathon_project\Hack4change\TranscendAI\tts_pdf_reader_key.json'
# Initialize Google Cloud clients
speech_client = speech.SpeechClient()
translate_client = translate.Client()
tts_client = texttospeech.TextToSpeechClient()

def download_video(video_url):
    yt = YouTube(video_url)
    video = yt.streams.filter(only_audio=True).first()
    video_file = video.download()
    return video_file

def convert_video_to_audio(video_file):
    audio_clip = mp.AudioFileClip(video_file)
    audio_file = "audio.wav"
    audio_clip.write_audiofile(audio_file)
    return audio_file

def transcribe_audio(audio_file):
    with open(audio_file, "rb") as f:
        audio_content = f.read()
    audio = speech.RecognitionAudio(content=audio_content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
        enable_word_time_offsets=True,
        enable_automatic_punctuation=True
    )
    response = speech_client.recognize(config=config, audio=audio)
    
    captions = []
    for result in response.results:
        for alt in result.alternatives:
            for word_info in alt.words:
                word = word_info.word
                start_time = word_info.start_time.total_seconds()
                end_time = word_info.end_time.total_seconds()
                captions.append({'text': word, 'start_time': start_time, 'end_time': end_time})
    return captions

def translate_captions(captions, target_language):
    translated_captions = []
    for caption in captions:
        translation = translate_client.translate(caption['text'], target_language=target_language)
        translated_captions.append({
            'text': translation['translatedText'],
            'start_time': caption['start_time'],
            'end_time': caption['end_time']
        })
    return translated_captions

def generate_audio_segments(translated_captions, target_language):
    audio_segments = []
    for caption in translated_captions:
        synthesis_input = texttospeech.SynthesisInput(text=caption['text'])
        voice = texttospeech.VoiceSelectionParams(
            language_code=target_language,
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )
        response = tts_client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        segment_file = f"segment_{caption['start_time']}.wav"
        with open(segment_file, "wb") as out:
            out.write(response.audio_content)
        audio_segments.append((segment_file, caption['start_time'], caption['end_time']))
    return audio_segments

def merge_audio_segments(audio_segments):
    combined_audio = "combined_audio.wav"
    inputs = [ffmpeg.input(segment[0]) for segment in audio_segments]
    ffmpeg.concat(*inputs, v=0, a=1).output(combined_audio).run()
    return combined_audio

def combine_audio_with_video(video_file, combined_audio):
    video_clip = mp.VideoFileClip(video_file)
    audio_clip = mp.AudioFileClip(combined_audio)
    final_video = video_clip.set_audio(audio_clip)
    output_video = "output_video.mp4"
    final_video.write_videofile(output_video, codec='libx264', audio_codec='aac')
    return output_video

def main():
    video_url = 'https://youtu.be/dQw4w9WgXcQ?si=rNF4wiDOyBW-m5if'
    target_language = 'es'  # Set your target language here

    video_file = download_video(video_url)
    audio_file = convert_video_to_audio(video_file)
    captions = transcribe_audio(audio_file)
    translated_captions = translate_captions(captions, target_language)
    audio_segments = generate_audio_segments(translated_captions, target_language)
    combined_audio = merge_audio_segments(audio_segments)
    output_video = combine_audio_with_video(video_file, combined_audio)

    print(f"Transcription: {' '.join([caption['text'] for caption in captions])}")
    print(f"Translated Text: {' '.join([caption['text'] for caption in translated_captions])}")
    print(f"Output Video: {output_video}")

    # Cleanup


if __name__ == '__main__':
    main()
