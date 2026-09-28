// SPDX-FileCopyrightText: 2026 DrSciCortex
//
// SPDX-License-Identifier: MIT

using System.Net;
using System.Net.Sockets;
using System.Text;
using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using BepInEx.NET.Common;
using BepInExResoniteShim;
using BepisResoniteWrapper;
using FrooxEngine;
using FrooxEngine.ProtoFlux;
using InterprocessLib;
using MoreFluxActions.Shared;
using Renderite.Shared;

namespace MoreFluxActions;

/// <summary>
/// The engine half. The renderer half (MoreFluxActions.Renderer) reads SteamVR's FluxAction1..42 and sends each
/// press and release here; this fires them as ProtoFlux dynamic impulses into the local user's hierarchy in the
/// focused world, so receivers anywhere under your avatar react:
///   <c>FluxAction7.Pressed</c>, <c>FluxAction7.Released</c>   (Dynamic Impulse Receiver)
///   <c>FluxAction7</c> with a bool: true on press, false on release   (Dynamic Impulse Receiver With Value&lt;bool&gt;)
/// Impulses run on this client only, like any dynamic impulse: what the flux writes syncs as usual.
/// Other programs on this PC fire them too, without SteamVR: see <see cref="FluxActionProtocol.UdpPort"/>.
/// </summary>
[ResonitePlugin(PluginMetadata.GUID, PluginMetadata.NAME, PluginMetadata.VERSION, PluginMetadata.AUTHORS, PluginMetadata.REPOSITORY_URL)]
[BepInDependency(BepInExResoniteShim.PluginMetadata.GUID, BepInDependency.DependencyFlags.HardDependency)]
public class Plugin : BasePlugin
{
    internal static new ManualLogSource Log = null!;

    private Messenger? _messenger;
    private UdpClient? _udp;
    private readonly bool[] _logged = new bool[FluxActionProtocol.Count + 1];
    private ConfigEntry<int> _muteAction = null!;

    public override void Load()
    {
        Log = base.Log;
        // Resonite has no mute action for SteamVR, and ProtoFlux can't mute you (voice mode is read-only to it; the
        // dash's mute lives in Userspace), so a FluxAction can be Resonite's mute here.
        // 42 by default: FluxAction42 is the CyberFinger's right pink button (the CyberFinger bindings leave it for
        // that), so the glove's mute button works out of the box.
        _muteAction = Config.Bind("Mute", "MuteToggleAction", 42,
            "A FluxAction (1-42) whose press also toggles your microphone mute in Resonite, like the dash's mute " +
            "button (its impulses still fire). 0: none. 42 (the default) is the CyberFinger's right pink button, " +
            "with the CyberFinger bridge's right pink on SteamVR.");
        ResoniteHooks.OnEngineReady += OnEngineReady;
        Log.LogInfo($"Plugin {PluginMetadata.GUID} is loaded!");
    }

    private void OnEngineReady()
    {
        // The engine owns the queue; the renderer half connects to it once it exists.
        Messenger.OnWarning += message => Log.LogWarning($"[InterprocessLib] {message}");
        Messenger.OnFailure += ex => Log.LogError($"[InterprocessLib] {ex}");
        _messenger = new Messenger(FluxActionProtocol.OwnerId, true, FluxActionProtocol.QueueName,
                                   SimpleMemoryPackerPool.Instance);
        _messenger.ReceiveValue<int>(FluxActionProtocol.EventMessageId, OnFluxAction);
        Log.LogInfo($"Listening for FluxAction1..{FluxActionProtocol.Count} from the renderer " +
                    $"(queue {FluxActionProtocol.QueueName})");
        StartUdp();
    }

    private void OnFluxAction(int code)
    {
        FluxActionProtocol.Decode(code, out int action, out bool pressed);
        Dispatch(action, pressed);
    }

    // Loopback only: programs on this PC, such as the CyberFinger bridge (its right pink button, when set to a
    // FluxAction).
    private void StartUdp()
    {
        try
        {
            _udp = new UdpClient(new IPEndPoint(IPAddress.Loopback, FluxActionProtocol.UdpPort));
        }
        catch (SocketException ex)
        {
            Log.LogWarning($"No FluxActions from other programs: port {FluxActionProtocol.UdpPort} is taken " +
                           $"({ex.SocketErrorCode})");
            return;
        }
        new Thread(ReceiveUdp) { IsBackground = true, Name = "MoreFluxActions UDP" }.Start();
        Log.LogInfo($"Listening for FluxActions from other programs on 127.0.0.1:{FluxActionProtocol.UdpPort}");
    }

    private void ReceiveUdp()
    {
        var from = new IPEndPoint(IPAddress.Any, 0);
        while (true)
        {
            byte[] data;
            try
            {
                data = _udp!.Receive(ref from);
            }
            catch (SocketException ex)
            {
                Log.LogWarning($"Stopped listening for FluxActions from other programs: {ex.SocketErrorCode}");
                return;
            }
            catch (ObjectDisposedException)
            {
                return;
            }
            if (FluxActionProtocol.TryParseDatagram(Encoding.ASCII.GetString(data), out int action, out bool pressed))
                Dispatch(action, pressed);
        }
    }

    // InterprocessLib's thread or the UDP one: hand over to the focused world's update.
    private void Dispatch(int action, bool pressed)
    {
        if (action < 1 || action > FluxActionProtocol.Count)
            return;
        World? world = Engine.Current?.WorldManager?.FocusedWorld;
        if (world == null)
            return;
        world.RunSynchronously(() => Fire(world, action, pressed));
    }

    private void Fire(World world, int action, bool pressed)
    {
        Slot? root = world.LocalUser?.Root?.Slot;
        IDynamicImpulseHandler? handler = ProtoFluxHelper.DynamicImpulseHandler;
        if (root == null || handler == null)
            return;
        string tag = FluxActionProtocol.ImpulseTag(action);
        if (pressed && action == _muteAction.Value)
        {
            AudioSystem audio = world.Engine.AudioSystem;
            audio.IsMuted = !audio.IsMuted;
            Log.LogInfo($"{tag}: {(audio.IsMuted ? "muted" : "unmuted")} (MuteToggleAction)");
        }
        int receivers = handler.TriggerDynamicImpulse(root, tag + (pressed ? ".Pressed" : ".Released"), true);
        receivers += handler.TriggerDynamicImpulseWithArgument(root, tag, true, pressed);
        if (!_logged[action])
        {
            _logged[action] = true;
            Log.LogInfo($"{tag} {(pressed ? "pressed" : "released")}: {receivers} receiver(s) under {root.Name} " +
                        $"in {world.Name}");
        }
    }
}
