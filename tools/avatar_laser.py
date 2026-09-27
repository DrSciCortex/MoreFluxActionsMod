# SPDX-FileCopyrightText: 2026 DrSciCortex
#
# SPDX-License-Identifier: MIT

"""A laser pointer built into your avatar, on the two-finger point, switched from your dial, live over ResoniteLink.

    python tools\\avatar_laser.py            build (again), under your avatar
    python tools\\avatar_laser.py --remove

While you hold the two-finger point (FluxAction36 on the left hand, 37 on the right), a beam leaves that index finger,
aimed along it, up to what it hits (a dot there) or 20 m. Let go and it's gone. No world object is needed: save the
avatar and it works in any world where MoreFluxActions runs.

Your dial (context menu) gets a "Laser" item that switches the gesture on and off; the choice is saved with the avatar.

How it's built. The gesture's flux runs on your client (the mod fires there): it puts the beam on the finger's end bone,
aimed along the finger, and switches it on or off (synced, once per gesture). The beam's length and the dot come from
a Raycaster evaluated through drives, which every client computes for itself: nothing is sent while you point.
"""

import argparse
import asyncio
import sys

from pyresonitelink.data import members, primitives, workers

import fluxlink
from fluxlink import FE, FEC, PF, Flux, LinkError
from laser_pointer import BODY_NODE, GROUP, HANDS, POPUP, SLOT, TOGGLES

LASER = "MoreFluxActions Laser"                  # under the avatar
BEAM = LASER + " Beam"                           # + " (Left)" / " (Right)": moved onto the finger bone when used
CORE = "[ProtoFluxBindings]FrooxEngine.FrooxEngine.ProtoFlux.CoreNodes."
REACH = 20.0                                     # m, the beam's length when it hits nothing
BEAM_RADIUS, DOT_RADIUS, DOT_LENGTH = 0.0015, 0.008, 0.004
GREEN = primitives.ColorX(r=0.15, g=1.0, b=0.25, a=1.0, profile="sRGB")
GREY = primitives.ColorX(r=0.55, g=0.55, b=0.55, a=1.0, profile="sRGB")


async def set_list(f: Flux, node, name, targets):
    """A reference list member (MeshRenderer.Materials …) set to targets, read back."""
    m = node.member(name)
    if not isinstance(m, members.SyncList):
        raise LinkError(f"{fluxlink.short(node.type)}.{name} is a {type(m).__name__}, not a list")
    elements = [members.Reference(targetId=fluxlink._target_id(t)) for t in targets]
    fluxlink._check(await f.rl.update_component(workers.Component(id=node.id, componentType=node.type,
                                                                  members={name: members.SyncList(id=m.id, elements=elements)})),
                    f"set {fluxlink.short(node.type)}.{name}")
    fresh = await f.read(node.id)
    got = [getattr(e, "targetId", None) for e in fresh.member(name).elements]
    if got != [fluxlink._target_id(t) for t in targets]:
        raise LinkError(f"{fluxlink.short(node.type)}.{name} holds {got} after setting it")
    node.members = fresh.members
    return node


async def drive(f: Flux, slot, type_arg, target_member, value):
    """A ValueFieldDrive<T> driving target_member from value. Its target sits on the proxy it gets on the slot."""
    node = await f.add(slot, CORE + f"ValueFieldDrive<{type_arg}>")
    await f.wire(node, Value=value)
    comps = fluxlink._check(await f.rl.get_slot(slot, depth=0, includeComponentData=True), "get drive slot").data
    proxy = next((c for c in comps.components or [] if (c.componentType or "").endswith("+Proxy")
                  and getattr((c.members or {}).get("Node"), "targetId", None) == node.id), None)
    if proxy is None:
        raise LinkError(f"no drive proxy for ValueFieldDrive<{type_arg}>")
    await f.wire(await f.read(proxy.id), Drive=target_member)
    return node


async def beam_visual(f: Flux, parent, name, avatar_id):
    """A beam slot (inactive): the line and the dot, driven from a raycast along its +Z."""
    beam = await f.slot(parent, name, active=False)
    material = await f.add(beam, FE + "UnlitMaterial", TintColor=GREEN, BlendMode="Additive")
    line = await f.add(beam, FE + "SegmentMesh", Radius=BEAM_RADIUS)
    line_renderer = await f.add(beam, FE + "MeshRenderer")
    await f.wire(line_renderer, Mesh=line)
    await set_list(f, line_renderer, "Materials", [material])
    dot_slot = await f.slot(beam, "Dot")
    dot = await f.add(dot_slot, FE + "SegmentMesh", Radius=DOT_RADIUS)
    dot_renderer = await f.add(dot_slot, FE + "MeshRenderer")
    await f.wire(dot_renderer, Mesh=dot)
    await set_list(f, dot_renderer, "Materials", [material])

    # Where it hits, in the beam's own space: the line ends there (or at REACH), the dot sits there.
    flux = await f.slot(beam, "Flux")
    me = await f.ref(flux, SLOT, beam)
    at = await f.add(flux, PF + "FrooxEngine.Transform.GlobalTransform")
    await f.wire(at, Instance=me)
    ahead = await f.add(flux, PF + "FrooxEngine.Transform.LocalDirectionToGlobal")
    await f.wire(ahead, Instance=me, LocalDirection=await f.const(flux, "float3", primitives.Float3(0.0, 0.0, 1.0)))
    ray = await f.add(flux, PF + "FrooxEngine.Physics.Raycaster")
    await f.wire(ray, Origin=at.out("GlobalPosition"), Direction=ahead, MaxDistance=await f.const(flux, "float", REACH),
                 IgnoreHierarchy=await f.ref(flux, SLOT, avatar_id))
    hit = await f.add(flux, PF + "FrooxEngine.Transform.GlobalPointToLocal")
    await f.wire(hit, Instance=me, GlobalPoint=ray.out("HitPoint"))
    end = await f.add(flux, PF + "ValueConditional<float3>")
    await f.wire(end, Condition=ray.out("HasHit"), OnTrue=hit,
                 OnFalse=await f.const(flux, "float3", primitives.Float3(0.0, 0.0, REACH)))
    dot_start = await f.add(flux, PF + "Operators.ValueSub<float3>")
    await f.wire(dot_start, A=end, B=await f.const(flux, "float3", primitives.Float3(0.0, 0.0, DOT_LENGTH)))
    await drive(f, flux, "float3", line.member("PointB"), end)
    await drive(f, flux, "float3", dot.member("PointA"), dot_start)
    await drive(f, flux, "float3", dot.member("PointB"), end)
    await drive(f, flux, "bool", dot_renderer.member("Enabled"), ray.out("HasHit"))
    return beam


async def dial_item(f: Flux, parent):
    """The dial's "Laser" item: a ButtonToggle on an enabled flag, which labels and colours the item."""
    item = await f.slot(parent, "Dial item")
    enabled = await f.add(item, FE + "ValueField<bool>", Value=True)
    source = await f.add(item, FE + "ContextMenuItemSource", Label="Laser: on", Color=GREEN)
    root_item = await f.add(item, FE + "RootContextMenuItem")
    await f.wire(root_item, Item=source)
    toggle = await f.add(item, FE + "ButtonToggle")
    await f.wire(toggle, TargetValue=enabled.member("Value"))
    for kind, on, off, target in (("string", "Laser: on", "Laser: off", source.member("Label")),
                                  ("colorX", GREEN, GREY, source.member("Color"))):
        shown = await f.add(item, FE + f"BooleanValueDriver<{kind}>", TrueValue=on, FalseValue=off)
        await f.wire(shown, TargetField=target)
        copy = await f.add(item, FE + "ValueCopy<bool>")
        await f.wire(copy, Source=enabled.member("Value"), Target=shown.member("State"))
    return enabled


async def gesture(f: Flux, parent, side, action, beam, enabled):
    """FluxAction36/37: while the two-finger point is held (and the dial allows it), the beam on that index finger."""
    s = await f.slot(parent, f"{side} hand (FluxAction{action})")
    beam_ref = await f.ref(s, SLOT, beam)
    yes, no = await f.const(s, "bool", True), await f.const(s, "bool", False)
    user = await f.add(s, PF + "FrooxEngine.Users.LocalUser")
    bone = {}
    for part in ("Proximal", "Distal"):
        node = await f.add(s, PF + "FrooxEngine.Avatar.BodyNodeSlot")
        await f.wire(node, Source=user, Node=await f.const(s, BODY_NODE, f"{side}IndexFinger_{part}"))
        xform = await f.add(s, PF + "FrooxEngine.Transform.GlobalTransform")
        await f.wire(xform, Instance=node)
        bone[part] = (node, xform)
    along = await f.add(s, PF + "Operators.ValueSub<float3>")
    await f.wire(along, A=bone["Distal"][1].out("GlobalPosition"), B=bone["Proximal"][1].out("GlobalPosition"))
    unit = await f.add(s, PF + "Operators.Normalized_Float3")
    await f.wire(unit, **{fluxlink_input(unit): along})
    aim = await f.add(s, PF + "Math.Quaternions.LookRotation_floatQ")
    await f.wire(aim, Forward=unit, Up=await f.const(s, "float3", primitives.Float3(0.0, 1.0, 0.0)))

    on = await f.add(s, PF + "FrooxEngine.Slots.SetSlotActiveSelf")
    await f.wire(on, Instance=beam_ref, Active=yes)
    place = await f.add(s, PF + "FrooxEngine.Transform.SetGlobalPositionRotation")
    await f.wire(place, Instance=beam_ref, Position=bone["Distal"][1].out("GlobalPosition"), Rotation=aim, Next=on)
    attach = await f.add(s, PF + "FrooxEngine.Slots.SetParent")
    await f.wire(attach, Instance=beam_ref, NewParent=bone["Distal"][0], PreserveGlobalPosition=yes, Next=place)
    off = await f.add(s, PF + "FrooxEngine.Slots.SetSlotActiveSelf")
    await f.wire(off, Instance=beam_ref, Active=no)

    allowed_ref = await f.add(s, FE + f"ProtoFlux.GlobalReference<{FE}IValue<bool>>")
    await f.wire(allowed_ref, Reference=enabled.member("Value"))
    allowed = await f.add(s, CORE + "ValueSource<bool>")
    await f.wire(allowed, Source=allowed_ref)
    rx = await f.receiver(s, f"FluxAction{action}", value_type="bool")
    show = await f.add(s, PF + "Operators.AND_Bool")
    await f.wire(show, A=rx.out("Value"), B=allowed)
    branch = await f.add(s, PF + "If")
    await f.wire(branch, Condition=show, OnTrue=attach, OnFalse=off)
    await f.wire(rx, OnTriggered=branch)


def fluxlink_input(node):
    for name in ("A", "V", "Value", "Input"):
        if name in node.members:
            return name
    raise LinkError(f"{node!r}: no input among A, V, Value, Input")


async def remove(f: Flux, avatar_id):
    """This rig: its root, and beams already moved onto finger bones."""
    n = await f.remove_named(avatar_id, LASER)
    tree = fluxlink._check(await f.rl.get_slot(avatar_id, depth=-1), "get avatar").data
    found = []

    def walk(s):
        if s.name and (s.name.value or "").startswith(BEAM):
            found.append(s.id)
            return
        for c in s.children or []:
            walk(c)

    walk(tree)
    for slot_id in found:
        fluxlink._check(await f.rl.remove_slot(slot_id), "remove beam")
    return n + len(found)


async def build(f: Flux, user, avatar):
    await remove(f, avatar.id)
    # laser_pointer.py's world rig listens to the same gestures: this replaces it.
    head = await f.child(user.id, "Head", create=False)
    old = await f.remove_named(user.id, GROUP) + await f.remove_named(user.id, TOGGLES)
    if head is not None:
        old += await f.remove_named(head, POPUP)
    if old:
        print("removed laser_pointer.py's world rig (group 1, its FluxAction1 toggle and popup): this replaces it")

    laser = await f.slot(avatar.id, LASER)
    enabled = await dial_item(f, laser)
    for side, action in HANDS:
        beam = await beam_visual(f, laser, f"{BEAM} ({side})", avatar.id)
        await gesture(f, laser, side, action, beam, enabled)
    print(f"avatar laser under {avatar.name.value}: two-finger point FluxAction36 left, 37 right; "
          f"'Laser: on/off' in your dial")


async def main(args):
    port = args.port
    if port is None:
        port, _ = await asyncio.to_thread(fluxlink.discover)
    rl = await fluxlink.connect(port)
    f = Flux(rl)
    try:
        user = await fluxlink.find_user(rl, args.user)
        avatar = await fluxlink.find_avatar(rl, user.id)
        if avatar is None:
            raise LinkError("no avatar under your user root (an AvatarRoot): equip one first")
        if args.remove:
            print(f"removed {await remove(f, avatar.id)} slot(s)")
            return
        await build(f, user, avatar)
        print(f"{f.count} components, every write read back. Save your avatar to keep it.")
    except LinkError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        raise SystemExit(1)
    finally:
        await rl.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--remove", action="store_true", help="remove the avatar laser")
    p.add_argument("--port", type=int, help="the session's ResoniteLink port (default: the one announced)")
    p.add_argument("--user", help="part of your user name, when the session has several users")
    asyncio.run(main(p.parse_args()))
