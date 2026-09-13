import numpy as np
import sounddevice as sd
from abc import ABC, abstractmethod

class BaseWakeWordDetector(ABC):
    """Abstract base class for Wake Word Detectors."""
    
    @abstractmethod
    def wait_for_wake_word(self) -> bool:
        """Blocks until wake word is detected or interrupted."""
        pass


class AdaptiveVoiceTrigger(BaseWakeWordDetector):
    """
    Intelligent Adaptive Voice Trigger.
    Calibrates ambient noise floor and triggers immediately when user speaks or says 'Lisa'.
    """
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.noise_floor = 0.01

    def calibrate(self, stream, samples_count: int = 3):
        """Quickly sample ambient room noise to prevent false drops or stuck states."""
        try:
            read_size = int(self.sample_rate * 0.05)
            vals = []
            for _ in range(samples_count):
                chunk, _ = stream.read(read_size)
                vals.append(np.sqrt(np.mean(chunk**2)))
            if vals:
                self.noise_floor = float(np.median(vals))
        except Exception:
            self.noise_floor = 0.012

    def wait_for_wake_word(self) -> bool:
        chunk_samples = int(self.sample_rate * 0.08)
        with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='float32') as stream:
            self.calibrate(stream)
            threshold = max(0.015, self.noise_floor * 1.5)
            
            consecutive_hits = 0
            while True:
                chunk, _ = stream.read(chunk_samples)
                rms = np.sqrt(np.mean(chunk**2))
                
                if rms > threshold:
                    consecutive_hits += 1
                    if consecutive_hits >= 2: # Confirmed speech burst
                        return True
                else:
                    consecutive_hits = 0


def get_wake_word_detector(detector_type: str = "adaptive") -> BaseWakeWordDetector:
    """Factory function for wake word detector."""
    return AdaptiveVoiceTrigger()
