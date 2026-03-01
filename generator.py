from math import ceil
import pretty_midi as pm
import argparse, os, sys
import normalizer

RPM_COEFFICIENT = 0.37
RPM_MIN = 3000
RPM_MAX = 15000
RPM_OFFSET = 512

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

def note_to_rpm(note, base_note=36, base_freq=65.41):
    """Map a MIDI note to a corresponding RPM value using a linear mapping.
    Args:
        note (int): The MIDI pitch of the note.
        base_note (int): The MIDI pitch that corresponds to the base RPM.
        base_rpm (int): The RPM value corresponding to the base note.
    Returns:
        int: The corresponding RPM value.
    """
    freq = base_freq * (2 ** ((note - base_note) / 12))
    rpm = freq * 60 * RPM_COEFFICIENT + RPM_OFFSET
    return max(RPM_MIN, min(RPM_MAX, int(rpm)))

def generate_funky_expression(notes, base_note=36, base_rpm=RPM_MIN):
    """Generate a Funky-Tree expression sequence from a list of MIDI notes.
    Args:
        notes (list): A list of dictionaries containing note information.
        base_note (int): The MIDI pitch that corresponds to the base RPM.
        base_rpm (int): The RPM value corresponding to the base note.
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