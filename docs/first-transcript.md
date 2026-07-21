# earbox — the first live transcript

**2026-07-22, ~04:59 workshop time.**

The first end-to-end live transcription happened here. Real speech into the
**reSpeaker XVF3800** 4-mic array, over USB into the **Jetson Orin Nano Super**,
through **faster-whisper** (CPU, int8, `small`) running fully **on-device**, out
to text. **The audio was deleted by construction** — transient in tmpfs,
never durably written, exactly as the privacy invariant demands. This is the
first time the whole chain carried live voice, not a canned wav.

The hard part wasn't the model. The mic read as a dead signal — silence where
speech should be — and the culprit was a **USB-A→USB-C adapter** in the path.
Swapped it for a **known-good cable** and the array came alive on the first try.

## The transcript

```
[0.00  -> 24.77] C'est bizarre de chier dans la choucroute.
[24.77 -> 31.65] Même les chats chient dans la choucroute, ce qui est très bizarre.
[36.33 -> 40.33] C'est bizarre à 4h59 de chier dans la choucroute.
[40.33 -> 49.48] C'est très bizarre à 5h du matin de chier dans la choucroute.
[49.48 -> 60.01] C'est bizarre de chier dans la choucroute si tôt le matin.
```

The improvised time references in the speech — *"à 4h59"*, *"à 5h du matin"* —
match the wall clock at recording. That's the proof it was **live**: the model
transcribed words spoken in the room at that minute, not a replay.

## Performance

**60 s of audio transcribed in ~16 s** on the Orin CPU (faster-whisper, int8,
`small`). Real-time factor well under 1× before the GPU is even in the picture —
CUDA int8 is the headroom, this was the floor.
