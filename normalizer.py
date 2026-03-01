import math


# Constants for RPM mapping
RPM_COEFFICIENT = 0.37
RPM_MIN = 3000
RPM_MAX = 15000
RPM_OFFSET = 512

def rpm_to_freq(rpm: float) -> float:
    return (rpm - RPM_OFFSET) / (60.0 * RPM_COEFFICIENT)

def freq_to_midi_note(freq: float, base_note=36, base_freq=65.41) -> float:
    return base_note + 12.0 * math.log2(freq / base_freq)

def get_playable_midi_range(base_note=36, base_freq=65.41):
    """
    Returns an inclusive (min_note, max_note) range that the engine can reach
    without hitting the clamps too much.
    """
    f_min = max(1e-9, rpm_to_freq(RPM_MIN))
    f_max = max(1e-9, rpm_to_freq(RPM_MAX))

    n_min = max(0, min(127, int(math.ceil(freq_to_midi_note(f_min, base_note, base_freq)))))
    n_max = max(0, min(127, int(math.floor(freq_to_midi_note(f_max, base_note, base_freq)))))
    return n_min, n_max

def _candidate_pitches_in_range(pitch: int, lo: int, hi: int):
    """
    All octave-shifted versions of `pitch` that land in [lo, hi].
    """
    candidates = []
    # k range big enough to cover MIDI range
    for k in range(-10, 11):
        p = pitch + 12 * k
        if lo <= p <= hi:
            candidates.append(p)
    return sorted(set(candidates))

def normalize_octaves_track_dp(notes, lo_note=None, hi_note=None,
                               contour_w=2.0, jump_w=0.15, shift_w=1.0,
                               base_note=36, base_freq=65.41):
    """
    Normalize a single track (list of note dicts) by octave-shifting pitches into a playable range.

    Cost terms:
      - shift_w * |new_pitch - orig_pitch|        (stay close)
      - contour_w * |(new-prev_new) - (orig-prev_orig)| (preserve contour)
      - jump_w * |new - prev_new|                (discourage huge jumps)

    Returns: 
        new list of note dicts (copies) with adjusted 'pitch'.
    """
    if not notes:
        return []

    if lo_note is None or hi_note is None:
        lo_note, hi_note = get_playable_midi_range(base_note, base_freq)

    orig_pitches = [n["pitch"] for n in notes]

    # compute possible normalized pitches for each note
    choices = []
    for p in orig_pitches:
        cand = _candidate_pitches_in_range(p, lo_note, hi_note)
        if not cand:
            cand = [max(lo_note, min(hi_note, p))]
        choices.append(cand)

    dp = []
    parent = []

    dp0 = []
    par0 = []
    for new_p in choices[0]:
        cost = shift_w * abs(new_p - orig_pitches[0])
        dp0.append(cost)
        par0.append(-1)
    dp.append(dp0)
    parent.append(par0)

    for i in range(1, len(notes)):
        dpi = [float("inf")] * len(choices[i])
        pari = [-1] * len(choices[i])

        orig_interval = orig_pitches[i] - orig_pitches[i - 1]

        for j, new_p in enumerate(choices[i]):
            base_cost = shift_w * abs(new_p - orig_pitches[i])

            best = float("inf")
            best_k = -1

            for k, prev_new in enumerate(choices[i - 1]):
                new_interval = new_p - prev_new

                contour_cost = contour_w * abs(new_interval - orig_interval)
                jump_cost = jump_w * abs(new_interval)

                total = dp[i - 1][k] + base_cost + contour_cost + jump_cost

                if total < best:
                    best = total
                    best_k = k

            dpi[j] = best
            pari[j] = best_k

        dp.append(dpi)
        parent.append(pari)

    # backtrack best ending
    last_j = min(range(len(dp[-1])), key=lambda j: dp[-1][j])
    new_pitches = [None] * len(notes)
    j = last_j
    for i in reversed(range(len(notes))):
        new_pitches[i] = choices[i][j]
        j = parent[i][j] if i > 0 else -1

    out = []
    for n, p in zip(notes, new_pitches):
        nn = dict(n)
        nn["pitch"] = int(p)
        out.append(nn)
    return out

def normalize_octaves_all_tracks(tracks, lo_note=None, hi_note=None, **kwargs):
    """
    Apply octave normalization to every track (tracks is list[list[dict]]).
    """
    if lo_note is None or hi_note is None:
        lo_note, hi_note = get_playable_midi_range(kwargs.get("base_note", 36),
                                                   kwargs.get("base_freq", 65.41))
    return [normalize_octaves_track_dp(t, lo_note, hi_note, **kwargs) for t in tracks]