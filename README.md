<img src="images/icon_512.png" alt="MoreFluxActions icon" width="128" align="right">

# MoreFluxActions

A [Resonite](https://resonite.com/) mod that adds **FluxAction1 to FluxAction42** to Resonite's SteamVR bindings.
Bind them to any button of any controller in SteamVR, and each press and release fires a ProtoFlux dynamic impulse
on your avatar, so your own ProtoFlux can react to buttons Resonite doesn't use.

Made as the companion of [CyberFinger](https://github.com/SciCortex/CyberFinger_SteamVR), whose SteamVR
defaults for Resonite bind the black wrist button's long press to FluxAction1 (left hand) and FluxAction2 (right
hand), C/D/E to FluxAction3–8, the two-finger point gesture to FluxAction36/37 and the pinky pinch and index point
gestures to FluxAction38–41. It works with any SteamVR controller.

## Documentation

| | |
|---|---|
| [Architecture](docs/architecture.md) | How a button press in SteamVR (or a UDP datagram) becomes a dynamic impulse on your avatar, across Resonite's engine and renderer processes |
| [Examples](docs/examples.md) | The test rigs: a console that logs every FluxAction, the Dev Tool on FluxAction1, fly/walk on FluxAction2, built live over ResoniteLink |
| [Developing your own actions](docs/developing.md) | The contract, building by hand or with a script, patterns (toggle, hold, cycle, combos, forwarding), testing, gotchas |
| [Ideas](docs/ideas.md) | What people can do with 42 spare buttons: building, movement, expression, performance, teaching, accessibility, science, games, and other programs driving your avatar |

## Using it in ProtoFlux

For every action the mod fires three dynamic impulses into your user's hierarchy (your user root, which holds your
avatar), in the focused world:

| Tag | Node | When |
|---|---|---|
| `FluxAction7.Pressed` | Dynamic Impulse Receiver | the button goes down |
| `FluxAction7.Released` | Dynamic Impulse Receiver | the button goes up |
| `FluxAction7` | Dynamic Impulse Receiver With Value (bool) | both: `true` on press, `false` on release |

Put the receivers anywhere under your avatar. Like any dynamic impulse, they run on your client only; whatever the
flux writes syncs to everyone as usual.

## Binding the actions

Open SteamVR's controller bindings while Resonite runs. A new action set, **Flux Actions**, lists Flux Action 1–42:
bind them to whatever buttons you like. They're read whatever controller you use, alongside Resonite's own actions.

In the binding editor, action sets are the tabs along the top, and an input's action list shows only the selected
tab's actions. Resonite has one set per controller family (Generic, Vive, Oculus Touch, …), so switch to the **Flux
Actions** tab before picking a Flux Action for a button.

## From other programs

Programs on the same PC can fire the actions without SteamVR: send one UDP datagram to `127.0.0.1:42042` per change,
whose text is the impulse's tag, `FluxAction42.Pressed` or `FluxAction42.Released` (ASCII). The CyberFinger bridge
does this for the right CyberFinger's pink button when it's set to a FluxAction. From Python:

```python
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(b"FluxAction42.Pressed", ("127.0.0.1", 42042))
s.sendto(b"FluxAction42.Released", ("127.0.0.1", 42042))
```

The mod listens on the loopback address only, so nothing on your network can reach it; any program on your PC can.

## A FluxAction as your mute

Resonite has no mute action a controller can be bound to, and ProtoFlux can't mute you (it can read a voice mode,
not set one; the dash's mute lives in Userspace, out of a world's reach). So the mod can do it:
**`MuteToggleAction`** (in the mod's config, `[Mute]`; 42 by default) names a FluxAction whose press also toggles
your microphone mute, exactly like the dash's mute button. Its impulses still fire, so your own flux can show the
state. 42 is the CyberFinger's right pink button (with the CyberFinger bridge's right pink on *SteamVR*, its
default), so the CyberFinger's mute button works out of the box; the log shows `FluxAction42: muted` / `unmuted` on each
press. If you bind FluxAction42 to something else, set `MuteToggleAction` to 0 (off) or another action.

## Test rigs

[`tools/deploy.py`](tools/README.md) builds a FluxAction console, a Dev Tool on FluxAction1 and a fly toggle on
FluxAction2 live in your session over ResoniteLink, nothing to install: `python tools/deploy.py all`.
[`tools/toggle_slot.py`](tools/toggle_slot.py) binds a FluxAction to showing and hiding any part of your avatar. See
[examples](docs/examples.md) and [developing](docs/developing.md).

## Installation

Install with a Thunderstore mod manager (Gale, r2modman), which brings the dependencies:
[BepisLoader](https://thunderstore.io/c/resonite/p/ResoniteModding/BepisLoader/),
[BepisResoniteWrapper](https://thunderstore.io/c/resonite/p/ResoniteModding/BepisResoniteWrapper/),
BepInExResoniteShim, [InterprocessLib](https://thunderstore.io/c/resonite/p/Nytra/InterprocessLib/),
[BepInExRenderer](https://thunderstore.io/c/resonite/p/ResoniteModding/BepInExRenderer/) and
[RenderiteHook](https://thunderstore.io/c/resonite/p/ResoniteModding/RenderiteHook/).

The mod has two halves: `plugins/MoreFluxActions/MoreFluxActions.dll` loads in the engine (BepInEx 6), and
`Renderer/BepInEx/plugins/MoreFluxActions.Renderer/MoreFluxActions.Renderer.dll` in the renderer (BepInEx 5).

### Checking it works

- Renderer log (`<profile>/Renderer/BepInEx/LogOutput.log`): `SteamVR gets FluxAction1..42`, then
  `Connected to the engine half` and `Reading FluxAction1..42 from SteamVR`.
- Engine log (BepInEx): `Listening for FluxAction1..42` and `Listening for FluxActions from other programs on
  127.0.0.1:42042`, and on the first press of each action `FluxAction1 pressed: 1 receiver(s) under …`.

## How it works

Since Resonite split its renderer into its own process, SteamVR input is read there, by Valve's Unity plugin, and
reaches the engine only as fixed per-controller states. The renderer half therefore:

1. hands SteamVR an extended copy of Resonite's action manifest (the `FluxActions` set added; written to the
   renderer's BepInEx config folder, with Resonite's default bindings beside it), by redirecting the native
   `SetActionManifestPath` call only;
2. adds the `FluxActions` set to every `UpdateActionState`, so SteamVR delivers it whatever controller Resonite
   recognised, and reads the 42 actions after each update;
3. sends each change to the engine half over InterprocessLib (one `int` per change).

The engine half fires the dynamic impulses (`ProtoFluxHelper.DynamicImpulseHandler`) under the focused world's local
user, for these events and for the datagrams of other programs. The details, with the reasons for each choice, are
in [docs/architecture.md](docs/architecture.md).

## Building

Needs the .NET 10 SDK and a Resonite install (the game's DLLs are referenced from it; InterprocessLib and BepInEx 5
are fetched from Thunderstore on the first build).

```
dotnet build MoreFluxActions.slnx -c Release                   # both halves
dotnet build MoreFluxActions.slnx -c Release -p:Deploy=true    # and copy them into your mod profile
dotnet build -c Release -target:PackTS -v d                    # Thunderstore package in ./build
```

`Deploy` copies into Gale's `Default` Resonite profile if there is one, else into the game folder; set
`-p:ModProfilePath=<folder>\` for another profile. Close Resonite first (the DLLs are locked while it runs).

## Licences

- **Code:** [MIT](LICENSE), except two files adapted from [DesktopBuddy](https://github.com/DevL0rd/DesktopBuddy) by
  DevL0rd, which keep its [AGPL-3.0-only](LICENSES/AGPL-3.0-only.txt) licence:
  [`Shared/QueueScope.cs`](Shared/QueueScope.cs) (the queue scoping by `-shmprefix`, and the unpooled message pool)
  and [`ThunderstoreRefs.targets`](ThunderstoreRefs.targets) (fetching the Thunderstore packages the build references).
  `QueueScope.cs` is compiled into both halves, so the mod as built and distributed is covered by the AGPL-3.0 as a
  whole (its source is this repository); every other file can be reused on its own under MIT.
- **Icon:** `icon.png`, `images/icon_source.png` and `images/icon_512.png` are adapted from the
  [Resonite logo](https://wiki.resonite.com/Resonite_Logo) (the Resonite Wiki; Resonite is Copyright © Yellow Dog
  Man Studios s.r.o.), available under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/): recoloured
  and redrawn as a burst of petals, with a transparent background (`tools/make_icon.py`). Under its ShareAlike terms
  the MoreFluxActions icon is licensed under [CC BY-SA 4.0](LICENSES/CC-BY-SA-4.0.txt) too.

Each file says which applies (an SPDX header, or a `.license` file beside an image); the full texts are in
[`LICENSES/`](LICENSES).
