# Changelog

## 0.1.0

- FluxAction1–42 in Resonite's SteamVR bindings (an extended action manifest, read by the renderer half).
- Each press and release fires ProtoFlux dynamic impulses under your user: `FluxActionN.Pressed`,
  `FluxActionN.Released`, and `FluxActionN` with a bool.
- Other programs on the PC fire them too: UDP datagrams to `127.0.0.1:42042` (`FluxAction42.Pressed`, `.Released`).
- Test rigs built live over ResoniteLink (`tools/`): a FluxAction console, a Dev Tool on FluxAction1, fly/walk on
  FluxAction2, and showing or hiding parts of your avatar.
- Icon, adapted from the Resonite logo (CC BY-SA 4.0).
- Licences: MIT; `Shared/QueueScope.cs` and `ThunderstoreRefs.targets`, adapted from DesktopBuddy, AGPL-3.0-only;
  the icon CC BY-SA 4.0.
