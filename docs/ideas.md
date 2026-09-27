# Ideas

42 spare buttons, reaching anything ProtoFlux can do on your avatar and beyond. Here are some starting points,
grouped by what they're for. Each comes with a hint of how it's built. The patterns (toggle, hold, cycle,
combo, forwarding to a world object) are in [developing.md](developing.md#patterns).

## Building and creating

- **Quick tools.** Equip the Dev Tool, ProtoFlux Tool or Material Tool on one button each, like the
  [Dev Tool example](examples.md#fluxaction1-the-dev-tool). Holding a button can bring up a tool and letting go
  can put it away.
- **Guides while held.** Show a grid, a ruler or alignment guides only while the button is down
  (`toggle_slot.py --hold` on their slot).
- **Spawn your favourites.** Keep inactive templates under your avatar, and duplicate one in front of you
  (Duplicate Slot, then place and activate the copy).
- **Measure.** Press once to mark a point, press again to show the distance.

## Moving around

- **Fly / walk**, like the [example](examples.md#fluxaction2-fly-and-walk). Noclip or Teleport work the same way,
  by module name.
- **Sprint while held.** Switch to a faster locomotion module while the button is down, and back on release.
- **Home point.** One button remembers where you stand, another takes you back.

## Avatar and expression

- **Outfits and accessories.** Hats, glasses and props, with
  [`toggle_slot.py`](../tools/toggle_slot.py) and no ProtoFlux writing at all. Or cycle through outfits on one
  button.
- **Facial expressions.** Hold for a smile, a blink or a pout, by driving blend shapes from the button's bool.
  With a CyberFinger, the glove's own finger tracking stays free for your hands.
- **Emotes.** Play an animation or a particle burst: confetti, hearts, a thought bubble.
- **On-air light.** Set the bridge's right pink button to a FluxAction, and let it toggle a light on your avatar.
- **Size.** Toggle between two scales (Set User Scale) for crowded rooms and big builds.

## Social and performance

- **Sound board.** Applause, a rimshot, a party horn, your walk-on music (Play One Shot): one button each, or
  cycle through them.
- **Raise hand.** Put an indicator above your head for meetings and classes.
- **Stage lights and effects.** Forward to the venue's lights and fog, when the world's owner gives you the tags.
- **DJ and VJ.** Trigger loops, drops and visuals. Hold for filters, sweep with the stick.

## Presenting and teaching

- **Slide clicker.** Forward FluxAction3/4 to a presentation board as next and previous.
- **Laser pointer while held.** Show a pointer beam only while the button is down.
- **Highlight.** Pulse the object you're pointing at, or show and hide labels on a model (a brain atlas, an
  engine, a molecule).
- **Timer.** Start, pause and reset a talk timer only you can see.

## Streaming and cameras

- **Camera angles.** Cycle a stream camera through presets.
- **Scene cues.** Pair Resonite with OBS: send FluxActions from OBS scene changes over UDP, so your avatar
  reacts as the stream changes.
- **Privacy.** One button hides things from the camera, or blanks a mirror.

## Accessibility

- **One-handed control.** Put the gestures and menus you'd otherwise need two hands for on one glove.
- **Big, simple toggles.** Combine the hold pattern with a large on-screen label, for players who find small UI
  hard.
- **Reduce motion.** Switch to teleport, fade the vignette in, or dim bright effects.
- **Call for help.** Alert your friends, or show a visible marker, with one press.

## Science and experiments

- **Event markers.** Stamp trials, stimuli or observations with a timestamp, like the
  [console](examples.md#the-console). Its log is a working example of a timestamped record.
- **Stimulus control.** Start a trial, present a stimulus, and advance a protocol from a glove the participant
  already wears.
- **Annotate a dataset.** Walk through a 3D reconstruction or volume, and mark points of interest with a press.
- **External rigs.** A lab program (a stimulus PC, an EEG recorder, a tracker) can fire FluxActions over UDP, so
  the virtual scene reacts to real events.

## Games

- **Minigame controls.** Jump, use and ability buttons for games you build.
- **Score and ready.** Forward to a scoreboard, or signal "ready" to a game host.
- **Party games.** Buzzers for a quiz show, one FluxAction per player.

## Other programs driving your avatar (UDP)

Anything on your PC can press a FluxAction ([how](developing.md#firing-from-other-programs)):

- **Stream Deck, MIDI pads, foot pedals:** a small script turns each key into a FluxAction.
- **Voice commands:** speech recognition says "lights" and a script sends FluxAction9.
- **Home and desktop events:** a doorbell, a timer, a calendar reminder, a message arriving. Your avatar or your
  room shows it.
- **Game or app state:** a program watching another game or app reflects its events in Resonite.
- **The CyberFinger bridge:** the right pink button, set to a FluxAction.

## AI-assisted flux

The `fluxlink` builder already does what an AI assistant needs to write ProtoFlux safely. It creates nodes by
name, reports every member that exists, reads every write back, and can press the buttons itself over UDP to
check the result. Describe what a button should do; an assistant builds it on your avatar, tests it, and tells
you what it changed. That's the next tool planned for this repository.
