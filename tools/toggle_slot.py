# SPDX-FileCopyrightText: 2026 DrSciCortex
#
# SPDX-License-Identifier: MIT

"""Bind a FluxAction to showing and hiding a part of your avatar (a hat, glasses, a prop), live over ResoniteLink.

  python tools\\toggle_slot.py "Sunglasses" --action 3            each press shows or hides it
  python tools\\toggle_slot.py "Sunglasses" --action 3 --hold     shown only while the button is held
  python tools\\toggle_slot.py "Sunglasses" --action 3 --remove

The slot is found by name anywhere under your avatar. The flux goes under your avatar too, in
"MoreFluxActions Examples/FluxAction3 Toggle Sunglasses": save the avatar to keep it.

Also the smallest complete example of building your own action with fluxlink: find a target, create nodes,
wire them, and let every write be checked.
"""

import argparse
import asyncio
import sys

import fluxlink
from deploy import EXAMPLES, SLOT
from fluxlink import FE, PF, Flux, LinkError


def _find(slot, name):
    """The first slot called name in a slot tree (depth first), or None."""
    for child in slot.children or []:
        if child.name and child.name.value == name:
            return child
        found = _find(child, name)
        if found is not None:
            return found
    return None


async def build_toggle(f: Flux, parent, action, target_id, target_name, hold):
    """FluxActionN shows/hides target: toggled on each press, or shown while held."""
    flux = await f.slot(parent, f"FluxAction{action} Toggle {target_name}")
    target = await f.ref(flux, SLOT, target_id)
    show = await f.add(flux, PF + "FrooxEngine.Slots.SetSlotActiveSelf")
    await f.wire(show, Instance=target)
    if hold:
        # FluxActionN carries the button's state: true on press, false on release. Use it as the active state.
        rx = await f.receiver(flux, f"FluxAction{action}", on_triggered=show, value_type="bool")
        await f.wire(show, Active=rx.out("Value"))
    else:
        # On each press: active = not active.
        active = await f.add(flux, PF + "FrooxEngine.Slots.GetSlotActiveSelf")
        await f.wire(active, Instance=target)
        flipped = await f.add(flux, PF + "Operators.NOT_Bool")
        await f.wire(flipped, A=active)
        await f.wire(show, Active=flipped)
        await f.receiver(flux, f"FluxAction{action}.Pressed", on_triggered=show)
    return flux


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
            raise LinkError("no avatar found under your user root")
        name = f"FluxAction{args.action} Toggle {args.slot}"
        examples = await f.child(avatar.id, EXAMPLES)
        await f.remove_named(examples, name)
        if args.remove:
            print(f"removed {name}")
            return
        tree = fluxlink._check(await rl.get_slot(avatar.id, depth=-1), "get avatar")
        target = _find(tree.data, args.slot)
        if target is None:
            raise LinkError(f"no slot called {args.slot!r} under {avatar.name.value}")
        await build_toggle(f, examples, args.action, target.id, args.slot, args.hold)
        how = "while held" if args.hold else "on each press"
        print(f"FluxAction{args.action} shows/hides {args.slot} {how} ({f.count} components, every write read back)")
    except LinkError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        raise SystemExit(1)
    finally:
        await rl.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("slot", help="the name of the slot to show and hide, anywhere under your avatar")
    p.add_argument("--action", type=int, required=True, choices=range(1, 43), metavar="1..42")
    p.add_argument("--hold", action="store_true", help="shown only while the button is held")
    p.add_argument("--remove", action="store_true", help="remove this binding")
    p.add_argument("--port", type=int, help="the session's ResoniteLink port (default: the one announced)")
    p.add_argument("--user", help="part of your user name, when the session has several users")
    asyncio.run(main(p.parse_args()))
