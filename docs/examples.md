# Examples: the test rigs

[`tools/deploy.py`](../tools/deploy.py) builds three examples straight into your running session over
[ResoniteLink](https://github.com/Yellow-Dog-Man/ResoniteLink), with nothing to import or install. Each run
removes what the previous run built and builds it again. Together they show the whole path working: a button
press in SteamVR (or a UDP datagram) reaches ProtoFlux on your avatar and does something.

## Running them

1. Install the mod, start Resonite, and enable ResoniteLink in the session (Session tab).
2. From the repository, with Python 3.12+ and [pyresonitelink](https://github.com/XekriRedmane/pyresonitelink)'s
   `src` folder on the path:

   ```powershell
   $env:PYTHONPATH = "$HOME\src\pyresonitelink\src;$env:PYTHONPATH"
   python tools\deploy.py all          # or: console, devtool, fly, examples, remove
   ```

The script finds the session from ResoniteLink's own announcements (UDP 12512, every 10 s). Pass `--port` to pick
one when several are running, and `--user` when the session has several users.

```
Looking for a ResoniteLink session (announced every 10 s)...
Found DrSciCortex World on port 17838
console: panel ahead of you, 42 receivers under User DrSciCortex
devtool: FluxAction1 equips or puts away the Dev Tool (right hand)
fly: FluxAction2 switches between Fly and Walk/Run
examples under drsci cyberfinger v1.0 (MoreFluxActions Examples)
266 components in 28.6 s, every write read back
```

## The console

A panel appears 0.8 m in front of your head. It lists every FluxAction press and release it receives, newest
first, with the time in UTC:

```
16:46:46.590  FluxAction42 released
16:46:46.334  FluxAction42 pressed
16:46:33.925  FluxAction1 released
16:46:33.774  FluxAction1 pressed
```

It is the first thing to build when a binding "does nothing". A line appears: the button, the binding and the
mod all work, and the problem is in your ProtoFlux. No line: look at the binding, or the logs in the
[README](../README.md#checking-it-works).

**How it's built.** The panel is a UIX canvas in the world. You can grab it and move it; it stays where you put
it. Its receivers sit under your user root, in `MoreFluxActions Console Receivers`, because that's where the mod
fires the impulses. The flux is:

```
for each N in 1..42:                                   (--actions 1-8,42 picks fewer)
    FluxActionN (bool)  ─►  name := "FluxActionN"  ─►  pressed := value  ─►  append
append:  log := (time + "  " + name + (pressed ? " pressed" : " released") + "\n" + log)[:4000]
```

- **Receivers:** one Dynamic Impulse Receiver With Value `<bool>` per action.
- **Stores:** two data-model stores hand the action's name and state to one shared chain.
- **The log itself:** the log text is the panel's `Text.Content`, read and written through an `ObjectValueSource`
  (a `GlobalReference` to the field). A single node is both the value you read and the variable you write.

## FluxAction1: the Dev Tool

Press FluxAction1 (on a CyberFinger: hold the left black button) to equip a Dev Tool in your right hand, and
again to put it away.

It keeps a Dev Tool of its own, parked and inactive under `MoreFluxActions Examples/FluxAction1 Dev Tool` on
your avatar. A `DevTool` component builds its own visual when it's attached, so no asset is needed.

```
FluxAction1.Pressed ─► If (Is Tool Equipped: our Dev Tool)
    true  ─► Dequip Tool (right) ─► Set Parent (back home) ─► Set Slot Active (off)
    false ─► Set Slot Active (on) ─► Equip Tool (our Dev Tool, right, dequip existing)
```

If you put the tool away from its own menu instead, it's left lying in the world. The next press picks it up
from there.

## FluxAction2: fly and walk

Press FluxAction2 (on a CyberFinger: hold the right black button) to fly, and again to walk.

```
FluxAction2.Pressed ─► If (archetype of the active locomotion module == Fly)
    true  ─► Switch Locomotion Module "WalkRun"
    false ─► Switch Locomotion Module "Fly"
```

It asks which locomotion is active on every press, so it stays right if you change locomotion from the menu.
Modules are matched by a part of their name: Resonite's names are locale keys such as `Locomotion.Fly.Name` and
`Locomotion.WalkRunGripping.Name`. A world that disallows flying simply doesn't switch.

## Keeping them

The Dev Tool and fly examples are built under your avatar, in `MoreFluxActions Examples`: save the avatar to
keep them in every world. The console is a debugging aid, built fresh when you need it. `python tools\deploy.py
remove` removes all three.

## Checking without a controller

The mod also listens on UDP `127.0.0.1:42042`. Send it the impulse names to "press" a button from a script, and
read the result back over ResoniteLink. That's how the examples were tested:

```python
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(b"FluxAction2.Pressed", ("127.0.0.1", 42042))
s.sendto(b"FluxAction2.Released", ("127.0.0.1", 42042))
```

| Sent | Read back over ResoniteLink |
|---|---|
| FluxAction2 | locomotion module #0 (Walk/Run) → #1 (Fly) |
| FluxAction2 | #1 → #0 |
| FluxAction1 | the Dev Tool moves under `Tooltip Holder` (your hand), active |
| FluxAction1 | back under `FluxAction1 Dev Tool`, inactive |
| every press and release | a console line |
