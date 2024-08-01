from flask import Flask, request, jsonify
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import translate_v2 as translate
from google.cloud import texttospeech
from pytube import YouTube
import moviepy.editor as mp
import os
import ffmpeg

app = Flask(__name__)

# Initialize Google Cloud clients
speech_client = speech.SpeechClient()
translate_client = translate.Client()
tts_client = texttospeech.TextToSpeechClient()

@app.route('/process-video', methods=['POST'])
def process_video():
    data = request.json
    video_url = data['video_url']
    target_language = data['target_language']

    # Download video
    yt = YouTube(video_url)
    video = yt.streams.filter(only_audio=True).first()
    video_file = video.download()

    # Convert video to audio
    audio_clip = mp.AudioFileClip(video_file)
    audio_file = "audio.wav"
    audio_clip.write_audiofile(audio_file)

    # Transcribe audio with timestamps
    with open(audio_file, "rb") as f:
        audio_content = f.read()
    audio = speech.RecognitionAudio(content=audio_content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=int(audio_clip.fps),
        language_code="en-US",
        enable_word_time_offsets=True,
        enable_automatic_punctuation=True
    )
    response = speech_client.recognize(config=config, audio=audio)
    
    # Extract transcription with timestamps
    captions = []
    for result in response.results:
        for alt in result.alternatives:
            for word_info in alt.words:
                word = word_info.word
                start_time = word_info.start_time.total_seconds()
                end_time = word_info.end_time.total_seconds()
                captions.append({'text': word, 'start_time': start_time, 'end_time': end_time})

    # Translate each segment
    translated_captions = []
    for caption in captions:
        translation = translate_client.translate(caption['text'], target_language=target_language)
        translated_captions.append({
            'text': translation['translatedText'],
            'start_time': caption['start_time'],
            'end_time': caption['end_time']
        })

    # Generate audio for each translated segment
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

    # Merge audio segments into one file
    combined_audio = "combined_audio.wav"
    input_files = '|'.join([f'[0:a]atrim=start={start}:end={end}[a{i}];[a{i}]' for i, (_, start, end) in enumerate(audio_segments)])
    filter_complex = f"{input_files}concat=n={len(audio_segments)}:v=0:a=1[outa]"
    ffmpeg.input(audio_file).output(combined_audio, format='wav', acodec='pcm_s16le', filter_complex=filter_complex, map='[outa]').run()

    # Merge captions and audio with video
    output_video = "output_video.mp4"
    video_clip = mp.VideoFileClip(video_file)
    audio_clip = mp.AudioFileClip(combined_audio)
    final_video = video_clip.set_audio(audio_clip)
    final_video.write_videofile(output_video, codec='libx264', audio_codec='aac')

    # Cleanup
    os.remove(video_file)
    os.remove(audio_file)
    for segment_file, _, _ in audio_segments:
        os.remove(segment_file)

    return jsonify({
        'transcription': " ".join([caption['text'] for caption in captions]),
        'translated_text': " ".join([caption['text'] for caption in translated_captions]),
        'output_video': output_video
    })

if __name__ == '__main__':
    app.run(debug=True)
