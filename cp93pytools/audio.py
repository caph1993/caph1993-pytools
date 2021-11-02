from .methodtools import cached_property, cached_method
import warnings


class MissingPackage(UserWarning):
    pass


try:
    import ffmpeg
except ImportError:
    warnings.warn('pip3 install ffmpeg-python', MissingPackage)
try:
    import numpy as np
except ImportError:
    warnings.warn('pip3 install numpy', MissingPackage)
try:
    from scipy.io import wavfile
except ImportError:
    warnings.warn('pip3 install scipy', MissingPackage)

import os
import ffmpeg
import numpy as np
from scipy.io import wavfile


def ffmpeg_run(out):
    try:
        ffmpeg.run(out, capture_stdout=True, capture_stderr=True,
                   overwrite_output=True)
    except ffmpeg.Error as e:
        print(e.stderr.decode())
        raise
    return


class Sequence(np.ndarray):

    rate: float

    def __new__(cls, arr, rate: float):
        obj = np.asarray(arr).view(cls)
        obj.rate = rate  # (sample rate Hz)
        return obj

    @classmethod
    def from_wav(cls, file):
        rate, data = wavfile.read(file)
        return cls(data, rate=rate)

    def to_wav(self, file):
        return wavfile.write(file, rate=self.rate, data=self)

    @cached_property
    def duration(self):
        return len(self) / self.rate

    def _float_index(self, idx_float):
        idx_floor = np.floor(idx_float).astype(int)
        p_next = idx_float - idx_floor
        idx_next = np.minimum(idx_floor + 1, len(self) - 1)
        arr = self[idx_floor] * (1 - p_next) + self[idx_next] * p_next
        return self.rated(arr.astype(self.dtype))

    def rated(self, arr):
        return self.__class__(arr, self.rate)

    def clip_cast(self, arr):
        if arr.dtype != self.dtype:
            lo = np.ma.maximum_fill_value(self.dtype)
            hi = np.ma.minimum_fill_value(self.dtype)
            arr = np.clip(arr, lo, hi).astype(self.dtype)
        return self.__class__(arr, self.rate)

    def total_rms(self):
        return float(np.sqrt(np.mean(np.square(self, dtype=np.float32))))

    def moving_average(self, width: float):
        n = len(self)
        r = max(1, int(0.5 + width * self.rate / 2))
        assert r > 0 and n > 1
        idxlo = np.maximum(np.arange(n) - r, 0)
        idxhi = np.minimum(np.arange(n) + r, n - 1)
        cum = np.cumsum(self)
        mav = (cum[idxhi] - cum[idxlo]) / (idxhi - idxlo)
        return self.rated(mav)

    def envelope(self, width: float):
        rms = self.rated(np.square(self.astype(np.float32)))
        mav = np.sqrt(rms.moving_average(width))
        return self.rated(mav)

    @cached_property
    def _cached_std_envelope(self):
        env = self.envelope(0.5)
        #env = env.moving_average(3)
        return self.rated(env / env.std())

    @cached_method(maxsize=5)
    def cached_resample(self, rate: float):
        return self.resample(rate)

    @cached_property
    def time(self):
        return np.arange(len(self)) / self.rate

    def plot(self, ax=None):
        import matplotlib.pyplot as plt
        if ax == None:
            ax = plt.gca()
        return ax.plot(self.time, self)

    @classmethod
    def from_video(cls, file, rate, mono=True):
        tmp = f'{file}.tmp.wav'
        try:
            out = ffmpeg.input(file)['a:0']
            out = ffmpeg.output(out, tmp, ar=rate, ac=int(mono))
            ffmpeg_run(out)
            seq = cls.from_wav(tmp)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        return seq

    def normalized_to(self, ref, width: float):
        that = np.maximum(ref.envelope(width), 1e-3)
        this = np.maximum(self.envelope(width), 1e-3)
        return self.clip_cast(self * (that / this))

    def to_ogg(self, file):
        assert file.endswith('.ogg'), f'File {file} must end in .ogg'
        wav = f'{file}.wav'
        self.to_wav(wav)
        ffmpeg_run(ffmpeg.output(ffmpeg.input(wav), file))
        os.remove(wav)
        return

    def resample(self, out_rate: float):
        in_duration = self.duration
        out_duration = self.duration * out_rate / self.rate
        out = self.respeed(in_duration, out_duration)
        out.rate = out_rate
        return out

    def respeed(self, in_duration: float, out_duration: float):
        '''
        output signal has out_duration and same rate as self, but
        the content resembles self from 0 to in_duration (at different playback speed)
        '''
        assert 0 < min(
            in_duration,
            out_duration), f'Non sense: {in_duration}s {out_duration}s'
        in_samples = int(0.5 + in_duration * self.rate)
        out_samples = int(0.5 + out_duration * self.rate)
        if out_duration == in_duration:
            seq = self.rated(self[:in_samples])
        else:
            assert 0 < out_samples < 3e8, (out_samples, in_samples, in_duration,
                                           out_duration)
            idx = np.linspace(0, in_samples, out_samples, endpoint=False)
            seq = self._float_index(idx)
        return seq

    def _synced_to_plots(self, ref, start, end):
        this, that = self._synced_to_valid(ref, start, end)
        import matplotlib.pyplot as plt
        plt.plot(this.time, this)
        plt.plot(that.time, that, alpha=0.5)
        plt.show()
        #plt.scatter(this, that, alpha=0.1, marker='.')
        #plt.show()
        return

    def _synced_to_corr(self, ref, start, end):
        x, y = self._synced_to_valid(ref, start, end)
        C = np.corrcoef(x, y)
        total_duration = (self.duration + ref.duration)
        valid_duration = (x.duration + y.duration)
        return C[0, 1] * valid_duration / total_duration

    def _synced_to_valid(self, ref, start, end):
        'trims self and ref to the valid interval (no padding)'
        this, lo, hi = self._synced_to(ref, start, end)
        this = self.rated(this[:hi - lo])
        that = self.rated(ref[lo:hi])
        return this, that

    def _synced_to(self, ref, start, end):
        seq = self
        if seq.rate != ref.rate:
            seq = seq.cached_resample(ref.rate)
        in_duration = seq.duration
        out_duration = end - start
        seq = seq.respeed(in_duration, out_duration)
        lo = int(start * ref.rate)
        if lo < 0:
            seq = self.rated(seq[-lo:])
            lo = 0
        hi = min(int(end * ref.rate), lo + len(seq), len(ref))
        return seq, lo, hi

    def synced_to(self, ref, start, end, padcopy=True, width_normalize=10,
                  width_softpad=2, width_softstart=0.2):
        '''
        sync self to ref.
        out starts at start and ends at end (seconds).
        out is stretched if neccesary.
        out is trimmed and padded to fill (0, self.duration) 
        out is padded with a copy of ref if padcopy==True
        out padding is soften around border
        '''
        seq, lo, hi = self._synced_to(ref, start, end)
        out = self.rated(np.zeros_like(ref))
        out[lo:hi] = seq[:hi - lo]
        if width_normalize > 0:
            out = out.normalized_to(ref, width_normalize)
        if padcopy:
            out[:lo] = ref[:lo]
            out[hi:] = ref[hi:]
        if width_softpad > 0:
            k = min(int(ref.rate * width_softpad), hi - lo)
            p = np.linspace(0, 1, k)
            out[lo:lo + k] = p * out[lo:lo + k] + (1 - p) * ref[lo:lo + k]
            out[hi - k:hi] = (1 - p) * out[hi - k:hi] + p * ref[hi - k:hi]
        if width_softstart > 0:
            k = min(int(ref.rate * width_softstart), len(out) // 2)
            p = np.linspace(0, 1, k)
            out[:k] = p * out[:k]
            out[-k:] = (1 - p) * out[-k:]
        return out

    @cached_property
    def _std_envelope(self):
        env = self.envelope(5)
        env /= self.envelope(60)
        env = (env / env.mean() - 1) / env.std()
        return self.rated(env)

    def _sync_to_delays(self, ref):
        start = (ref.duration - self.duration) / 2
        rend = -start
        d_ref = ref.duration
        d_self = self.duration
        this = _this = self._std_envelope.resample(200)
        that = _that = ref._std_envelope.resample(200)
        radius = max(3, 1.3 * abs(start))
        nparts = 31
        corr = 0
        a = start
        b = rend
        while radius > 0.001:
            rate = min(nparts / radius, 200)
            this = _this.resample(rate)
            that = _that.resample(rate)
            points = []
            search = radius * np.linspace(-1, 1, nparts)
            for a in search + start:
                for b in search + rend:
                    d = d_ref + b - a
                    drastic = d <= 0 or max(d / d_self, d_self / d) >= 1.2
                    if not drastic:
                        c = this._synced_to_corr(that, a, d_ref + b)
                        points.append((c, a, b))
            corr, start, rend = max(*points)
            radius *= min(max(2.5 / nparts, 0.25), 0.75)
            nparts = max(5, 1 + nparts // 2)
        if corr < 0.3:
            print(
                f'  r={radius:.3f} [{start:.3f}s, {rend:.3f}s] corr={corr:.4f}')
            this._synced_to_plots(that, a, d_ref + b)
        #assert corr >= 0.3, (f'Insufficient correlation', corr, start, rend)
        return start, d_ref + rend, corr
