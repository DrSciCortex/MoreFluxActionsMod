# Test rigs, built live over ResoniteLink

`deploy.py` builds ProtoFlux in your running Resonite session over [ResoniteLink](https://github.com/Yellow-Dog-Man/ResoniteLink)
with [pyresonitelink](https://github.com/XekriRedmane/pyresonitelink). Nothing is saved or installed: each run removes
what the previous run built and builds it again.

| Command | What it builds |
|---|---|
| `console` | A panel that logs every FluxAction press and release, with the time (UTC). The panel stands in the world, so you can grab it to move it. Its receivers go under your user root, where the mod fires the impulses. `--actions 1-8,42` limits which actions it listens to (default 1-42). Below the log is a simulator. Pick an action with a preset (1, 2, 36–41, the ones the CyberFinger defaults bind) or with − and +, then hold **Fire**. It fires what the mod fires for a real button, in the same place: `FluxActionN.Pressed` and `FluxActionN` (true) on press, `.Released` and (false) on release. That lets you test a rig without the glove in the loop. |
| `devtool` | FluxAction1 (on the CyberFinger, the left black button held): equips a Dev Tool in your right hand, or puts it away. |
| `fly` | FluxAction2 (the right black button held): switches between Fly and Walk/Run. |
| `examples` | `devtool` and `fly`, under your avatar (`MoreFluxActions Examples`), so saving the avatar keeps them. |
| `all` | `console` and `examples`. |
| `remove` | Removes everything above. |

Also here:

| Script | What it builds |
|---|---|
| `toggle_slot.py "Hat" --action 3 [--hold]` | A FluxAction showing and hiding a part of your avatar |
| `laser_pointer.py [--pointer LaserPointer]` | **Group 1**: while you hold the two-finger point (FluxAction36 left, 37 right) a laser pointer in the world rides on that index finger, aimed along it, beam on; let go and it goes home, beam off. **FluxAction1** switches group 1 on and off (the mod skips receivers in inactive slots), with a 2.5 s popup at the front left of your view that only you see (a `ValueUserOverride` your client writes). Replaces the Dev Tool example on FluxAction1. |
| `avatar_laser.py [--remove]` | **A laser pointer built into your avatar**, so no world object is needed. While you hold the two-finger point (FluxAction36 left, 37 right), a green beam leaves that index finger and ends in a dot on whatever it hits, up to 20 m. A **"Laser: on/off"** item in your dial switches the gesture. Save the avatar to keep it in every world. The gesture flux runs on your client and only moves the beam onto the finger and switches it. Each client computes the beam's length and dot itself, from a raycast through drives. Replaces `laser_pointer.py`'s world rig. |
| `make_icon.py` | The mod's icons, from `images/icon_source.png` |

## Running it

1. In Resonite, enable ResoniteLink for the session (Session tab).
2. From this folder, with Python 3.12+ and pyresonitelink's `src` on the path:

   ```powershell
   $env:PYTHONPATH = "$HOME\src\pyresonitelink\src;$env:PYTHONPATH"
   python deploy.py all
   ```

   The script finds the session from ResoniteLink's own announcements, sent to UDP 12512 every 10 s, so finding it
   can take up to 10 s. With more than one session running, pass `--port <port>` to pick one. If the session has
   several users, pass `--user <part of your name>`.

## How it stays honest

`fluxlink.py` creates each component empty, then sets and wires it by member name. It takes the member names and
reference types from the live component, then reads every write back. A reference that didn't land (Resonite
drops an incompatible one without an error) stops the run with the member, what it expects, and what it holds.
The run then fails loudly instead of leaving a graph that silently does nothing.
