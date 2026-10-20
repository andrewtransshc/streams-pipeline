import whisper, json, sys
m = whisper.load_model("small.en")
for w in sys.argv[1:]:
    r = m.transcribe(f"work/{w}/audio16k.wav", word_timestamps=True, verbose=False, condition_on_previous_text=False,
                     initial_prompt="Lelac playing Copycat. BaoChickaWowWow. Dawn, Olive.")
    json.dump(r, open(f"work/{w}/transcript.json","w"))
    print(w, "done", len(r["segments"]), flush=True)
