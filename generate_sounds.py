import wave
import struct
import random
import math

SAMPLE_RATE = 44100

def save_wav(filename, samples):
    """Saves a list of float samples (-1.0 to 1.0) as a 16-bit PCM WAV file."""
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        for s in samples:
            # Clamp to prevent clipping
            s = max(-1.0, min(1.0, s))
            wav_file.writeframes(struct.pack('<h', int(s * 32767.0)))

def generate_thrust():
    """Generates a looping, crunchy 8-bit static noise for the rocket thruster."""
    samples = []
    # 1 second loop is plenty
    for _ in range(SAMPLE_RATE):
        # Stepping the random noise gives it a lower-fi 'crunchy' sound
        noise = random.choice([-0.3, -0.1, 0.1, 0.3])
        samples.append(noise)
    save_wav('thrust.wav', samples)
    print("Generated thrust.wav")

def generate_crash():
    """Generates an 8-bit explosion sound that fades out."""
    samples = []
    duration = 1.5
    for i in range(int(SAMPLE_RATE * duration)):
        t = i / SAMPLE_RATE
        # Envelope: starts at 1.0, decays to 0
        envelope = max(0, 1.0 - (t / duration))
        # Gritty noise
        noise = random.choice([-1.0, 1.0]) * 0.8
        samples.append(noise * envelope)
    save_wav('crash.wav', samples)
    print("Generated crash.wav")

def generate_success():
    """Generates an 8-bit victory jingle (a rapid square wave arpeggio)."""
    samples = []
    # Frequencies for a happy C major arpeggio: C5, E5, G5, C6
    notes = [523.25, 659.25, 783.99, 1046.50]
    note_duration = 0.15 
    
    for freq in notes:
        for i in range(int(SAMPLE_RATE * note_duration)):
            t = i / SAMPLE_RATE
            # Square wave generation
            wave_val = 1.0 if math.sin(2 * math.pi * freq * t) > 0 else -1.0
            # Envelope to slightly fade each note so they don't pop
            envelope = 1.0 - (i / (SAMPLE_RATE * note_duration)) 
            samples.append(wave_val * 0.3 * envelope)
            
    save_wav('success.wav', samples)
    print("Generated success.wav")

if __name__ == "__main__":
    print("Synthesizing 8-bit audio files...")
    generate_thrust()
    generate_crash()
    generate_success()
    print("Done! You can now run your game.")