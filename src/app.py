# app.py
from flask import Flask, request, jsonify
import os
import subprocess

app = Flask(__name__)

SHARED_FOLDER = '/shared'

def validate_time_format(time_str):
    """Validate time string format (HH:MM:SS)"""
    try:
        parts = time_str.split(':')
        if len(parts) != 3:
            return False
        hours, minutes, seconds = map(int, parts)
        return 0 <= hours <= 23 and 0 <= minutes <= 59 and 0 <= seconds <= 59
    except:
        return False

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

def extract_muted_video(input_path, output_path):
    """Extract video without audio using ffmpeg"""
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-an',  # No audio
        '-c:v', 'copy',  # Copy video codec to avoid re-encoding
        '-y',  # Overwrite output
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running ffmpeg: {e.stderr.decode()}")
        return False

def extract_audio(input_path, output_path, audio_format='mp3'):
    """Extract audio from video file using ffmpeg"""
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-vn',  # No video
        '-acodec', 'libmp3lame' if audio_format == 'mp3' else 'pcm_s16le',  # mp3 or wav codec
        '-y',  # Overwrite output
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running ffmpeg: {e.stderr.decode()}")
        return False

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

@app.route('/segments/from-file', methods=['POST'])
def create_segments_from_file():
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


@app.route('/extract-audio', methods=['POST'])
def extract_audio_endpoint():
    data = request.get_json()
    
    # Validate request data
    required_fields = ['input_file', 'output_file']
    if not all(field in data for field in required_fields):
        return jsonify({
            'error': f'Missing required fields. Required: {required_fields}'
        }), 400
    
    input_file = data['input_file']
    output_file = data['output_file']
    audio_format = data.get('format', 'mp3').lower()
    
    # Validate format
    if audio_format not in ['mp3', 'wav']:
        return jsonify({'error': 'Unsupported audio format. Use mp3 or wav'}), 400
    
    # Validate input file exists
    input_path = os.path.join(SHARED_FOLDER, input_file)
    if not os.path.exists(input_path):
        return jsonify({'error': 'Input file not found'}), 404
    
    # Ensure output file has correct extension
    output_name = output_file if output_file.endswith(f'.{audio_format}') else f'{output_file}.{audio_format}'
    output_path = os.path.join(SHARED_FOLDER, output_name)
    
    # Extract audio
    success = extract_audio(input_path, output_path, audio_format)
    
    if success:
        return jsonify({
            'message': 'Audio extraction complete',
            'output_file': output_name,
            'format': audio_format
        })
    else:
        return jsonify({'error': 'Failed to extract audio'}), 500


@app.route('/extract-muted-video', methods=['POST'])
def extract_muted_video_endpoint():
    data = request.get_json()
    
    # Validate request data
    required_fields = ['input_file', 'output_file']
    if not all(field in data for field in required_fields):
        return jsonify({
            'error': f'Missing required fields. Required: {required_fields}'
        }), 400
    
    input_file = data['input_file']
    output_file = data['output_file']
    
    # Validate input file exists
    input_path = os.path.join(SHARED_FOLDER, input_file)
    if not os.path.exists(input_path):
        return jsonify({'error': 'Input file not found'}), 404
    
    # Ensure output file has .mp4 extension
    output_name = output_file if output_file.endswith('.mp4') else f'{output_file}.mp4'
    output_path = os.path.join(SHARED_FOLDER, output_name)
    
    # Extract video without audio
    success = extract_muted_video(input_path, output_path)
    
    if success:
        return jsonify({
            'message': 'Muted video extraction complete',
            'output_file': output_name
        })
    else:
        return jsonify({'error': 'Failed to extract muted video'}), 500


@app.route('/segments', methods=['POST'])
def create_segments():
    data = request.get_json()
    
    # Validate request data
    required_fields = ['input_file', 'segments', 'output_folder']
    if not all(field in data for field in required_fields):
        return jsonify({
            'error': f'Missing required fields. Required: {required_fields}'
        }), 400
    
    # Validate segments format
    segments = data['segments']
    if not isinstance(segments, list) or not segments:
        return jsonify({
            'error': 'segments must be a non-empty array'
        }), 400
    
    # Validate each segment
    for i, segment in enumerate(segments):
        if not isinstance(segment, dict):
            return jsonify({
                'error': f'Invalid segment at index {i}: must be an object'
            }), 400
            
        required_segment_fields = ['start_time', 'end_time', 'output_name']
        if not all(field in segment for field in required_segment_fields):
            return jsonify({
                'error': f'Segment at index {i} missing required fields. Required: {required_segment_fields}'
            }), 400
            
        # Validate time format
        if not validate_time_format(segment['start_time']):
            return jsonify({
                'error': f'Invalid start_time format at index {i}. Required format: HH:MM:SS'
            }), 400
        if not validate_time_format(segment['end_time']):
            return jsonify({
                'error': f'Invalid end_time format at index {i}. Required format: HH:MM:SS'
            }), 400
    
    input_file = data['input_file']
    output_folder = data['output_folder']
    
    # Validate input file exists
    input_path = os.path.join(SHARED_FOLDER, input_file)
    if not os.path.exists(input_path):
        return jsonify({'error': 'Input file not found'}), 404
    
    # Create output directory if it doesn't exist
    output_dir = os.path.join(SHARED_FOLDER, output_folder)
    os.makedirs(output_dir, exist_ok=True)
    
    # Process segments
    results = []
    for segment in segments:
        output_path = os.path.join(output_dir, f"{segment['output_name']}.mp4")
        success = cut_video(
            input_path,
            segment['start_time'],
            segment['end_time'],
            output_path
        )
        
        results.append({
            'output_file': os.path.join(output_folder, f"{segment['output_name']}.mp4"),
            'start_time': segment['start_time'],
            'end_time': segment['end_time'],
            'success': success
        })
    
    return jsonify({
        'message': 'Processing complete',
        'results': results
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
