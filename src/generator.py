import math
import warnings
import pretty_midi as pm
import argparse, os, sys
import normalizer

RPM_MIN = 2150
RPM_MAX = 15000
RPM_OFFSET = 512

# Empirical calibration data
_CALIBRATION = [
    (50, 2150),    # D3
    (51, 2300),    # D#3
    (52, 2500),    # E3
    (53, 2750),    # F3
    (54, 2960),    # F#3
    (55, 3200),    # G3
    (56, 3450),    # G#3
    (57, 3750),    # A3
    (58, 4000),    # A#3
    (59, 4300),    # B3
    (60, 4700),    # C4
    (61, 5000),    # C#4
    (62, 5450),    # D4
    (63, 5850),    # D#4
    (64, 6250),    # E4
    (65, 6600),    # F4
    (66, 7150),    # F#4
    (67, 7600),    # G4
    (68, 8000),    # G#4
    (69, 8720),    # A4
    (70, 9300),    # A#4
    (71, 10010),   # B5
    (72, 10700),   # C5
    (73, 11500),   # C#5
    (74, 12200),   # D5
    (75, 13100),   # D#5
    (76, 14000),   # E5
]

_CAL_NOTES    = [p[0] for p in _CALIBRATION]
_CAL_RPMS = [p[1] for p in _CALIBRATION]

# Engine slip zone
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

    if note <= _CAL_NOTES[0]:
        return _CAL_RPMS[0]
    if note >= _CAL_NOTES[-1]:
        return _CAL_RPMS[-1]

    idn = _CAL_NOTES.index(note)
    rpm = _CAL_RPMS[idn]

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
        rpm = note_to_rpm(note["pitch"]) + RPM_OFFSET
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
    parser.add_argument("-l", "--loop", help="Enable looping by using Time%%<length>.", action="store_true")
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
