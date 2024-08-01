from flask import Flask, request, jsonify
from sentencebysentence_translate import process_video

app = Flask(__name__)

@app.route('/process-video', methods=['POST'])
def process_video_endpoint():
    data = request.get_json()
    video_url = data.get('video_url')
    target_language = data.get('target_language')

    if not video_url or not target_language:
        return jsonify({"error": "Missing 'video_url' or 'target_language' in the request"}), 400

    try:
        output_video = process_video(video_url, target_language)
        return jsonify({"message": "Video processed successfully", "output_video": output_video}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
