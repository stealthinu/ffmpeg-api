# app.py
from flask import Flask, request, jsonify
import os
import subprocess

app = Flask(__name__)

SHARED_FOLDER = '/shared'

def process_cutlist(cutlist_path):
    """Parse cutlist file and return list of cut specifications"""
    cuts = []
    with open(os.path.join(SHARED_FOLDER, cutlist_path), 'r') as f:
        for line in f:
            # Skip empty lines and comments
            if not line.strip() or line.strip().startswith('#'):
                continue
            # Parse line: "HH:MM:SS HH:MM:SS output_name"
            parts = line.strip().split()
            if len(parts) == 3:
                start_time, end_time, output_name = parts
                cuts.append({
                    'start': start_time,
                    'end': end_time,
                    'output': f"{output_name}.mp4"
                })
    return cuts

def cut_video(input_path, start_time, end_time, output_path):
    """Cut video segment using ffmpeg with re-encoding"""
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-ss', start_time,
        '-to', end_time,
        # '-c', 'copy' を削除
        # 映像コーデックを指定（H.264を使用）
        '-c:v', 'libx264',
        # プリセットを指定（速度と品質のバランス）
        '-preset', 'medium',
        # 音声コーデックを指定（AACを使用）
        '-c:a', 'aac',
        '-y',
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running ffmpeg: {e.stderr.decode()}")
        return False

@app.route('/cut', methods=['POST'])
def cut_videos():
    data = request.get_json()
    
    # Validate request data
    required_fields = ['input_file', 'cutlist_file', 'output_folder']
    if not all(field in data for field in required_fields):
        return jsonify({
            'error': f'Missing required fields. Required: {required_fields}'
        }), 400
    
    input_file = data['input_file']
    cutlist_file = data['cutlist_file']
    output_folder = data['output_folder']
    
    # Validate input files exist
    input_path = os.path.join(SHARED_FOLDER, input_file)
    cutlist_path = os.path.join(SHARED_FOLDER, cutlist_file)
    
    if not all(os.path.exists(p) for p in [input_path, cutlist_path]):
        return jsonify({'error': 'Input file or cutlist file not found'}), 404
    
    # Create output directory if it doesn't exist
    output_dir = os.path.join(SHARED_FOLDER, output_folder)
    os.makedirs(output_dir, exist_ok=True)
    
    # Process cutlist and perform cuts
    cuts = process_cutlist(cutlist_file)
    results = []
    
    for cut in cuts:
        output_path = os.path.join(output_dir, cut['output'])
        success = cut_video(input_path, cut['start'], cut['end'], output_path)
        
        results.append({
            'output_file': os.path.join(output_folder, cut['output']),
            'success': success
        })
    
    return jsonify({
        'message': 'Processing complete',
        'results': results
    })

@app.route('/shared', methods=['GET'])
def list_shared():
    """List contents of the shared folder"""
    try:
        files = os.listdir(SHARED_FOLDER)
        files_info = []
        for file in files:
            file_path = os.path.join(SHARED_FOLDER, file)
            stats = os.stat(file_path)
            files_info.append({
                'name': file,
                'size': stats.st_size,
                'is_dir': os.path.isdir(file_path),
                'path': file_path
            })
        return jsonify({
            'shared_folder': SHARED_FOLDER,
            'contents': files_info
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'shared_folder': SHARED_FOLDER
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    