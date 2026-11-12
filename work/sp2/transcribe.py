import os, sys; sys.path.insert(0, os.getcwd())  # run from the Streams folder
import pipeline_env  # puts ffmpeg on PATH for Whisper
import whisper, json, sys
m = whisper.load_model("small.en")
r = m.transcribe("work/sp2/audio16k.wav", word_timestamps=True, verbose=False, condition_on_previous_text=False)
json.dump(r, open("work/sp2/transcript.json","w", encoding="utf-8"))
print("done", len(r["segments"]))
