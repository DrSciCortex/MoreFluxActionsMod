# Developing your own actions

A FluxAction is a button with no meaning until you give it one. You write that meaning in ProtoFlux, by hand in
Resonite or with a script, and it travels with your avatar. This page covers the contract, both ways of building,
patterns that come up again and again, and how to test.

## The contract

For every press and release of FluxAction *N* (1 to 42), the mod fires three dynamic impulses at your user root,
in the world you're focused on:

| Tag | Receiver | Fires |
|---|---|---|
| `FluxActionN.Pressed` | Dynamic Impulse Receiver | when the button goes down |
| `FluxActionN.Released` | Dynamic Impulse Receiver | when it goes up |
| `FluxActionN` | Dynamic Impulse Receiver With Value `<bool>` | both: `true` down, `false` up |

Put receivers **anywhere under your avatar** and keep their slots **active**. That's all.
[architecture.md](architecture.md) explains why, and
[What survives a reload](#what-survives-a-reload-and-how-to-reconnect) covers receivers that live anywhere else.

## 1. Pick an action and bind it

- **Any SteamVR controller:** open SteamVR's controller bindings while Resonite runs. In the binding editor, action
  sets are the tabs along the top. Switch to **Flux Actions**, then click a button and pick Flux Action 1–42 (an
  input's list only shows the selected tab's actions). It's read alongside Resonite's own actions, whatever
  controller you use.
- **CyberFinger:** each CyberFinger has an extra input, **A held**, which turns on after the black wrist button has
  been held for 0.8 s (the driver's `black_hold_ms`). The default Resonite binding uses these, left then right:

  | Input | Flux Actions |
  |---|---|
  | A held (black button, held) | 1, 2 |
  | C / D / E (on CyberFingers that have them) | 3, 4 / 5, 6 / 7, 8 |
  | Two-finger point (hand tracking: index and middle out, the thumb over the others) | 36, 37 |
  | Thumb-pinky pinch (hand tracking) | 38, 39 |
  | Index point (hand tracking) | 40, 41 |

  These are ordinary bindings: change them in the Flux Actions tab. The bridge can also make the right pink button
  any FluxAction (its *Right pink button* option; 42 by default, which the binding leaves free). You point
  often, so give 40/41 something harmless, or something you want to follow your pointing.
- **Another program:** send `FluxActionN.Pressed` / `.Released` to UDP `127.0.0.1:42042`
  ([below](#firing-from-other-programs)).

It's worth keeping a note of which number does what. 42 is plenty, but they all look alike in the bindings UI.

## 2a. Build it by hand in Resonite

1. Equip the ProtoFlux Tool and create a **Dynamic Impulse Receiver**. Type the tag into its Tag field, for
   example `FluxAction3.Pressed`.
2. Connect its output to what should happen, exactly as you would from any other impulse.
3. Put the nodes in a slot under your avatar (parent them there with the inspector), and **save the avatar**.
4. Press the button. Nothing happens? Build the [console](examples.md#the-console) to see whether the press
   arrives.

## 2b. Build it with a script

The `tools/` folder builds ProtoFlux over ResoniteLink, from Python. That's handy for anything you'll rebuild,
share, or generate: many actions, per-avatar variants, a whole control scheme.

[`tools/toggle_slot.py`](../tools/toggle_slot.py) is the smallest complete example. It binds a FluxAction to
showing and hiding any part of your avatar:

```powershell
python tools\toggle_slot.py "Sunglasses" --action 3            # each press shows or hides them
python tools\toggle_slot.py "Sunglasses" --action 3 --hold     # shown only while held
```

Its builder is the whole idea in a dozen lines:

```python
async def build_toggle(f: Flux, parent, action, target_id, target_name, hold):
    flux = await f.slot(parent, f"FluxAction{action} Toggle {target_name}")
    target = await f.ref(flux, SLOT, target_id)                      # RefObjectInput<Slot>
    show = await f.add(flux, PF + "FrooxEngine.Slots.SetSlotActiveSelf")
    await f.wire(show, Instance=target)
    if hold:
        rx = await f.receiver(flux, f"FluxAction{action}", on_triggered=show, value_type="bool")
        await f.wire(show, Active=rx.out("Value"))                   # the button's state
    else:
        active = await f.add(flux, PF + "FrooxEngine.Slots.GetSlotActiveSelf")
        await f.wire(active, Instance=target)
        flipped = await f.add(flux, PF + "Operators.NOT_Bool")
        await f.wire(flipped, A=active)
        await f.wire(show, Active=flipped)                           # not active
        await f.receiver(flux, f"FluxAction{action}.Pressed", on_triggered=show)
```

Tested live: the toggle flipped a slot off and on again, and the hold showed it only while pressed.

### The `fluxlink` builder

[`tools/fluxlink.py`](../tools/fluxlink.py) wraps pyresonitelink so a graph reads like the list of nodes it is.

| Call | Does |
|---|---|
| `await fluxlink.discover()` | `(port, session name)` of the ResoniteLink session announced on this PC |
| `await fluxlink.find_user(rl)` / `find_avatar(rl, user_id)` | your user root slot / your avatar slot |
| `f.slot(parent, name, position=, rotation=, active=)` | a new slot |
| `f.child(parent, name)` / `f.remove_named(parent, name)` | find or create a child / remove children by name (rebuild cleanly) |
| `f.add(slot, type, **fields)` | a component, fields set and checked |
| `f.wire(node, **refs)` | point inputs, impulse outputs or refs at nodes, outputs, fields or slots, each checked |
| `f.set(node, **fields)` | set fields, checked |
| `f.receiver(slot, tag, on_triggered=, value_type=)` | a Dynamic Impulse Receiver with its Tag |
| `f.const(slot, type, value)` | `ValueInput<T>`, or `ValueObjectInput<string>` for `"string"` |
| `f.ref(slot, type, target)` | `RefObjectInput<T>` holding target |
| `node.out("Value")` | one output of a node with several (a receiver's `Value`, `UnpackNullable`'s `Value`) |

Three rules it follows, and why:

- **Create, then wire.** Nodes are added empty and connected afterwards. Wiring at creation is unreliable.
- **Read every write back.** Resonite drops a reference to the wrong kind of node *without an error*. `wire`
  checks each one and stops with the member name, what it expects, and what it holds. The alternative is a graph
  that looks right and never fires.
- **Names from the live component.** `node.member("Foo")` lists the members that exist when `Foo` doesn't. To
  find a node's inputs, create it and read the error.

**Type names.** Nodes are `PF + "<namespace>.<Node>"` (`PF` = `[ProtoFluxBindings]FrooxEngine.ProtoFlux.Runtimes.Execution.Nodes.`).
Generic arguments are bare for primitives (`<bool>`, `<string>`) and assembly-qualified otherwise
(`<[FrooxEngine]FrooxEngine.Slot>`). pyresonitelink's `generated/protoflux` folder has every node's exact
`COMPONENT_TYPE`.

- **Strings are objects in ProtoFlux:** `ValueObjectInput<string>`, `ObjectWrite`, `ObjectConditional`, never the
  `Value*` variants.
- **A receiver's Tag is a `GlobalValue<string>`**, not an input node. `f.receiver` handles it.
- **Writes to a data-model store** (`DataModelValueFieldStore<T>` / `DataModelObjectFieldStore<T>`) use
  `ValueWrite<FrooxEngineContext,T>` / `ObjectWrite<FrooxEngineContext,T>`.

## Patterns

**Toggle on each press.** `FluxActionN.Pressed` → set X to `NOT X`. This is `toggle_slot.py` without `--hold`.

**Only while held.** A `FluxActionN` receiver with a `bool` → use its `Value` as the state (active, visible,
enabled). This is `toggle_slot.py --hold`. It's also the way to make a push-to-talk, a sprint, or a "show my
menu while I hold".

**Different actions for tap and hold.** On a CyberFinger the black button already does this: it gives a
tap to Resonite and a hold to FluxAction1/2. For other buttons, time it in flux: `Pressed` stores the time,
`Released` compares against it and branches.

**Cycle through states.** Keep an `int` in a store, and on each `Pressed` add one and wrap around (modulo N).
Then drive what shows from it: outfits, colours, camera angles.

**Two buttons together.** Store each button's state from its `FluxActionN` bool receiver. On either change,
`If (A AND B)`. Combos multiply the 42 actions, and they're hard to trigger by accident.

**Reaching things outside your avatar.** The impulses only travel down from your user root. To drive a world
object (a door, a slide show, a scoreboard), forward the impulse with a **Dynamic Impulse Trigger**: set
`TargetHierarchy` to the object's slot (found by tag with `FindChildByTag`, say) and give it its own tag. The
object's builder then listens for that tag.

**Waiting.** A receiver's chain is synchronous. For delays, sounds that play to the end and other async nodes,
go through **Start Async Task** first.

## What survives a reload, and how to reconnect

The mod fires into your **user root**, and Resonite builds a new user root every time you join a world or it
reloads. So where your receivers live decides whether they're still listening next time.

| Where the flux lives | Survives | What it needs |
|---|---|---|
| **Under your avatar**, and the avatar saved | Every world and session, while you wear that avatar | Nothing: the avatar comes back under your new user root. Examples: the Dev Tool and fly examples, the avatar laser. |
| **Under your user root**, built in the session (ResoniteLink rigs, things you dropped there) | Until you leave the world or it reloads | Nothing brings it back: build it again, or move it onto your avatar or into a world object with an installer |
| **In a world object** that listens itself (a console, a control panel), the world saved | With the world | **An installer**, because receivers in the world never hear the impulses. See below. Example: the console. |
| **In a world object driven from your avatar** (a door, a slide show) | With the world | No installer: receivers on your avatar forward the press with a Dynamic Impulse Trigger, finding the object when you press (by tag or name) |
| **In Userspace** (the dash) | — | Out of reach: the impulses only fire in the focused world. Resonite's own mute, which lives there, is why the mod has `MuteToggleAction`. |

**The installer.** Keep the receivers in the object as an **inactive template** named, say, `My Receivers`. Beside
it, on every client, for its own user:

```
missing := NotNull(LocalUserSlot) AND IsNull(FindChildByName(LocalUserSlot, "My Receivers"))
install := DuplicateSlot (the template) ─► SetParent (the copy, LocalUserSlot) ─► SetSlotActiveSelf (the copy, true)

FireOnLocalTrue (missing) ─OnChange─► install
OnStart ─► Start Async Task ─► Delay 3 s ─► If (missing) ─► install
```

`FireOnLocalTrue` fires on a *change* to true: when your user root appears after the object loads, or when the copy
goes missing. If the condition is already true when the node starts (your root was there first, or you just
built it), it never changes, so the `OnStart` branch installs anyway, a few seconds after the object starts on your
client. A script that builds the installer can also nudge it: create a stand-in slot with the template's name
under your user root, then remove it (`deploy.py` does, then checks that the real copy arrived). Everyone in the world with the mod gets
their own copy, installed by their own client, so the object hears all of them. The copies' chains can call back
into the object (a log, a store): a duplicate keeps its references to things outside itself. Name the template
uniquely, so the check finds the copy and doesn't install it twice.

**References that go stale.** A reference stored at build time only lasts as long as its target:

- **Your user root, or anything under it:** gone next session. Look it up when it's needed: `LocalUserSlot`,
  `LocalUser`. The console's simulator fires at the presser's `LocalUserSlot` for this reason.
- **A world object, from your avatar:** only exists in that world. Find it at press time (`FindChildByTag`, a
  dynamic variable) and do nothing when it isn't there.
- **Your bones:** find them at press time with `BodyNodeSlot` (the avatar laser does), and the flux keeps working
  on another avatar or after a rig change.
- **Anything inside the same avatar, or the same saved object:** safe. The reference is saved with it.

## Testing and debugging

- **The console:** `python tools\deploy.py console` logs every press and release it receives. A line appears but
  nothing happens: your flux is the problem. No line: the binding or the mod is.
- **Press without a controller:** send the impulse names over UDP ([below](#firing-from-other-programs)). You can
  test from your desk, or from a script that checks the result over ResoniteLink, as the
  [examples](examples.md#checking-without-a-controller) were.
- **The logs:** the engine log shows `FluxAction3 pressed: 1 receiver(s) under …` for each action's first press.
  0 receivers means the tag is wrong (tags are exact, including case) or the receiver isn't under your user root,
  or its slot is inactive.
- **Rebuild freely.** Scripts that remove their own slots by name before building can run as often as you like.
  Address things by name (slot names, tags, dynamic variables) rather than by element ID: IDs change on every
  rebuild and every session.

## Firing from other programs

Anything on your PC can press a FluxAction: one UDP datagram per change to `127.0.0.1:42042`, whose text is the
impulse's tag.

```python
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(b"FluxAction7.Pressed", ("127.0.0.1", 42042))
s.sendto(b"FluxAction7.Released", ("127.0.0.1", 42042))
```

```powershell
$udp = New-Object System.Net.Sockets.UdpClient
foreach ($m in "FluxAction7.Pressed", "FluxAction7.Released") {
    $b = [Text.Encoding]::ASCII.GetBytes($m); [void]$udp.Send($b, $b.Length, "127.0.0.1", 42042)
}
```

Always send the release too. Receivers of the `bool` form, and anything "while held", wait for it.

## Gotchas

| Symptom | Cause |
|---|---|
| The console shows the press, your receiver doesn't fire | Tag typo (exact, case-sensitive), receiver not under your user root, or its slot inactive |
| Works in one world, not another | The flux was built in the world but not saved on the avatar, or the world denies the action (locomotion, tools, permissions) |
| Worked until you rejoined or the world reloaded | The receivers were under your user root (rebuilt each session), or a reference points at the old one: see [What survives a reload](#what-survives-a-reload-and-how-to-reconnect) |
| A wire "didn't take" | Wrong kind of node on that input: `Value*` for a string, a `ValueObjectInput` for a Tag, a sync node after an async one |
| Other users don't see the effect | Impulses run on your client only. Change something synced (a field, a slot's active state), not a local-only value |
| Nothing from SteamVR, UDP works | Resonite isn't the focused VR app, or the button isn't bound in the Flux Actions set |
