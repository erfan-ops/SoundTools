"""### made by Mohammad Erfan Karami
github: https://github.com/erfan-ops

### version: 0.2.3.2

this package is used to create, play and save sound files
it has some basic sound waves although you can add your own and modify the package.

it stores the sound waves as numpy arrays and uses pyaudio for playback
and uses matplotlib to visualize the waves"""


import pyaudio
import numpy as np
from typing import Callable, Iterable, Literal, Self, Tuple, Dict, List
import scipy.io.wavfile as wf
import matplotlib.pyplot as plt
import librosa.effects as effect
from os.path import splitext
from pydub.audio_segment import AudioSegment
from soundfile import read as sfRead


# types
Dtype = np.dtype[np.float32|np.int16|np.uint8]
SoundBuffer = np.ndarray[np.any, Dtype]
Wave = Callable[[float, float, float], SoundBuffer]
Note = str|float


# its just a dictionary
class Notes(Dict[str, float]):
    """a dictionary used to store note names and frequencies"""
    def __init__(self):
        super().__init__()
    
    def __getitem__(self, __key: str) -> float:
        return super().__getitem__(__key.upper())
    
    def __setitem__(self, __key: str, __value: float) -> None:
        return super().__setitem__(__key.upper(), __value)


#-- sound waves --#
class Sounds:
    """has some basic sound waves and also caches the result of the functions for faster output"""
    def __init__(self, sample_rate: int=48000, dtype:Dtype=np.float32) -> None:
        self.default_sample_rate: int = sample_rate
        self.existed_notes: Dict[str, Tuple] = {}
        
        self.tau = 2*np.pi
        self.rev_pi = 1/np.pi
        self.two_oper_pi = 2/np.pi
        self.four_over_pi = 4/np.pi
        self.eight_over_pi_sqr = 8/np.pi**2
        
        self.change_dtype(dtype)
    
    
    def change_dtype(self, dtype: Dtype):
        self.dtype = dtype
        if self.dtype == np.float32:
            self.min_amp = -1
            self.max_amp = 1
        else:
            i = np.iinfo(self.dtype)
            self.min_amp = i.min+1
            self.max_amp = i.max-1
    
    
    # caches the waves so if you had to generate a note multiple times its not gonna take long to execute
    # you can't use the lru_cache from the functools module because waves are stored as numpy arrays and numpy arrays are not hashable
    # so this decorator will save a tuple of that numpy array in self.existed_notes and convert it back to a numpy array each time you want to use that wave
    def cache_wave(wave_type: str) -> SoundBuffer:
        """caches the waves so if you had to generate a note multiple times it's gonna use the cached wave.
        you can't use the `lru_cache` from the `functools` module because waves are stored as numpy arrays and numpy arrays are not hashable, 
        so this decorator will store the numpy array as a tuple in `self.existed_notes` and convert it back to a numpy array each time you want to use that wave
        \nreturns the cached value if available, otherwise caches the returned wave"""
        def decorator(func: Wave) -> SoundBuffer:
            def wrapper(self: Self, freq: float, dur: float, vol: float):
                # Error if frequency is negative
                if freq < 0:
                    raise f"frequency must be positive number, given frequency: {freq}"
                
                name = f"{wave_type}|{freq}|{dur}|{self.dtype}"
                if name in self.existed_notes.keys():
                    wave: SoundBuffer = vol * np.array(self.existed_notes[name], dtype=self.dtype)
                    return wave
                
                temp = func(self, freq, dur, self.max_amp)
                result: SoundBuffer = func(self, freq, dur, vol*self.max_amp)
                result = self._fix_amp(result, -vol, vol)
                self.existed_notes[name] = self.array_to_tuple(temp)
                
                return result
            return wrapper
        return decorator

    @cache_wave("sine")
    def sine_wave(self, freq:float, dur:float, vol: float) -> SoundBuffer:
        """creates a sine-wave based on the given frequency, duration and amplitude."""
        
        wave = (vol * np.sin(self.tau * freq / self.default_sample_rate * np.arange(self.default_sample_rate * dur))).astype(self.dtype)
        return wave
    
    @cache_wave("sqr")
    def square_wave(self, freq:float, dur:float, vol: float) -> SoundBuffer:
        """creates a square-wave based on the given frequency, duration and amplitude\n
        a square wave is typically generated by adding all the odd harmonics (3, 5, 7, 9...) to a fundamental frequency\n
        each harmonic is added with a lower amplitude which causes the overall wave amplitude to change, so at the end the amplitude is multiplied by `4/pi` to fix it."""
        
        # -- creating the fundumental note --#
        fund = self.tau * freq / self.default_sample_rate * np.arange(self.default_sample_rate * dur)
        buf = np.sin(fund)
        
        n = np.ceil(20_000 / freq).astype(np.int16)
        for h in range(3, n, 2):
            #-- adding the harmonics --#
            buf += np.sin(fund*h) / h
        
        wave = (self.four_over_pi*vol*buf).astype(self.dtype)
        return wave
    
    @cache_wave("fast_sqr")
    def fast_square_wave(self, f: float, dur: float, vol: float) -> SoundBuffer:
        """the result is same as square_wave but it's time complexity is O(1)"""
        return vol * ((-1)**np.floor(2 * f / self.default_sample_rate * np.arange(dur * self.default_sample_rate))).astype(self.dtype)
    
    @cache_wave("tri")
    def triangle_wave(self, freq:float, dur:float, vol: float) -> SoundBuffer:
        """creates a triangle wave based on the given frequency, duration and amplitude\n
        a triangle-wave is typically generated by adding all the odd harmonics (3, 5, 7, 9...) to a fundamental frequency, but every second one is negative.\n
        each harmonic is added with a lower amplitude which causes the overall amplitude to change, so at the end the amplitude is multiplied by `8/pi^2` to fix it."""
        
        fund = self.tau * freq / self.default_sample_rate * np.arange(self.default_sample_rate * dur)
        buf = np.sin(fund)
        
        n = np.ceil(10_000 / freq).astype(np.int16)
        for h in range(1, n):
            harmonic = (2*h+1)
            buf += (-1)**h / (harmonic*harmonic) * np.sin(fund * harmonic) 
        
        wave = ((self.eight_over_pi_sqr)*vol*buf).astype(self.dtype)
        return wave
    
    @cache_wave("fast_tri")
    def fast_triangle_wave(self, freq:float, dur:float, vol: float) -> SoundBuffer:
        """the result is same as triangle_wave but it's time complexity is O(1)"""
        return (self.two_oper_pi * vol * np.arcsin(np.sin(self.tau * freq / self.default_sample_rate * np.arange(self.default_sample_rate * dur)))).astype(self.dtype)
    
    @cache_wave("saw")
    def sawtooth_wave(self, freq:float, dur:float, vol: float) -> SoundBuffer:
        """creates a sawtooth-wave based on the given frequency, duration and amplitude\n
        a sawtooth wave is typically generated by adding all the harmonics to a fundamental frequency with the odd harmonics being negative (2, -3, 4, -5...)\n
        each harmonic is added with a lower amplitude which causes the overall amplitude to change so at the end the amplitude is multiplied by `-(2/pi)`
        >>> vol * -self.two_oper_pi * buf"""
        
        fund = self.tau * freq / self.default_sample_rate * np.arange(self.default_sample_rate * dur) 
        buf = np.sin(fund) * -1
        
        n = np.ceil(20_000 / freq).astype(np.int16)
        for h in range(2, n):
            buf += (-1)**h / h * np.sin(fund * h) 
        
        wave = (vol * -self.two_oper_pi * buf).astype(self.dtype)
        return wave
    
    @cache_wave("fast_saw")
    def fast_sawtooth_wave(self, freq: float, dur: float, vol: float) -> SoundBuffer:
        """the result is same as sawtooth_wave but it's time complexity is O(1)"""
        T = 1/freq / 2 * self.default_sample_rate
        t = freq * np.arange(dur * self.default_sample_rate + T) / self.default_sample_rate
        wave = (t - np.floor(t) - 0.5)[int(T):]
        return 2 * vol * wave.astype(self.dtype)
    
    def smooth_saw_wave(self, freq:float, dur:float, vol: float, smoothness: float=2.5) -> SoundBuffer:
        """creates a wave, like the saw-wave but without the sharp points"""
        
        fund = self.tau * np.arange(self.default_sample_rate * dur) * freq / self.default_sample_rate
        buf = np.sin(fund) * -1
        
        n = np.ceil(20_000 / freq).astype(np.int16)
        for h in range(2, n):
            buf += (-1)**h / h**smoothness * np.sin(fund * h)
        
        wave = (vol * -self.two_oper_pi * buf).astype(self.dtype)
        return wave
    
    @cache_wave("organ")
    def organ(self, freq:float, dur:float, vol: float) -> SoundBuffer:
        """creates an organ like sound based on the given frequency, duration and amplitude or volume"""
        
        fund = self.tau * freq / self.default_sample_rate * np.arange(self.default_sample_rate * dur)
        buf = np.sin(fund)
        buf += 0.9 * np.sin(fund * 2)
        buf += np.sin(fund * 4)
        buf += 0.6 * np.sin(fund * 6)
        buf += 0.7 * np.sin(fund* 16)
        buf += 0.5 * np.sin(fund * 20)
        buf += 0.3 * np.sin(fund* 24)

        wave: SoundBuffer = vol * (buf*0.334).astype(self.dtype)
        return wave
    
    @cache_wave("marimb")
    def marimba(self, freq:float, dur:float, vol: float) -> SoundBuffer:
        """creates a "not even close to marimba" sound based on the given frequency, duration and amplitude or volume\n
        warning!: very annoying sound"""
        
        fund = self.tau * freq / self.default_sample_rate * np.arange(self.default_sample_rate * dur)
        buf = np.sin(fund)
        buf += 0.75 * np.sin(fund * 10)
        buf += 0.5  * np.sin(fund * 20)
        buf += 0.25 * np.sin(fund * 30)
        
        wave = vol * (buf/4).astype(self.dtype)
        return self.fade_out(wave, wave.size)
    
    @cache_wave("tst")
    def test(self, freq:float, dur:float, vol: float) -> SoundBuffer:
        fund = self.tau * freq / self.default_sample_rate * np.arange(self.default_sample_rate * dur)
        buf = np.sin(fund)
        
        n = np.ceil(20_000 / freq).astype(np.int16)
        for h in range(1, 1000):
            buf += (-1)**h / h * np.sin(fund * h)
        
        wave = (vol * (0.5 - self.rev_pi*buf)).astype(self.dtype)
        return wave
    
    
    def _fix_amp(self, wave: SoundBuffer, min_amp=None, max_amp=None) -> SoundBuffer:
        if not min_amp: min_amp = self.min_amp
        if not max_amp: max_amp = self.max_amp
        
        wave[wave > max_amp] = max_amp
        wave[wave < min_amp] = min_amp
        return wave
    
    
    def _generate_fade_buffer(self, fade_len:int, start=0, stop=np.pi, dtype: Dtype|None=None) -> SoundBuffer:
        if not dtype:
            dtype = self.dtype
        
        return ((1 - np.cos(np.linspace(start, stop, fade_len))) * 0.5).astype(dtype)
    
    
    def fade_in(self, buffer: SoundBuffer, fadein_len:int) -> SoundBuffer:
        fadein = self._generate_fade_buffer(fadein_len, dtype=buffer.dtype)
        buffer[:fadein_len] *= fadein
        return buffer
    
    
    def fade_in_secs(self, buffer: SoundBuffer, secs: float, sample_rate:int|None=None) -> SoundBuffer:
        if not sample_rate: sample_rate = self.default_sample_rate
        
        fadein_nsamples = int(secs * sample_rate)
        return self.fade_in(buffer, fadein_nsamples)
    
    
    def fade_out(self, buffer: SoundBuffer, fadeout_len:int) -> SoundBuffer:
        fadein = self._generate_fade_buffer(fadeout_len, dtype=buffer.dtype)
        fadeout = np.flip(fadein)
        buffer[-fadeout_len:] *= fadeout
        
        return buffer
    
    
    def fade_out_secs(self, buffer: SoundBuffer, secs: float, sample_rate:int|None=None) -> SoundBuffer:
        if not sample_rate: sample_rate = self.default_sample_rate
        
        fadeout_nsamples = int(secs * sample_rate)
        return self.fade_out(buffer, fadeout_nsamples)
    
    
    def fade_in_out(self, buffer: SoundBuffer, fadein_len:int, fadeout_len:int) -> SoundBuffer:
        buffer = self.fade_in(buffer, fadein_len)
        buffer = self.fade_out(buffer, fadeout_len)
        return buffer
    
    
    def fade_in_out_secs(self, buffer: SoundBuffer, fadein_secs: float, fadeout_secs: float, sample_rate:int|None=None) -> SoundBuffer:
        if not sample_rate: sample_rate = self.default_sample_rate
        
        buffer = self.fade_in_secs(buffer, fadein_secs, sample_rate)
        buffer = self.fade_out_secs(buffer, fadeout_secs, sample_rate)
        return buffer
    
    
    def staccato(self, wave: SoundBuffer, play_time: float=0.75) -> SoundBuffer:
        playing = len(wave)*play_time
        resting = (1-play_time) * (wave.size/self.default_sample_rate)
        return np.append(wave[0:int(playing)], self.generate_note_buffer(0, self.sine_wave, resting))
    
    
    def array_to_tuple(self, np_array: SoundBuffer) -> Tuple:
        """Iterates recursivelly."""
        try:
            return tuple(self.array_to_tuple(_) for _ in np_array)
        except TypeError:
            return np_array


class Export:
    def __init__(self) -> None:
        pass
    
    # converts a float32 array to an int type
    def float2pcm(self, sig: np.ndarray, dtype: Literal["int32", "int16", "uint8"]="int16") -> SoundBuffer:
        """gets a float dtype array as input, converts it to int and returns the converted array"""
        
        sig = np.asarray(sig)
        if sig.dtype.kind != 'f':
            raise TypeError("'sig' must be a float array")
        dtype = np.dtype(dtype)
        if dtype.kind not in 'iu':
            raise TypeError("'dtype' must be an integer type")

        i = np.iinfo(dtype)
        abs_max: int = 2 ** (i.bits - 1)
        offset = i.min + abs_max
        return (sig * abs_max + offset).clip(i.min, i.max).astype(dtype)
    
    # converts an int type array to a float32
    def pcm2float(self, sig: np.ndarray) -> SoundBuffer:
        """gets an int dtype array as input, converts it to float and returns the converted array"""
        
        sig = np.asarray(sig)
        if sig.dtype.kind not in 'iu':
            raise TypeError("'sig' must be an array of integers")

        i = np.finfo(np.float32)
        abs_max: int = 2 ** (i.bits - 1)
        offset = i.min + abs_max
        return (sig.astype(np.float32) - offset) / abs_max
        
    # exports to .erfan file which is completely useless but you can play them with the app.py file adn you can convert them to wav file which is actualy useful
    def export_to_erfan(self, file_name:str, buffer: np.ndarray|bytes, sample_rate: int, dtype, channels: int) -> None:
        """exports to \".erfan\" file which can be played with the app in my github https://github.com/erfan-ops"""
        
        if type(buffer) != bytes:
            dtype = buffer.dtype
            if dtype == np.uint8 or dtype == "uint8":
                audio_format = 1
            elif dtype == np.int16 or dtype == "int16":
                audio_format = 2
            elif dtype == "int24":
                audio_format = 3
            elif dtype == np.float32 or dtype == "float32":
                audio_format = 4
            else:
                raise ValueError(f"Incorrect dtype: {dtype}\nvalid options are: \"uint8, int16, int24, float32\"")
            
        
        with open(file_name, "wb") as f:
            f.write(sample_rate.to_bytes(4, "little"))
            f.write(audio_format.to_bytes(2, "little"))
            f.write(channels.to_bytes(2, "little"))
            
            if type(buffer) == np.ndarray:
                buffer = buffer.tobytes()
            
            f.write(buffer)
    
    
    def export_to_wav(self, file_path:str, buffer: np.ndarray|bytes, sample_rate: int, dtype) -> None:
        if type(buffer) == bytes:
            buffer = np.frombuffer(buffer[8:], dtype=dtype)
        
        wf.write(file_path, sample_rate, buffer)
    
    # reads and return the bytes containing the sound from an erfan file
    def read_from_erfan(self, file_name: str) -> SoundBuffer:
        """read and returns data from \".erfan\" file"""
        with open(file_name, "rb") as f:
            data = f.read()
            sample_rate = int.from_bytes(data[0:4], "little")
            sampwidth = int.from_bytes(data[4:6], "little")
            channels = int.from_bytes(data[6:8], "little")
            
            self.stream = self.AUDIO_OBJECT.open(format=self.AUDIO_OBJECT.get_format_from_width(sampwidth),
                                                 channels=channels,
                                                 rate=sample_rate,
                                                 output=True)
            return np.frombuffer(data[8:], self.get_sampwidth_from_int(sampwidth))
    
    
    def erfan_to_wav(self, file_name: str, dir: str="", dtype=np.float32) -> None:
        """converts a \".erfan\" file to a \".wav\" file"""
        file_short_name = file_name.removesuffix(".erfan")
        with open(file_name, "rb") as f:
            data = f.read()
            sample_rate = int.from_bytes(data[0:4], "little")
            data = np.frombuffer(data[8:], dtype=dtype)
        
        wf.write(f"{dir}{file_short_name}.wav", sample_rate, data)
    
    
    def wav_to_erfan(self, file_name: str) -> None:
        """converts a \".wav\" file to a \".erfan\""""
        file_short_name = file_name.removesuffix(".wav")
        with open(file_name, "rb") as f:
            data = f.read()
            n_channels = int.from_bytes(data[22:24], "little")
            dtype = int.from_bytes(data[20:22], "little")
            sample_rate = int.from_bytes(data[24:28], "little")
            data = data[42:]
        
        with open(f"{file_short_name}.erfan", "wb") as f:
            f.write(sample_rate.to_bytes(4, "little"))
            f.write(dtype.to_bytes(2, "little"))
            f.write(n_channels.to_bytes(2, "little"))
            f.write(data)

    # converts a float32 wav file to an int type
    def wav_float32_to_int(self, file_path: str, dtype: Literal["int32", "int16", "uint8"]="int16") -> None:
        """converts a \".wav\" file with float32 dtype to an int type"""
        
        with open(file_path, "rb") as f:
            sample_rate, data = wf.read(file_path)
            if data.dtype != "float32":
                raise f"This function is only used to conver \"float32\" dtype to \"int\" not <{data.dtype}>"
            
            wf.write(f"{file_path}.wav", sample_rate, self.float2pcm(data, dtype))

    
    def get_sampwidth_from_str(self, dtype: Literal["float32", "int24", "int16", "uint8"]) -> int:
        match dtype:
            case "uint8":
                width = 1
            case "int16":
                width = 2
            case "int24":
                width = 3
            case "float32":
                width = 4
            case _:
                return 4
        
        return width
    
    
    def get_sampwidth_from_int(self, dtype: Literal[1, 2, 3, 4]) -> str:
        if not (0 < dtype < 5):
            raise f"Invalid data type {dtype}"
        
        match dtype:
            case 1:
                width = "uint8"
            case 2:
                width = "int16"
            case 3:
                width = "int24"
            case 4:
                width = "float32"
        
        return width


class Music(Sounds, Export):
    """used for creating and playing sounds"""
    def __init__(self, middle_a=440, tempo=60, sample_rate=48000, tune=12) -> None:
        super().__init__(sample_rate)
        self.sample_rate: int = sample_rate
        self.AUDIO_OBJECT = pyaudio.PyAudio() # making an audio object that we,ll need to play sounds
        self.TUNE = tune                       # using 12 tone equal temperament
        self.MIDDLE_A = middle_a                  # middle a has a frecuency of 440 hertz
        self._NOTES: Notes = Notes()                 # a directory that has all the notes that we can use in it and R is just for rest
        self.NOTE_NAMES: List[str] = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        self.FULL_NOTE_NAMES = []
        self.DEFAULT_DURATION = 1
        self.DEFAULT_VOLUME = self.max_amp
        self.tempo = tempo
        self.channels: int = 1
    
    
    # you have to use this function to initialize before playing any note.
    def init(self) -> None:
        super().__init__(self.sample_rate)
        self.SEMI_TONE: float = np.power(2, (1/self.TUNE)) # a semitone in a 12 equal temperament is 2 to the power of 1/12, that means in a 6 equal temperament system a semitone is 2^(1/6)
        self.generate_note_names()
        self.assign_middle_a()
        self.assign_frequencies()
        self.init_output_stream()
        self.init_input_stream()
    
    
    def init_output_stream(self,
                           samp_width:int|str="float32",
                           n_channels:int|None=None,
                           sample_rate:int|None=None) -> None:
        
        if not n_channels:
            n_channels = self.channels
        if not sample_rate:
            sample_rate = self.sample_rate
        
        self.stream = self.config_stream(samp_width=samp_width,
                                         channels=n_channels,
                                         sample_rate=sample_rate)
    
    
    def init_input_stream(self,
                          samp_width: int|str="float32",
                          n_channels: int=1,
                          sample_rate: int|None=None,
                          chunk:int=3200) -> None:
        if not sample_rate:
            sample_rate = self.sample_rate
        
        if type(samp_width) == str:
            samp_width = self.get_sampwidth_from_str(dtype=samp_width)
        
        self.input_stream = self.AUDIO_OBJECT.open(format=self.AUDIO_OBJECT.get_format_from_width(samp_width),
                                                   channels=n_channels,
                                                   rate=sample_rate,
                                                   input=True,
                                                   frames_per_buffer=chunk)
        
        self.input_rate = sample_rate
        self.input_chunk = chunk
        self.input_dtype = self.get_sampwidth_from_int(samp_width)
        self.input_channels = n_channels
    
    
    def config_stream(self, samp_width: int|str, channels: int, sample_rate: int) -> pyaudio.Stream:
        if type(samp_width) == str:
            samp_width = self.get_sampwidth_from_str(dtype=samp_width)
        
        if not samp_width in (8, 32):
            samp_width = self.AUDIO_OBJECT.get_format_from_width(samp_width)
        
        return self.AUDIO_OBJECT.open(format=samp_width,
                                      channels=channels,
                                      rate=sample_rate,
                                      output=True)
    
    
    def generate_note_names(self) -> None:
        # the number of note names has to be the same as the tune so if its less its not going to work.
        if self.FULL_NOTE_NAMES and (len(self.FULL_NOTE_NAMES) < self.TUNE):
            raise Exception(f"Not enough note names for base {self.TUNE} scale")

        for n in self.NOTE_NAMES:
            if len(self.FULL_NOTE_NAMES) == self.TUNE:
                break
            self.FULL_NOTE_NAMES.append(n)
            
            # we don't need B# and E# because we have enharmonic notes for them,
            # but if you want to use those you can by changing the notes manually.
            if n != "B" and n != "E":
                self.FULL_NOTE_NAMES.append(f"{n}#")
    
    
    # if you want to change the middle a in the middle of a song you need to use this function
    def assign_middle_a(self, new_frequency:int|float=None) -> None:
        if new_frequency:
            self.MIDDLE_A = new_frequency
        self.BASS_A = self.MIDDLE_A
        self._hbl = 1
        
        exponent = int(np.log2(self.MIDDLE_A / 20))
        self.BASS_A /= 2**exponent
        self._hbl = exponent+1
    
    # you need to call the "assign_frequencies" function after it to change all the note's frecuencies based on the new middle a
    # although you can just change the self.middle_a value and use init after it, which will also call this function.
    
    
    # this function will create a dictionary of all the notes with a range of 20- to 20'000 frequencies.
    # it is depended on the middle_a and the tune that you're using.
    def assign_frequencies(self) -> None:
        octave = 0
        frequency = 0
        
        # this loop will create the directory and the name of notes are formatted like this "'{note}{octave}':frecuency"
        while frequency <= 20000:
            for i in range(self.TUNE):
                frequency = self.BASS_A * np.power(self.SEMI_TONE, i) * (np.power(2, octave)).astype(np.float32)
                
                if frequency > 20000:
                    break
                
                elif frequency >= 20:
                    self._NOTES[self.FULL_NOTE_NAMES[i%self.TUNE]+str(octave-(self._hbl-5))] = frequency

            octave += 1
    
    
    def fix_duration(self, duration:str|float=0) -> float:
        if not duration:
            duration = self.DEFAULT_DURATION
        
        elif str(duration)[-1].lower() != "s":
            duration = 60 / self.tempo * float(duration)
        else:
            duration = float(duration[:-1])
        
        return duration
    
    
    def fix_volume(self, volume:float=0) -> float:
        if not volume:
            volume = self.max_amp/2
        
        elif volume > self.max_amp or volume < self.min_amp:
            raise f"volume must be between {self.min_amp} and {self.max_amp}"
        
        return volume
    
    
    def get_file_data(self, file_path: str) -> Tuple[SoundBuffer, int]:
        """gets the file data and returns a tuple[wave, sample_rate]
        you ca access other information as shown below
        
        >>> channels = data.ndim
        >>> sample_width = data.dtype"""
        
        fformat = splitext(file_path)[1]
        fformat = fformat.removeprefix(".")
        
        if fformat == "erfan":
            with open(file_path, "rb") as f:
                data = f.read()
                sample_rate = int.from_bytes(data[0:4], "little")
                dtypen = int.from_bytes(data[4:6], "little")
            match dtypen:
                case 1:
                    dtype = np.uint8
                case 2:
                    dtype = np.int16
                case 4:
                    dtype = np.float32
                case _:
                    dtype = np.float32
            
            data = np.frombuffer(data[8:], dtype=dtype)
            return (data, sample_rate)
        
        #-- for adts files --#
        elif fformat in ["aac", "wma", "m4a"]:
            sound = AudioSegment.from_file(file_path, fformat)
            
            match sound.sample_width:
                case 1:
                    dtype = np.uint8
                case 2:
                    dtype = np.int16
                case _:
                    dtype = np.float32
            data = np.frombuffer(sound._data, dtype=dtype)
            return (data, sound.frame_rate)
            
        
        #-- other files such as mp3, ogg, wav, aiff, flac --#
        else:
            return sfRead(file_path)
    
    
    def pitch_shift(self, wave: SoundBuffer, n_semitones: float, sample_rate: int|None=None, semitones_per_octave: int=12) -> SoundBuffer:
        """shifts the pitch by the given number of semitones"""
        if not sample_rate:
            sample_rate = self.default_sample_rate
        
        return effect.pitch_shift(wave,
                                  sr=sample_rate,
                                  n_steps=n_semitones,
                                  bins_per_octave=semitones_per_octave)
    
    
    # creates a note buffer but doesn't turn it into bytes
    def generate_note_buffer(self, note:Note, wave_type: Wave, duration:str|float=0, volume:float=0) -> SoundBuffer:
        """creates a sound wave based on the given note, wave type, duration and volume\n
        ### parameter note:
        can be a float as a frequency, or a string representing the note name forexample: \"A4\" or \"c#3\" or 220
        ### duration:
        can be an int representing the duration in beats (so it can be different based on the tempo)
        or can be a string representing the duration in seconds like this: \"2s\"
        ### note!:
        if duration or volume are not passed as arguments when using the function, it will use `self.DEFAULT_DURATION` and `self.DEFAULT_VOLUME`, which you can change as well.
        ### example:
        >>> import soundtools
        >>> m = soundtools.Music()
        >>> m.init()
        >>> note = m.generate_note_buffer("a4", m.sine_wave, \"1.5s\", 1)
        >>> m.play_buffer(note)"""
        
        duration = self.fix_duration(duration)
        volume = self.fix_volume(volume)
        if str(note)[0].isdigit():
            f = float(note)
        else:
            f = self._NOTES[note]
        
        buf = wave_type(f, duration, volume)
        return buf
    
    
    # creates a chord buffer but doesn't turn it into bytes
    def generate_chord_buffer(self, notes: Iterable[Note], wave_type: Wave, duration:str|float=0, volume:float=0) -> SoundBuffer:
        """creates a sound wave based on the given notes, wave type, duration and volume\n
        ### parameter notes:
        is an iterable of floats as a frequency, or a strings representing the note name forexample:
        >>> import soundtools
        >>> m = soundtools.Music()
        >>> m.init()
        >>> chord = generate_chord_buffer((220, \"C#3\", \"e3\"), m.sine_wave, 1.5, 1)
        >>> m.play_buffer(chord)"""
        
        buf = self.generate_note_buffer(notes[0], wave_type, duration, volume)
        for n in notes[1:]:
            buf += self.generate_note_buffer(n, wave_type, duration, volume)
        return (buf/len(notes))
    
    
    def record(self, secs: float):
        total_frames: bytes = bytes()
        n_chunks = int(self.input_rate/self.input_chunk*secs)
        
        for _ in range(0, n_chunks):
            data = self.input_stream.read(self.input_chunk)
            total_frames += data
        
        self.input_stream.stop_stream()
        
        buf = np.frombuffer(total_frames, self.input_dtype)
        return buf
    
    
    def add_buffers(a: SoundBuffer, b: SoundBuffer, keep_volume: bool=True) -> SoundBuffer:
        s = a.size if a.size < b.size else b.size
        result = (a[:s] + b[:s])
        if keep_volume: result /= 2
        return result
    
    
    def add_multiple_buffers(*buffers: SoundBuffer, keep_volume: bool=True):
        s: int = buffers[0].size
        for buffer in buffers[1:]:
            if buffer.size < s:
                s = buffer.size
        
        s_bufs: SoundBuffer = buffers[0][:s]
        
        for buffer in buffers[1:]:
            s_bufs += buffer[:s]
        
        if keep_volume: s_bufs /= len(buffers)
            
        return s_bufs
    
    # creates a note buffer and plays it
    def play(self, note:str|float|int, wave_type: Wave, duration:str|float=0, volume:float=0) -> None:
        """generates then plays a note with the given arguments"""
        buf: bytes = self.generate_note_buffer(note, wave_type, duration, volume).tobytes()
    
        self.play_buffer(buf)
    
    
    # plays a buffer
    def play_buffer(self, wave: SoundBuffer|bytes, chunk:int=6400, dtype:Dtype|None=None) -> None:
        """plays the given wave"""
        
        if type(wave) != bytes:
            wave = wave.tobytes()
        
        size = len(wave)
        
        if size < chunk:
            self.stream.write(wave)
        
        n_chunks = int(size / chunk)
        for i in range(n_chunks):
            b = wave[i*chunk : (i+1)*chunk]
            self.stream.write(b)
        
        b = wave[(i+1)*chunk : ]
        self.stream.write(b)
    
    
    # created a chord sound buffer and plays it
    def play_chord(self, notes: Iterable[Note], wave_type: Wave, duration:str|float=0, volume:float=0) -> None:
        """generates then plays a chord with the given arguments"""
        buf = self.generate_chord_buffer(notes, wave_type, duration, volume).tobytes()
        
        self.play_buffer(buf)
    
    
    def play_erfan(self, file_name: str) -> None:
        self.play_buffer(self.read_from_erfan(file_name))
    
    
    def play_wav(self, file_name: str) -> None:
        sample_rate, data = wf.read(file_name)
        match data.dtype:
            case np.uint8:
                sampwidth = 1
            case np.int16:
                sampwidth = 2
            case "int24":
                sampwidth = 3
            case np.float32:
                sampwidth = 4
            
        self.stream = self.AUDIO_OBJECT.open(format=self.AUDIO_OBJECT.get_format_from_width(sampwidth),
                                             channels=data.ndim,
                                             rate=sample_rate,
                                             output=True)
        self.play_buffer(data)
    
    
    def visualize_sound(self, wave: SoundBuffer, sample_rate: int|None=None) -> None:
        """uses matplotlib.pyplot to visualize sound waves"""
        
        if not sample_rate: sample_rate = self.sample_rate
        
        times = np.linspace(0, wave.size/sample_rate, wave.size)
        duration = wave.size / sample_rate
        
        plt.figure(figsize=(15, 5))
        plt.plot(times, wave)
        plt.title('wave:')
        plt.ylabel('Signal Value')
        plt.xlabel('Time (s)')
        plt.xlim(0, duration)
        plt.show()
    
    
    def show_frequency_spectrum(self, wave: SoundBuffer, sample_rate: int) -> None:
        """uses matplotlib.pyplot to show the frequency spectrum"""
        duration = wave.size / sample_rate
        
        plt.figure(figsize=(15, 5))
        plt.specgram(wave, Fs=sample_rate, vmin=-20, vmax=50)
        plt.title('wave')
        plt.ylabel('Frequency (Hz)')
        plt.xlabel('Time (s)')
        plt.xlim(0, duration)
        plt.colorbar()
        plt.show()
    
    
    def done(self) -> None:
        """will stop and close the stream and terminate the audio_object (basicly closes everything)"""
        if self.stream.is_active():
            self.stream.stop_stream()
        if self.input_stream.is_active():
            self.input_stream.stop_stream()
        
        self.stream.close()
        self.input_stream.close()
        self.AUDIO_OBJECT.terminate()
