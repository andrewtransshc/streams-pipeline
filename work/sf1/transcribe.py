import whisper, json, sys
m = whisper.load_model("small.en")
r = m.transcribe("work/sf1/audio16k.wav", word_timestamps=True, verbose=False, condition_on_previous_text=False)
json.dump(r, open("work/sf1/transcript.json","w"))
print("done", len(r["segments"]))
