import io
import time
import numpy as np
import sounddevice as sd
from abc import ABC, abstractmethod

class BaseSTT(ABC):
    """Abstract base class for Speech-to-Text engines."""
    
    @abstractmethod
    def transcribe(self, audio_data: np.ndarray, sample_rate: int) -> str:
        """Transcribe numpy audio data to text."""
        pass


class FasterWhisperSTT(BaseSTT):
    """
    Local Whisper STT using faster-whisper (CTranslate2).
    Optimized for low-latency CPU and GPU inference.
    """
    def __init__(self, model_size: str = "base", device: str = "auto", compute_type: str = "int8"):
        from faster_whisper import WhisperModel
        print(f"Loading Whisper model ({model_size})...", end="", flush=True)
        # Default to CPU with int8 if GPU not available
        actual_device = "cpu" if device == "auto" else device
        self.model = WhisperModel(model_size, device=actual_device, compute_type=compute_type)
        print(" Done.")

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        # Convert float audio to 16-bit PCM WAV in memory
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
            
        # Normalize audio if needed
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            audio_data = audio_data / max_val

        segments, _ = self.model.transcribe(audio_data, beam_size=2, language="en")
        text = " ".join([segment.text for segment in segments]).strip()
        return text


class MicrophoneRecorder:
    """
    Records microphone audio with dynamic Voice Activity Detection.
    Automatically calibrates background noise floor and records until user finishes speaking.
    """
    def __init__(self, sample_rate: int = 16000, silence_duration: float = 1.3, energy_threshold: float = 0.012):
        self.sample_rate = sample_rate
        self.silence_duration = silence_duration
        self.energy_threshold = energy_threshold

    def record_utterance(self, max_duration: float = 15.0) -> np.ndarray:
        """
        Record until user stops talking (detected silence) or reaches max_duration.
        """
        chunk_duration = 0.08  # 80ms chunks
        chunk_samples = int(self.sample_rate * chunk_duration)
        
        audio_chunks = []
        silence_samples = 0
        max_silence_samples = int(self.silence_duration / chunk_duration)
        has_spoken = False
        start_time = time.time()

        print("🎙️  Listening... (speak now)", flush=True)

        with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='float32') as stream:
            # Quick noise calibration
            initial_vals = []
            for _ in range(3):
                init_chunk, _ = stream.read(chunk_samples)
                initial_vals.append(np.sqrt(np.mean(init_chunk**2)))
            noise_floor = float(np.median(initial_vals)) if initial_vals else 0.01
            effective_threshold = max(0.012, noise_floor * 1.4)

            while True:
                chunk, _ = stream.read(chunk_samples)
                audio_chunks.append(chunk.flatten())
                
                # Calculate RMS energy of current chunk
                rms = np.sqrt(np.mean(chunk**2))
                
                if rms > effective_threshold:
                    has_spoken = True
                    silence_samples = 0
                else:
                    if has_spoken:
                        silence_samples += 1
                        
                # If speech was detected and now silent for silence_duration, finish recording
                if has_spoken and silence_samples >= max_silence_samples:
                    break
                    
                # Timeout safety check
                if time.time() - start_time > max_duration:
                    break
                    
                # If no speech detected after 6 seconds, return empty
                if not has_spoken and (time.time() - start_time > 6.0):
                    return np.array([], dtype=np.float32)

        if len(audio_chunks) == 0:
            return np.array([], dtype=np.float32)

        return np.concatenate(audio_chunks)


def get_stt_engine(model_size: str = "base") -> BaseSTT:
    """Factory to get STT engine."""
    return FasterWhisperSTT(model_size=model_size)
