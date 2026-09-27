# SPDX-FileCopyrightText: 2026 DrSciCortex
#
# SPDX-License-Identifier: MIT

"""A pointing laser on the two-finger point, and FluxAction groups switched from a button, live over ResoniteLink.

    python tools\\laser_pointer.py [--pointer LaserPointer]     build (again)
    python tools\\laser_pointer.py --remove

Group 1 (a slot under your user root) holds the laser: while you hold the two-finger point (FluxAction36 on the
left hand, 37 on the right), the laser pointer in the world rides on that index finger, aimed along it, with its
beam on; let go and it returns where it was, beam off.

FluxAction1 (on a CyberFinger, the left black button held) switches group 1 on and off: the mod doesn't fire into
inactive slots, so a group's actions stop while it's off. A popup in front of you, to the left, says which for
2.5 s. Only you see it: its text is a ValueUserOverride (empty by default) with CreateOverrideOnWrite, and the flux
writing it runs on your client, so the message is an override of yours alone.

The laser pointer is any world object with a beam switched by a DataModelBooleanToggle (a "Boolean Latch" slot), its
beam along its own +Z: the Resonite laser pointer tool's layout. It's found by name under the world root.
"""

import argparse
import asyncio
import sys

from pyresonitelink.data import primitives

import fluxlink
from fluxlink import FE, FEC, PF, Flux, LinkError

GROUP = "MoreFluxActions Group 1"
TOGGLES = "MoreFluxActions Group Toggles"
POPUP = "MoreFluxActions Popup"
EXAMPLES, DEVTOOL = "MoreFluxActions Examples", "FluxAction1 Dev Tool"
POPUP_SECONDS = 2.5
POPUP_SIZE = 0.15        # text height, m; 0.42 m ahead of the eyes
BODY_NODE = "[Renderite.Shared]Renderite.Shared.BodyNode"
SLOT, STR = FE + "Slot", "string"
HANDS = (("Left", 36), ("Right", 37))


def _find(slot, predicate):
    if predicate(slot):
        return slot
    for child in slot.children or []:
        found = _find(child, predicate)
        if found is not None:
            return found
    return None


def _member(node, *names):
    for name in names:
        if name in node.members:
            return name
    raise LinkError(f"{node!r} has none of {names}: {sorted(node.members)}")


async def _pointer_parts(rl, name):
    """The pointer slot, and its beam latch's stored value (the member to write)."""
    # Under the world root, or (once used) under its home there.
    root = fluxlink._check(await rl.get_slot("Root", depth=2), "get Root")
    named = lambda c, n: c.name and c.name.value == n
    pointer = next((c for c in root.data.children if named(c, name)), None)
    for home in (c for c in root.data.children if named(c, name + " Home")):
        pointer = pointer or next((c for c in home.children or [] if named(c, name)), None)
    if pointer is None:
        raise LinkError(f"no slot called {name!r} under the world root or its home (let go of the point first)")
    tree = fluxlink._check(await rl.get_slot(pointer.id, depth=-1, includeComponentData=True), "get pointer").data
    latch = _find(tree, lambda s: any((c.componentType or "").endswith("DataModelValueFieldStore<bool>+Store")
                                      for c in s.components or []))
    if latch is None:
        raise LinkError(f"{name!r} has no Boolean Latch (DataModelBooleanToggle) to switch its beam")
    store = next(c for c in latch.components if (c.componentType or "").endswith("DataModelValueFieldStore<bool>+Store"))
    return tree, store


async def build(f: Flux, user, head_id, pointer_name):
    rl = f.rl
    pointer, store = await _pointer_parts(rl, pointer_name)
    for parent, name in ((user.id, GROUP), (user.id, TOGGLES), (head_id, POPUP)):
        await f.remove_named(parent, name)
    # FluxAction1 is the group toggle now: the Dev Tool example on it would fire as well.
    avatar = await fluxlink.find_avatar(rl, user.id)
    if avatar is not None:
        examples = await f.child(avatar.id, EXAMPLES, create=False)
        if examples and await f.remove_named(examples, DEVTOOL):
            print("removed the Dev Tool example: FluxAction1 is the group toggle now")

    # Where the pointer goes back to: where it is now (made once, kept across rebuilds).
    home_name = pointer_name + " Home"
    home = await f.child("Root", home_name, create=False)
    if home is None:
        p, r = pointer.position.value, pointer.rotation.value
        home = await f.slot("Root", home_name, position=(p.x, p.y, p.z), rotation=(r.x, r.y, r.z, r.w))
    beam = await f.read(store.id)
    await f.set(beam, Value=False)                                   # off until pointed

    # ── group 1: the laser ──
    group = await f.slot(user.id, GROUP)
    laser = await f.slot(group, "Laser")
    ref_pointer = await f.ref(laser, SLOT, pointer.id)
    ref_home = await f.ref(laser, SLOT, home)
    latch_field = await f.add(laser, FE + "ProtoFlux.GlobalReference<" + FE + "IValue<bool>>")
    await f.wire(latch_field, Reference=beam.member("Value"))
    latch = await f.add(laser, "[ProtoFluxBindings]FrooxEngine.FrooxEngine.ProtoFlux.CoreNodes.ValueSource<bool>")
    await f.wire(latch, Source=latch_field)
    yes, no = await f.const(laser, "bool", True), await f.const(laser, "bool", False)
    user_node = await f.add(laser, PF + "FrooxEngine.Users.LocalUser")
    up = await f.const(laser, "float3", primitives.Float3(0.0, 1.0, 0.0))

    # Let go: beam off, back home (global scale kept), home's pose.
    home_pose = await f.add(laser, PF + "FrooxEngine.Transform.SetLocalPositionRotation")
    await f.wire(home_pose, Instance=ref_pointer)
    park = await f.add(laser, PF + "FrooxEngine.Slots.SetParent")
    await f.wire(park, Instance=ref_pointer, NewParent=ref_home, PreserveGlobalPosition=yes, Next=home_pose)
    beam_off = await f.add(laser, PF + f"ValueWrite<{FEC},bool>")
    await f.wire(beam_off, Variable=latch, Value=no, **{_member(beam_off, "OnWritten"): park})

    for side, action in HANDS:
        s = await f.slot(laser, f"{side} hand (FluxAction{action})")
        bone = {}
        for part in ("Proximal", "Distal"):
            node = await f.add(s, PF + "FrooxEngine.Avatar.BodyNodeSlot")
            await f.wire(node, Source=user_node, Node=await f.const(s, BODY_NODE, f"{side}IndexFinger_{part}"))
            xform = await f.add(s, PF + "FrooxEngine.Transform.GlobalTransform")
            await f.wire(xform, Instance=node)
            bone[part] = (node, xform)
        along = await f.add(s, PF + "Operators.ValueSub<float3>")
        await f.wire(along, A=bone["Distal"][1].out("GlobalPosition"), B=bone["Proximal"][1].out("GlobalPosition"))
        unit = await f.add(s, PF + "Operators.Normalized_Float3")
        await f.wire(unit, **{_member(unit, "A", "V", "Value", "Input"): along})
        aim = await f.add(s, PF + "Math.Quaternions.LookRotation_floatQ")
        await f.wire(aim, Forward=unit, Up=up)
        # Point: onto the finger's end bone (it then follows the hand), aimed along the finger, beam on.
        beam_on = await f.add(s, PF + f"ValueWrite<{FEC},bool>")
        await f.wire(beam_on, Variable=latch, Value=yes)
        place = await f.add(s, PF + "FrooxEngine.Transform.SetGlobalPositionRotation")
        await f.wire(place, Instance=ref_pointer, Position=bone["Distal"][1].out("GlobalPosition"), Rotation=aim,
                     Next=beam_on)
        attach = await f.add(s, PF + "FrooxEngine.Slots.SetParent")
        await f.wire(attach, Instance=ref_pointer, NewParent=bone["Distal"][0], PreserveGlobalPosition=yes,
                     Next=place)
        rx = await f.receiver(s, f"FluxAction{action}", value_type="bool")
        branch = await f.add(s, PF + "If")
        await f.wire(branch, Condition=rx.out("Value"), OnTrue=attach, OnFalse=beam_off)
        await f.wire(rx, OnTriggered=branch)

    # ── the popup: front left of your head, seen only by you ──
    # Its text is per user: empty by default, and a write from your client (the flux runs there) sets yours alone.
    # (A slot's own fields, like its active state, can't be targeted over ResoniteLink: it gives them no IDs.)
    popup = await f.slot(head_id, POPUP)
    text_slot = await f.slot(popup, "Text", position=(-0.05, -0.08, 0.42))
    text = await f.add(text_slot, FE + "TextRenderer", Text="", Size=POPUP_SIZE, HorizontalAlign="Center",
                       Color=primitives.ColorX(r=1.0, g=1.0, b=1.0, a=1.0, profile="sRGB"))
    override = await f.add(popup, FE + "ValueUserOverride<string>", CreateOverrideOnWrite=True)
    await f.wire(override, Target=text.member("Text"))

    # ── FluxAction1: group 1 on/off ──
    toggles = await f.slot(user.id, TOGGLES)
    t = await f.slot(toggles, "Group 1 (FluxAction1)")
    ref_group = await f.ref(t, SLOT, group)
    t_yes, t_no = await f.const(t, "bool", True), await f.const(t, "bool", False)
    active = await f.add(t, PF + "FrooxEngine.Slots.GetSlotActiveSelf")
    await f.wire(active, Instance=ref_group)
    # The popup: "Group 1 on/off", green or amber, cleared after POPUP_SECONDS (the delay's Next; its OnTriggered
    # fires at once).
    words_field = await f.add(t, FE + "ProtoFlux.GlobalReference<" + FE + "IValue<string>>")
    await f.wire(words_field, Reference=text.member("Text"))
    words = await f.add(t, "[ProtoFluxBindings]FrooxEngine.FrooxEngine.ProtoFlux.CoreNodes.ObjectValueSource<string>")
    await f.wire(words, Source=words_field)
    clear = await f.add(t, PF + f"ObjectWrite<{FEC},string>")
    await f.wire(clear, Variable=words, Value=await f.const(t, STR, ""))
    delay = await f.add(t, PF + "DelaySecondsFloat")
    await f.wire(delay, Duration=await f.const(t, "float", POPUP_SECONDS), Next=clear)
    show = await f.add(t, PF + "FrooxEngine.Async.StartAsyncTask")
    await f.wire(show, TaskStart=delay)
    colour_field = await f.add(t, FE + "ProtoFlux.GlobalReference<" + FE + "IValue<colorX>>")
    await f.wire(colour_field, Reference=text.member("Color"))
    colour = await f.add(t, "[ProtoFluxBindings]FrooxEngine.FrooxEngine.ProtoFlux.CoreNodes.ValueSource<colorX>")
    await f.wire(colour, Source=colour_field)
    colour_now = await f.add(t, PF + "ValueConditional<colorX>")
    await f.wire(colour_now, Condition=active,
                 OnTrue=await f.const(t, "colorX", primitives.ColorX(r=0.35, g=1.0, b=0.45, a=1.0, profile="sRGB")),
                 OnFalse=await f.const(t, "colorX", primitives.ColorX(r=1.0, g=0.65, b=0.2, a=1.0, profile="sRGB")))
    set_colour = await f.add(t, PF + f"ValueWrite<{FEC},colorX>")
    await f.wire(set_colour, Variable=colour, Value=colour_now, OnWritten=show)
    words_now = await f.add(t, PF + "ObjectConditional<string>")
    await f.wire(words_now, Condition=active, OnTrue=await f.const(t, STR, "Group 1 on"),
                 OnFalse=await f.const(t, STR, "Group 1 off"))
    set_words = await f.add(t, PF + f"ObjectWrite<{FEC},string>")
    await f.wire(set_words, Variable=words, Value=words_now, OnWritten=set_colour)
    # Switched off: put the laser away too, in case it was pointing.
    off_home = await f.add(t, PF + "FrooxEngine.Transform.SetLocalPositionRotation")
    await f.wire(off_home, Instance=await f.ref(t, SLOT, pointer.id), Next=set_words)
    off_park = await f.add(t, PF + "FrooxEngine.Slots.SetParent")
    await f.wire(off_park, Instance=await f.ref(t, SLOT, pointer.id), NewParent=await f.ref(t, SLOT, home),
                 PreserveGlobalPosition=t_yes, Next=off_home)
    off_beam = await f.add(t, PF + f"ValueWrite<{FEC},bool>")
    await f.wire(off_beam, Variable=latch, Value=t_no, OnWritten=off_park)
    now_on = await f.add(t, PF + "If")
    await f.wire(now_on, Condition=active, OnTrue=set_words, OnFalse=off_beam)
    flip = await f.add(t, PF + "Operators.NOT_Bool")
    await f.wire(flip, A=active)
    switch = await f.add(t, PF + "FrooxEngine.Slots.SetSlotActiveSelf")
    await f.wire(switch, Instance=ref_group, Active=flip, Next=now_on)
    await f.receiver(t, "FluxAction1.Pressed", on_triggered=switch)
    print(f"group 1: the laser on the two-finger point (FluxAction36 left, 37 right), toggled by FluxAction1; "
          f"pointer {pointer_name!r}, home {home_name!r}")


async def main(args):
    port = args.port
    if port is None:
        port, _ = await asyncio.to_thread(fluxlink.discover)
    rl = await fluxlink.connect(port)
    f = Flux(rl)
    try:
        user = await fluxlink.find_user(rl, args.user)
        head = await f.child(user.id, "Head", create=False)
        if head is None:
            raise LinkError("no Head slot under your user root")
        if args.remove:
            n = sum([await f.remove_named(user.id, GROUP), await f.remove_named(user.id, TOGGLES),
                     await f.remove_named(head, POPUP)])
            print(f"removed {n} slot(s); the pointer and its home stay in the world")
            return
        await build(f, user, head, args.pointer)
        print(f"{f.count} components, every write read back")
    except LinkError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        raise SystemExit(1)
    finally:
        await rl.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pointer", default="LaserPointer", help="the laser pointer's slot name, under the world root")
    p.add_argument("--remove", action="store_true", help="remove group 1, its toggle and the popup")
    p.add_argument("--port", type=int, help="the session's ResoniteLink port (default: the one announced)")
    p.add_argument("--user", help="part of your user name, when the session has several users")
    asyncio.run(main(p.parse_args()))
