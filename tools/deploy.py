# SPDX-FileCopyrightText: 2026 DrSciCortex
#
# SPDX-License-Identifier: MIT

"""Build MoreFluxActions test rigs live in your Resonite session, over ResoniteLink. Nothing to install in the
game beyond the mod: every run removes what the previous one built and builds it again.

  console   A panel that logs every FluxAction press and release it receives, with the time (UTC).
            The panel stands in the world (grab it to move it); its receivers sit under your user root,
            where the mod fires the impulses.
  devtool   FluxAction1 (the left black button, held): equip a Dev Tool in your right hand, or put it away.
  fly       FluxAction2 (the right black button, held): switch between flying and walking.
  examples  devtool and fly (under your avatar, so saving the avatar keeps them).
  all       console and examples.
  remove    Remove everything these commands built.

Enable ResoniteLink in the session first (Session tab). The session is found from ResoniteLink's own
announcements (the one running here; --port picks one when there are several). Run with pyresonitelink on the path:
  set PYTHONPATH=%USERPROFILE%\\src\\pyresonitelink\\src
  python tools\\deploy.py all
"""

import argparse
import asyncio
import math
import sys
import time

from pyresonitelink.data import primitives

import fluxlink
from fluxlink import FE, FEC, PF, Flux, LinkError

COUNT = 42                                           # FluxAction1..42 (the mod's FluxActionProtocol.Count)
CONSOLE = "MoreFluxActions Console"                  # the panel, under the world root
CONSOLE_RX = "MoreFluxActions Console Receivers"     # its receivers, under the user root
EXAMPLES = "MoreFluxActions Examples"                # devtool and fly, under the avatar (else the user root)
DEVTOOL = "FluxAction1 Dev Tool"
FLY = "FluxAction2 Fly"
LOG_CHARS = 4000                                     # the log keeps the newest lines, this many characters

STR = "string"
SLOT = FE + "Slot"


def _rotate(q, v):
    """v rotated by the unit quaternion q = (x, y, z, w)."""
    x, y, z, w = q
    vx, vy, vz = v
    tx, ty, tz = 2 * (y * vz - z * vy), 2 * (z * vx - x * vz), 2 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty), vy + w * ty + (z * tx - x * tz), vz + w * tz + (x * ty - y * tx))


def _yaw_only(q):
    """The heading part of a rotation (x, y, z, w): the panel stands upright whatever the tilt."""
    fx, _, fz = _rotate(q, (0.0, 0.0, 1.0))
    yaw = math.atan2(fx, fz)
    return (0.0, math.sin(yaw / 2), 0.0, math.cos(yaw / 2))


async def _slot_transform(rl, slot_id):
    d = fluxlink._check(await rl.get_slot(slot_id, depth=1), "get slot")
    p = d.data.position.value if d.data.position else None
    r = d.data.rotation.value if d.data.rotation else None
    pos = (float(p.x), float(p.y), float(p.z)) if p is not None else (0.0, 0.0, 0.0)
    rot = (float(r.x), float(r.y), float(r.z), float(r.w)) if r is not None else (0.0, 0.0, 0.0, 1.0)
    return pos, rot, d.data.children


def _parse_actions(text):
    actions = set()
    for part in text.split(","):
        lo, _, hi = part.partition("-")
        actions.update(range(int(lo), int(hi or lo) + 1))
    bad = [a for a in actions if not 1 <= a <= COUNT]
    if bad:
        raise SystemExit(f"--actions: only 1..{COUNT} exist, not {bad}")
    return sorted(actions)


# ── the console ──

async def build_console(f: Flux, user, actions):
    rl = f.rl
    await f.remove_named("Root", CONSOLE)
    await f.remove_named(user.id, CONSOLE_RX)

    # The panel: 0.8 m ahead of your head, facing you, upright. Canvas units are millimetres (scale 0.001).
    upos, urot, uchildren = await _slot_transform(rl, user.id)
    head = next((c for c in uchildren if c.name and c.name.value == "Head"), None)
    hy = 1.5
    if head is not None and head.position and head.position.value is not None:
        hy = float(head.position.value.y)
    yaw = _yaw_only(urot)
    ahead = _rotate(yaw, (0.0, hy - 0.15, 0.8))
    panel = await f.slot("Root", CONSOLE, position=tuple(u + a for u, a in zip(upos, ahead)), rotation=yaw,
                         scale=(0.001, 0.001, 0.001))
    await f.add(panel, FE + "UIX.Canvas", Size=primitives.Float2(x=760.0, y=640.0))
    await f.add(panel, FE + "Grabbable")
    bg = await f.slot(panel, "Background")
    await f.add(bg, FE + "UIX.RectTransform")
    await f.add(bg, FE + "UIX.Image", Tint=primitives.ColorX(r=0.06, g=0.06, b=0.08, a=0.94, profile="sRGB"))

    title = await f.slot(panel, "Title")
    await f.add(title, FE + "UIX.RectTransform", AnchorMin=primitives.Float2(x=0.0, y=1.0),
                OffsetMin=primitives.Float2(x=16.0, y=-48.0), OffsetMax=primitives.Float2(x=-16.0, y=-8.0))
    await f.add(title, FE + "UIX.Text", Content=f"MoreFluxActions console · FluxAction{actions[0]}..{actions[-1]} · UTC",
                Size=24.0, HorizontalAutoSize=False, VerticalAutoSize=False, HorizontalAlign="Left",
                VerticalAlign="Middle", Color=primitives.ColorX(r=1.0, g=0.18, b=0.62, a=1.0, profile="sRGB"))

    body = await f.slot(panel, "Log")
    await f.add(body, FE + "UIX.RectTransform", OffsetMin=primitives.Float2(x=16.0, y=132.0),
                OffsetMax=primitives.Float2(x=-16.0, y=-56.0))
    text = await f.add(body, FE + "UIX.Text", Content="Waiting for a FluxAction: press a bound button.",
                       Size=20.0, HorizontalAutoSize=False, VerticalAutoSize=False, HorizontalAlign="Left",
                       VerticalAlign="Top", Color=primitives.ColorX(r=0.92, g=0.92, b=0.92, a=1.0, profile="sRGB"))

    # The receivers: under the user root, where the mod fires FluxActionN (a bool: pressed or released).
    rx_root = await f.slot(user.id, CONSOLE_RX)
    shared = await f.slot(rx_root, "Log")

    # The log text, read and written by the flux (a GlobalReference to Text.Content behind an ObjectValueSource).
    content = await f.add(shared, FE + f"ProtoFlux.GlobalReference<{FE}IValue<string>>")
    await f.wire(content, Reference=text.member("Content"))
    log = await f.add(shared, "[ProtoFluxBindings]FrooxEngine.FrooxEngine.ProtoFlux.CoreNodes.ObjectValueSource<string>")
    await f.wire(log, Source=content)

    # What the per-action chains hand over: the action's name and whether it was pressed.
    name = await f.add(await f.slot(shared, "name"), PF + "FrooxEngine.Variables.DataModelObjectFieldStore<string>")
    pressed = await f.add(await f.slot(shared, "pressed"), PF + "FrooxEngine.Variables.DataModelValueFieldStore<bool>")

    # line = time + "  " + name + (pressed ? " pressed" : " released");  log = (line + "\n" + log)[:LOG_CHARS]
    now = await f.add(shared, PF + "TimeAndDate.UtcNow")
    clock = await f.add(shared, PF + "ParsingFormatting.ToString_DateTime")
    await f.wire(clock, V=now, Format=await f.const(shared, STR, "HH:mm:ss.fff"))

    async def concat(a, b):
        node = await f.add(shared, PF + "Strings.ConcatenateString")
        return await f.wire(node, A=a, B=b)

    state = await f.add(shared, PF + "ObjectConditional<string>")
    await f.wire(state, OnTrue=await f.const(shared, STR, " pressed"), OnFalse=await f.const(shared, STR, " released"),
                 Condition=pressed)
    line = await concat(await concat(await concat(clock, await f.const(shared, STR, "  ")), name), state)
    joined = await concat(line, await concat(await f.const(shared, STR, "\n"), log))
    capped = await f.add(shared, PF + "Strings.Substring")
    await f.wire(capped, Str=joined, Length=await f.const(shared, "int", LOG_CHARS))
    append = await f.add(shared, PF + f"ObjectWrite<{FEC},string>")
    await f.wire(append, Variable=log, Value=capped)

    # Per action: receiver -> name = "FluxActionN" -> pressed = its bool -> append.
    for n in actions:
        s = await f.slot(rx_root, f"FluxAction{n}")
        rx = await f.receiver(s, f"FluxAction{n}", value_type="bool")
        set_name = await f.add(s, PF + f"ObjectWrite<{FEC},string>")
        await f.wire(set_name, Variable=name, Value=await f.const(s, STR, f"FluxAction{n}"))
        set_pressed = await f.add(s, PF + f"ValueWrite<{FEC},bool>")
        await f.wire(set_pressed, Variable=pressed, Value=rx.out("Value"))
        await f.wire(set_name, **{_next(set_name): set_pressed})
        await f.wire(set_pressed, **{_next(set_pressed): append})
        await f.wire(rx, OnTriggered=set_name)
        print(f"  console: FluxAction{n} ", end="\r", flush=True)
    await build_simulator(f, panel, user)
    print(f"console: panel ahead of you, {len(actions)} receivers under {user.name.value}, and a simulator")


SIMULATOR_PRESETS = (1, 2, 36, 37, 38, 39, 40, 41)   # the ones the CyberFinger defaults bind


async def build_simulator(f: Flux, panel, user):
    """The console's bottom rows: pick a FluxAction (presets, or - and +), and hold Fire. Fire fires what the mod
    fires for a real button, where it fires it (your user root, inactive slots skipped): FluxActionN.Pressed and
    FluxActionN(true) on press, FluxActionN.Released and FluxActionN(false) on release. So whatever a rig does
    downstream can be checked without the glove or its gestures in the loop."""
    white = primitives.ColorX(r=0.92, g=0.92, b=0.92, a=1.0, profile="sRGB")
    key = primitives.ColorX(r=0.18, g=0.18, b=0.24, a=1.0, profile="sRGB")
    fire_tint = primitives.ColorX(r=0.55, g=0.08, b=0.32, a=1.0, profile="sRGB")
    sim = await f.slot(panel, "Simulator")
    await f.add(sim, FE + "UIX.RectTransform")
    corner = primitives.Float2(x=0.0, y=0.0)

    async def label(parent, text, size=20.0):
        t = await f.slot(parent, "Label")
        await f.add(t, FE + "UIX.RectTransform")
        return await f.add(t, FE + "UIX.Text", Content=text, Size=size, HorizontalAutoSize=False,
                           VerticalAutoSize=False, HorizontalAlign="Center", VerticalAlign="Middle", Color=white)

    async def box(name, x0, y0, x1, y1):
        b = await f.slot(sim, name)
        await f.add(b, FE + "UIX.RectTransform", AnchorMin=corner, AnchorMax=corner,
                    OffsetMin=primitives.Float2(x=x0, y=y0), OffsetMax=primitives.Float2(x=x1, y=y1))
        return b

    async def button(name, text, x0, y0, x1, y1, tint=key):
        b = await box(name, x0, y0, x1, y1)
        await f.add(b, FE + "UIX.Image", Tint=tint)
        btn = await f.add(b, FE + "UIX.Button")
        await label(b, text)
        ref = await f.add(b, FE + f"ProtoFlux.GlobalReference<{FE}IButton>")
        await f.wire(ref, Reference=btn)
        events = await f.add(b, PF + "FrooxEngine.Interaction.ButtonEvents")
        return await f.wire(events, Button=ref)

    # The chosen action: a field, its label, and the tags built from it.
    flux = await f.slot(sim, "Flux")
    chosen = await f.add(flux, FE + "ValueField<int>", Value=SIMULATOR_PRESETS[2])
    chosen_ref = await f.add(flux, FE + f"ProtoFlux.GlobalReference<{FE}IValue<int>>")
    await f.wire(chosen_ref, Reference=chosen.member("Value"))
    n = await f.add(flux, "[ProtoFluxBindings]FrooxEngine.FrooxEngine.ProtoFlux.CoreNodes.ValueSource<int>")
    await f.wire(n, Source=chosen_ref)

    async def concat(a, b):
        node = await f.add(flux, PF + "Strings.ConcatenateString")
        return await f.wire(node, A=a, B=b)

    number = await f.add(flux, PF + "ParsingFormatting.ToString_Int")
    await f.wire(number, **{_member_of(number, "V", "Value", "Input"): n})
    tag = await concat(await f.const(flux, STR, "FluxAction"), number)
    pressed_tag = await concat(tag, await f.const(flux, STR, ".Pressed"))
    released_tag = await concat(tag, await f.const(flux, STR, ".Released"))

    shown = await box("Chosen", 86.0, 12.0, 316.0, 62.0)
    shown_text = await label(shown, f"FluxAction{SIMULATOR_PRESETS[2]}", size=24.0)
    shown_ref = await f.add(flux, FE + f"ProtoFlux.GlobalReference<{FE}IValue<string>>")
    await f.wire(shown_ref, Reference=shown_text.member("Content"))
    shown_src = await f.add(flux, "[ProtoFluxBindings]FrooxEngine.FrooxEngine.ProtoFlux.CoreNodes.ObjectValueSource<string>")
    await f.wire(shown_src, Source=shown_ref)
    relabel = await f.add(flux, PF + f"ObjectWrite<{FEC},string>")
    await f.wire(relabel, Variable=shown_src, Value=tag)

    async def choose(events, value_node):
        write = await f.add(flux, PF + f"ValueWrite<{FEC},int>")
        await f.wire(write, Variable=n, Value=value_node, **{_next(write): relabel})
        await f.wire(events, Pressed=write)

    # Row 1: presets.
    for i, preset in enumerate(SIMULATOR_PRESETS):
        x0 = 16.0 + i * 80.0
        events = await button(f"Preset {preset}", str(preset), x0, 70.0, x0 + 70.0, 120.0)
        await choose(events, await f.const(flux, "int", preset))

    # Row 2: -, the chosen action, +, Fire.
    for text, delta, x0 in (("-", -1, 16.0), ("+", 1, 326.0)):
        events = await button(f"Step {text}", text, x0, 12.0, x0 + 60.0, 62.0)
        step = await f.add(flux, PF + "Operators.ValueAdd<int>")
        await f.wire(step, A=n, B=await f.const(flux, "int", delta))
        clamp = await f.add(flux, PF + "Math.ValueClamp<int>")
        await f.wire(clamp, **{_member_of(clamp, "Value", "V", "Input"): step,
                               _member_of(clamp, "Min"): await f.const(flux, "int", 1),
                               _member_of(clamp, "Max"): await f.const(flux, "int", COUNT)})
        await choose(events, clamp)

    fire = await button("Fire", "Fire (hold)", 406.0, 12.0, 744.0, 62.0, tint=fire_tint)
    root = await f.ref(flux, SLOT, user.id)
    skip = await f.const(flux, "bool", True)
    for when, event_tag, value in (("Pressed", pressed_tag, True), ("Released", released_tag, False)):
        with_value = await f.add(flux, PF + "Actions.DynamicImpulseTriggerWithValue<bool>")
        await f.wire(with_value, Tag=tag, TargetHierarchy=root, ExcludeDisabled=skip,
                     Value=await f.const(flux, "bool", value))
        edge = await f.add(flux, PF + "Actions.DynamicImpulseTrigger")
        await f.wire(edge, Tag=event_tag, TargetHierarchy=root, ExcludeDisabled=skip, Next=with_value)
        await f.wire(fire, **{when: edge})


def _member_of(node, *names):
    for name in names:
        if name in node.members:
            return name
    raise LinkError(f"{node!r} has none of {names}: {sorted(node.members)}")


def _next(write_node):
    """A write node's continuation after a successful write (named OnWritten in current builds)."""
    for name in ("OnWritten", "Next", "OnSuccess"):
        if name in write_node.members:
            return name
    raise LinkError(f"no continuation on {write_node!r}: {sorted(write_node.members)}")


# ── FluxAction1: the Dev Tool ──

async def build_devtool(f: Flux, parent):
    await f.remove_named(parent, DEVTOOL)
    home = await f.slot(parent, DEVTOOL)
    # A Dev Tool of our own, parked inactive here between uses (a DevTool builds its own visual when attached).
    tool_slot = await f.slot(home, "Dev Tool", active=False)
    tool = await f.add(tool_slot, FE + "DevTool")
    flux = await f.slot(home, "Flux")

    ref_tool = await f.ref(flux, FE + "ITool", tool)
    ref_slot = await f.ref(flux, SLOT, tool_slot)
    ref_home = await f.ref(flux, SLOT, home)
    right = await f.const(flux, "[Renderite.Shared]Renderite.Shared.Chirality", "Right")
    yes = await f.const(flux, "bool", True)
    no = await f.const(flux, "bool", False)

    # Equipped: put it away (dequip, back home, inactive). Otherwise: activate it and equip it in the right hand.
    hide = await f.add(flux, PF + "FrooxEngine.Slots.SetSlotActiveSelf")
    await f.wire(hide, Instance=ref_slot, Active=no)
    park = await f.add(flux, PF + "FrooxEngine.Slots.SetParent")
    await f.wire(park, Instance=ref_slot, NewParent=ref_home, PreserveGlobalPosition=no, Next=hide)
    dequip = await f.add(flux, PF + "FrooxEngine.Interaction.Tools.DequipTool")
    await f.wire(dequip, Side=right, OnDequipped=park)

    equip = await f.add(flux, PF + "FrooxEngine.Interaction.Tools.EquipTool")
    await f.wire(equip, Tool=ref_tool, Side=right, DequipExisting=yes)
    show = await f.add(flux, PF + "FrooxEngine.Slots.SetSlotActiveSelf")
    await f.wire(show, Instance=ref_slot, Active=yes, Next=equip)

    equipped = await f.add(flux, PF + "FrooxEngine.Interaction.Tools.IsToolEquipped")
    await f.wire(equipped, Tool=ref_tool)
    branch = await f.add(flux, PF + "If")
    await f.wire(branch, Condition=equipped, OnTrue=dequip, OnFalse=show)
    await f.receiver(flux, "FluxAction1.Pressed", on_triggered=branch)
    print("devtool: FluxAction1 equips or puts away the Dev Tool (right hand)")


# ── FluxAction2: fly / walk ──

async def build_fly(f: Flux, parent):
    await f.remove_named(parent, FLY)
    flux = await f.slot(parent, FLY)
    arch = FE + "LocomotionArchetype"

    # Flying already (the active module's archetype is Fly): walk. Otherwise: fly. Modules match by name
    # ("Locomotion.Fly.Name", "Locomotion.WalkRunGripping.Name" / "...WalkRun.Name").
    active = await f.add(flux, PF + "FrooxEngine.Locomotion.GetActiveLocomotionModule")
    archetype = await f.add(flux, PF + "FrooxEngine.Locomotion.GetLocomotionArchetype")
    await f.wire(archetype, Module=active)
    unpack = await f.add(flux, PF + f"UnpackNullable<{arch}>")
    await f.wire(unpack, **{_only_input(unpack): archetype})
    flying = await f.add(flux, PF + f"ValueEquals<{arch}>")
    await f.wire(flying, A=unpack.out("Value"), B=await f.const(flux, arch, "Fly"))

    walk = await f.add(flux, PF + "FrooxEngine.Locomotion.SwitchLocomotionModule")
    await f.wire(walk, ModuleName=await f.const(flux, STR, "WalkRun"))
    fly = await f.add(flux, PF + "FrooxEngine.Locomotion.SwitchLocomotionModule")
    await f.wire(fly, ModuleName=await f.const(flux, STR, "Fly"))
    branch = await f.add(flux, PF + "If")
    await f.wire(branch, Condition=flying, OnTrue=walk, OnFalse=fly)
    await f.receiver(flux, "FluxAction2.Pressed", on_triggered=branch)
    print("fly: FluxAction2 switches between Fly and Walk/Run")


def _only_input(node):
    """The one reference input of a single-input node (UnpackNullable's name for it varies)."""
    from pyresonitelink.data import members
    refs = [k for k, m in node.members.items() if isinstance(m, members.Reference) and not k.startswith("_")
            and k not in ("persistent", "Enabled")]
    if len(refs) != 1:
        raise LinkError(f"expected one input on {node!r}, found {refs}")
    return refs[0]


# ── main ──

async def main(args):
    port = args.port
    if port is None:
        print("Looking for a ResoniteLink session (announced every 10 s)...", flush=True)
        try:
            port, session = await asyncio.to_thread(fluxlink.discover)
        except LinkError as e:
            print(f"FAILED: {e}", file=sys.stderr)
            raise SystemExit(1)
        print(f"Found {session} on port {port}")
    rl = await fluxlink.connect(port)
    f = Flux(rl)
    t0 = time.monotonic()
    try:
        user = await fluxlink.find_user(rl, args.user)
        avatar = await fluxlink.find_avatar(rl, user.id)
        host = avatar.id if avatar is not None else user.id
        if args.command == "remove":
            n = await f.remove_named("Root", CONSOLE) + await f.remove_named(user.id, CONSOLE_RX)
            for parent in {user.id, host}:
                n += await f.remove_named(parent, EXAMPLES)
            print(f"removed {n} slot(s)")
            return
        if args.command in ("console", "all"):
            await build_console(f, user, _parse_actions(args.actions))
        if args.command in ("devtool", "examples", "all"):
            await build_devtool(f, await f.child(host, EXAMPLES))
        if args.command in ("fly", "examples", "all"):
            await build_fly(f, await f.child(host, EXAMPLES))
        where = f"under {avatar.name.value}" if avatar is not None else f"under {user.name.value}"
        if args.command != "console":
            print(f"examples {where} ({EXAMPLES})")
        print(f"{f.count} components in {time.monotonic() - t0:.1f} s, every write read back")
    except LinkError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        raise SystemExit(1)
    finally:
        await rl.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=("console", "devtool", "fly", "examples", "all", "remove"))
    p.add_argument("--port", type=int, help="the session's ResoniteLink port (default: the one announced)")
    p.add_argument("--user", help="part of your user name, when the session has several users")
    p.add_argument("--actions", default=f"1-{COUNT}", help="the FluxActions the console listens to (e.g. 1-8,42)")
    asyncio.run(main(p.parse_args()))
