# SPDX-FileCopyrightText: 2026 DrSciCortex
#
# SPDX-License-Identifier: MIT

"""A small builder for ProtoFlux and other components in a live Resonite session, over ResoniteLink
(pyresonitelink).

Components are created empty, then set and wired by member name ("create then wire"). Every write is read back:
one that didn't land raises LinkError instead of leaving a graph that silently does nothing (the usual failure:
a reference to an incompatible node is dropped without an error). Member names and reference types come from
the live component, so nothing here guesses at the data model; a wrong name lists the ones that exist.
"""

import asyncio
import re
import time

import numpy as np
from pyresonitelink import client
from pyresonitelink.data import codec, members, primitives, workers


class NullableFieldEnum(members.FieldEnum):
    """An "enum?" field. pyresonitelink registers FieldEnum for both "enum" and "enum?", and the later one wins
    when encoding, so every enum went out as nullable (which Resonite refuses for a plain enum field). Giving
    "enum?" its own class makes each round-trip as it came."""


codec._register_type("enum?", NullableFieldEnum)
codec._register_type("enum", members.FieldEnum)

PF = "[ProtoFluxBindings]FrooxEngine.ProtoFlux.Runtimes.Execution.Nodes."
FE = "[FrooxEngine]FrooxEngine."
FEC = FE + "ProtoFlux.FrooxEngineContext"      # the context type argument of data-model writes


class LinkError(RuntimeError):
    """ResoniteLink refused a request, or a write didn't land."""


def short(type_name):
    """A component type without assembly and namespaces: ...Nodes.ObjectWrite<[FrooxEngine]...,string> ->
    ObjectWrite<FrooxEngineContext,string>."""
    return re.sub(r"\[[^\]]*\]|[\w]+\.", "", type_name or "?")


def _check(response, what):
    if not getattr(response, "success", False):
        raise LinkError(f"{what}: {getattr(response, 'errorInfo', None) or response}")
    return response


class Node:
    """A component in the session: its id, type and members (name -> Member, as last read)."""

    def __init__(self, id, type, members):
        self.id, self.type, self.members = id, type, members

    def member(self, name):
        m = self.members.get(name)
        if m is None:
            raise LinkError(f"{short(self.type)} has no member {name!r}; it has: {', '.join(sorted(self.members))}")
        return m

    def out(self, name):
        """One output of a node that has several (a receiver's Value, UnpackNullable's Value): wired by that
        output's member id. A node with one output is wired by the node itself."""
        return self.member(name).id

    def __repr__(self):
        return f"<{short(self.type)} {self.id}>"


def _target_id(target):
    if target is None or isinstance(target, str):
        return target
    if isinstance(target, Node):
        return target.id
    return target.id                                   # a Member (a field, wired by its id) or a Slot


def _field(member, value):
    """A new value for an existing field member, of the same kind."""
    if isinstance(member, members.FieldEnum):
        return type(member)(id=member.id, value=str(value), enumType=member.enumType)
    cls = type(member)
    default = cls().value if hasattr(cls(), "value") else None
    if isinstance(default, np.generic):
        value = type(default)(value)
    return cls(id=member.id, value=value)


def _same(sent, got):
    """Whether a field reads back as set. Vectors, colours and floats aren't compared (the server's echo may
    round them)."""
    if isinstance(sent, (bool, np.bool_)):
        return bool(sent) == bool(got)
    if isinstance(sent, (str, int, np.integer)):
        return str(sent) == str(got)
    return True


class Flux:
    """Creates slots and components under the slots you give it; remembers nothing but the connection."""

    def __init__(self, rl: client.Client, settle=0.03):
        self.rl, self.settle = rl, settle
        self.count = 0                                 # components created

    # ── slots ──

    async def slot(self, parent, name, position=None, rotation=None, scale=None, active=True):
        kwargs = {}
        if position is not None:
            kwargs["position"] = primitives.Float3(*position)
        if rotation is not None:
            x, y, z, w = rotation
            kwargs["rotation"] = primitives.FloatQ(x=x, y=y, z=z, w=w)
        if scale is not None:
            kwargs["scale"] = primitives.Float3(*scale)
        s = await self.rl.add_slot(parent=parent, name=name, isActive=active, **kwargs)
        if not s or not s.id:
            raise LinkError(f"could not add slot {name!r}")
        return s.id

    async def children(self, slot_id):
        d = _check(await self.rl.get_slot(slot_id, depth=1), f"get slot {slot_id}")
        return list(d.data.children or [])

    async def child(self, parent, name, create=True):
        """The parent's child called name (the first one), created if missing and create is set; else None."""
        for c in await self.children(parent):
            if c.name and c.name.value == name:
                return c.id
        return await self.slot(parent, name) if create else None

    async def remove_named(self, parent, name):
        """Removes the parent's children called name; returns how many."""
        n = 0
        for child in await self.children(parent):
            if child.name and child.name.value == name:
                _check(await self.rl.remove_slot(child.id), f"remove {name}")
                n += 1
        return n

    # ── components ──

    async def read(self, component_id):
        r = _check(await self.rl.get_component(component_id), f"get component {component_id}")
        return Node(component_id, r.data.componentType, dict(r.data.members or {}))

    async def add(self, slot, component_type, **values):
        """A component on slot, its fields then set from values (checked)."""
        r = _check(await self.rl.add_component(slot, componentType=component_type), f"add {short(component_type)}")
        self.count += 1
        await asyncio.sleep(self.settle)
        node = await self.read(r.entityId)
        if node.type is None or "<>" in (node.type or ""):
            raise LinkError(f"{short(component_type)} did not resolve to a concrete type")
        if values:
            await self.set(node, **values)
        return node

    async def set(self, node, **values):
        update = {name: _field(node.member(name), value) for name, value in values.items()}
        _check(await self.rl.update_component(workers.Component(id=node.id, componentType=node.type, members=update)),
               f"set {short(node.type)}.{', '.join(values)}")
        fresh = await self.read(node.id)
        for name, value in values.items():
            got = getattr(fresh.member(name), "value", None)
            if not _same(value, got):
                raise LinkError(f"{short(node.type)}.{name} = {got!r} after setting {value!r}")
        node.members = fresh.members
        return node

    async def wire(self, node, **targets):
        """Points reference members (inputs, impulse outputs, refs) at other nodes, outputs, fields or slots."""
        update = {}
        for name, target in targets.items():
            m = node.member(name)
            if not isinstance(m, members.Reference):
                raise LinkError(f"{short(node.type)}.{name} is a {type(m).__name__}, not a reference")
            update[name] = members.Reference(id=m.id, targetId=_target_id(target), targetType=m.targetType)
        _check(await self.rl.update_component(workers.Component(id=node.id, componentType=node.type, members=update)),
               f"wire {short(node.type)}.{', '.join(targets)}")
        await asyncio.sleep(self.settle)
        fresh = await self.read(node.id)
        for name, target in targets.items():
            got = fresh.member(name).targetId
            if got != _target_id(target):
                raise LinkError(f"{short(node.type)}.{name} did not take {target!r} (it expects "
                                f"{short(node.member(name).targetType)}); it holds {got!r}")
        node.members = fresh.members
        return node

    # ── ProtoFlux conveniences ──

    async def tag(self, slot, text):
        """A dynamic impulse receiver's Tag: a GlobalValue<string> (a ValueObjectInput is refused there)."""
        return await self.add(slot, FE + "ProtoFlux.GlobalValue<string>", Value=text)

    async def const(self, slot, type_arg, value):
        """A constant input node: ValueInput<T> for values, ValueObjectInput<string> for strings."""
        if type_arg == "string":
            return await self.add(slot, PF + "ValueObjectInput<string>", Value=value)
        return await self.add(slot, PF + f"ValueInput<{type_arg}>", Value=value)

    async def ref(self, slot, type_arg, target):
        """A RefObjectInput<T> holding target (a slot or component id, or Node)."""
        node = await self.add(slot, PF + f"RefObjectInput<{type_arg}>")
        return await self.wire(node, Target=target)

    async def receiver(self, slot, tag_text, on_triggered=None, value_type=None):
        """A DynamicImpulseReceiver for tag_text (WithValue<value_type> when given), wired to on_triggered."""
        kind = f"Actions.DynamicImpulseReceiverWithValue<{value_type}>" if value_type else "Actions.DynamicImpulseReceiver"
        tag = await self.tag(slot, tag_text)
        rx = await self.add(slot, PF + kind)
        await self.wire(rx, Tag=tag)
        if on_triggered is not None:
            await self.wire(rx, OnTriggered=on_triggered)
        return rx


ANNOUNCE_PORT = 12512          # ResoniteLink's LinkSessionListener.ANNOUNCE_PORT
ANNOUNCE_INTERVAL = 10.0       # seconds between a session's announcements


def discover(timeout=ANNOUNCE_INTERVAL + 2.0):
    """The first ResoniteLink session announced on this network: (port, session name). Each session with
    ResoniteLink enabled sends {"sessionName", "sessionID", "linkPort"} as JSON to UDP 12512 every 10 s (a
    negative linkPort: it closed). Waits up to timeout for one; raises LinkError without."""
    import json
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)     # Resonite and others may listen too
        sock.bind(("0.0.0.0", ANNOUNCE_PORT))
        end = time.monotonic() + timeout
        while (left := end - time.monotonic()) > 0:
            sock.settimeout(left)
            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                break
            try:
                session = json.loads(data)
                port = int(session.get("linkPort", -1))
            except (ValueError, TypeError, AttributeError):
                continue
            if session.get("sessionID") and port > 0:
                return port, session.get("sessionName") or session["sessionID"]
    finally:
        sock.close()
    raise LinkError(f"no ResoniteLink session announced within {timeout:.0f} s: enable ResoniteLink in the "
                    "session (Session tab), or pass --port")


async def connect(port):
    rl = client.Client()
    await rl.connect(port)
    return rl


async def find_user(rl, name=None):
    """The user root slot (a direct child of the world root called "User <name> ..."): the one matching name, or
    the only one. (Session data doesn't say which user is the one running ResoniteLink.)"""
    root = _check(await rl.get_slot("Root", depth=1), "get Root")
    users = [c for c in root.data.children if c.name and (c.name.value or "").startswith("User ")]
    if name:
        users = [u for u in users if name.lower() in u.name.value.lower()]
    if len(users) != 1:
        found = ", ".join(u.name.value for u in users) or "none"
        raise LinkError(f"need exactly one user slot{f' matching {name!r}' if name else ''}; found: {found}. "
                        "Pass --user <part of your name>.")
    return users[0]


async def find_avatar(rl, user_slot_id):
    """The avatar slot under a user root (the child with an AvatarRoot component), or None."""
    d = _check(await rl.get_slot(user_slot_id, depth=1), "get user root")
    for child in d.data.children:
        cd = _check(await rl.get_slot(child.id, depth=0, includeComponentData=False), "get child")
        if any((c.componentType or "").endswith("AvatarRoot") for c in cd.data.components or []):
            return child
    return None
