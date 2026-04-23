"""
Generates Hindi TTS audio for each section using gTTS.
"""

import os
from gtts import gTTS


def generate_audio(scripts, out_dir):
    """
    scripts: dict of section_name -> hindi text
    Returns dict of section_name -> audio_file_path
    """
    audio_files = {}
    for section, text in scripts.items():
        path = os.path.join(out_dir, f"audio_{section}.mp3")
        print(f"  Generating audio: {section}...")
        try:
            tts = gTTS(text=text, lang="hi", slow=False)
            tts.save(path)
            audio_files[section] = path
        except Exception as e:
            print(f"  [!] Audio failed for {section}: {e}")
            audio_files[section] = None
    return audio_files
