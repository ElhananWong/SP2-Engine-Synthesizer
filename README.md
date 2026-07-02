# SimplePlanes2 Car Engine Synthesizer

Converts MIDI files into SP2 funky tree expressions to control car engines as sound sources.

## Requirements
- Python 3.8+
- pretty_midi library (`pip install pretty_midi`)

## Usage
1. Clone the repository or download the generator script.
2. Place MIDI files in the same directory as the generator script.
3. Run the generator script.
	- `python generator.py [-o output_file.txt] [--loop] [--normalize] <midi_file.mid>`
4. Copy the generated expression into the input controller of the engine(s).
	- FT expression gives target RPM based on time since craft loaded. It is recommended to use a PID controller for engine control, with the expression as the target RPM input.
	- Multiple tracks can be played by using multiple engines each with their own FT expression.
## Options
- `-o, --output`: Specify the output file name. If not provided, only prints to console.
- `--loop`: Enable looping of the generated expression.
- `--normalize`: attempt to normalize octave ranges to fit inside engine RPM range.

## Sample craft
Default values in the generator script are set to match the demo craft's engine RPM range and tuning, but can be retuned for different setups.

MIDI used: https://onlinesequencer.net/5433043
