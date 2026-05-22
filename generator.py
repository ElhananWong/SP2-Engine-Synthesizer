import math
import warnings
import pretty_midi as pm
import argparse, os, sys
import normalizer

RPM_MIN = 2400
RPM_MAX = 15000
RPM_OFFSET = 512

# Empirical calibration data
_CALIBRATION = [
    (53, 2800),    # F3
    (55, 3200),    # G3
    (57, 3810),    # A3
    (59, 4460),    # B3
    (60, 4600),    # C4
    (62, 5400),    # D4
    (64, 6290),    # E4
    (65, 6830),    # F4
    (67, 7700),    # G4
    (69, 9290),    # A4
    (71, 11200),   # B4
    (72, 12500),   # C5
    (73, 14000),   # C#5
]

_CAL_NOTES    = [p[0] for p in _CALIBRATION]
_CAL_LOG_RPMS = [math.log(p[1]) for p in _CALIBRATION]

# Engine slip zone: RPM controller becomes bistable in this range.
# The engine rises to ~3560 when ascending, ~3100 when descending.
# Notes mapping here will not hold pitch reliably.
SLIP_ZONE_LOW  = 3100
SLIP_ZONE_HIGH = 3560


def parse_midi_tracks(path):
    """Parses a MIDI file and extracts the note information for each track.
    Args:
        path (str): The file path to the MIDI file.
    Returns:
        A list of dictionaries, each containing the note information for a track.
                - pitch (int): The MIDI pitch of the note.
                - start (float): The start time of the note in seconds.
                - end (float): The end time of the note in seconds.
                - duration (float): The duration of the note in seconds.
    """

    midi = pm.PrettyMIDI(path)
    tracks = []

    for instrument in midi.instruments:
        notes = []
        for note in instrument.notes:
            notes.append({
                "pitch": note.pitch,
                "start": note.start,
                "end": note.end,
                "duration": note.end - note.start
            })
        tracks.append(notes)

    return tracks

def _log_interp(x, xs, log_ys):
    """Piecewise log-linear interpolation with flat extrapolation at boundaries.

    Interpolates in log(y) space to track the power-law curvature of the engine's
    RPM–frequency response (~freq^1.3).
    """
    if x <= xs[0]:
        return log_ys[0]
    if x >= xs[-1]:
        return log_ys[-1]
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            t = (x - xs[i]) / (xs[i + 1] - xs[i])
            return log_ys[i] + t * (log_ys[i + 1] - log_ys[i])


def note_to_rpm(note):
    """Map a MIDI note to a target RPM using empirical calibration data.

    Notes that fall in the engine's slip zone (~3100–3560 RPM) are
    flagged: the controller cannot hold a steady RPM there and pitch
    will drift to one of the zone's edges.

    Args:
        note (int): MIDI pitch number (e.g. 69 = A4).
    Returns:
        int: Target RPM clamped to [RPM_MIN, RPM_MAX].
    """
    log_rpm = _log_interp(float(note), _CAL_NOTES, _CAL_LOG_RPMS)
    rpm = int(math.exp(log_rpm))

    if SLIP_ZONE_LOW <= rpm <= SLIP_ZONE_HIGH:
        warnings.warn(
            f"MIDI note {note} maps to {rpm} RPM, which falls in the engine "
            f"slip zone ({SLIP_ZONE_LOW}–{SLIP_ZONE_HIGH} RPM). "
            "The engine will not hold this pitch stably.",
            UserWarning,
            stacklevel=2,
        )

    return max(RPM_MIN, min(RPM_MAX, rpm))

def generate_funky_expression(notes, base_rpm=RPM_MIN):
    """Generate a Funky-Tree expression sequence from a list of MIDI notes.
    Args:
        notes (list): A list of dictionaries containing note information.
        base_rpm (int): The idle RPM value.
    Returns:
        str: A Funky-Tree expression sequence representing the track.
    """
    terms = [str(base_rpm)]

    for note in notes:
        rpm = note_to_rpm(note["pitch"])
        start = round(note["start"], 3)
        end = round(note["end"], 3)
        rpm = round(rpm, 1)
        term = f"(Time>{start}&Time<{end}?{rpm-base_rpm}:0)"
        terms.append(term)

    return "+".join(terms)

def generate_funky_tree_expression_from_midi(path, loop=False, normalize=False, output=""):
    """Generate Funky-Tree expressions for each track in a MIDI file and optionally save them to a text file.
    Args:
        path (str): The file path to the MIDI file.
        loop (bool): Whether to use looping time in the expressions.
        output (str): Optional file path to save the generated expressions. If empty, expressions will print to stdout.
    """
    tracks = parse_midi_tracks(path)

    # normalize pitches into range of engine rpms
    if normalize:
        lo, hi = normalizer.get_playable_midi_range()
        tracks = normalizer.normalize_octaves_all_tracks(tracks, lo, hi)

    # find max end time across all tracks to determine the length of the loop
    length = max(note["end"] for track in tracks for note in track) + 3 # add some extra time at the end
    length = round(length, 3)

    expressions = []
    for i, notes in enumerate(tracks):
        expression = generate_funky_expression(notes)
        new_expression = str.replace(expression, "Time", f"Time%{length}" if loop else "Time")
        expressions.append(f"Track {i + 1} Expression:\n{new_expression}\n")
    if output:
        with open(output, "w") as f:
            f.write("\n".join(expressions))
    else:
        print("\n".join(expressions))



def _build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="generator.py",
        description="Convert a MIDI file into Funky-Tree expressions."
    )
    parser.add_argument("midi", help="Path to the input MIDI file.")
    parser.add_argument("-o", "--output", help="Path to write expressions (default: stdout).", default="")
    parser.add_argument("-l", "--loop", help="Enable looping by using Time%<length>.", action="store_true")
    parser.add_argument("-n", "--normalize", help="Normalize pitches into playable engine range.", action="store_true")
    return parser


def _validate_args(args):
    if not os.path.isfile(args.midi):
        raise FileNotFoundError(f"MIDI file not found: {args.midi}")


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    try:
        _validate_args(args)
    except Exception as ex:
        print(f"Argument error: {ex}", file=sys.stderr)
        return 2

    try:
        generate_funky_tree_expression_from_midi(args.midi, loop=args.loop, normalize=args.normalize, output=args.output)
    except Exception as ex:
        print(f"Error processing MIDI: {ex}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())