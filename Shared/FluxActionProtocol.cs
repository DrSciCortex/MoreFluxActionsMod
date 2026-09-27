// SPDX-FileCopyrightText: 2026 DrSciCortex
//
// SPDX-License-Identifier: MIT

#nullable disable

using System;
using System.Globalization;

namespace MoreFluxActions.Shared
{
    /// <summary>
    /// What the two halves agree on. Resonite reads SteamVR input in its renderer process, so the renderer plugin adds
    /// the FluxAction1..<see cref="Count"/> actions to SteamVR's manifest, reads them, and sends every change to the
    /// engine plugin over InterprocessLib: one int per change (<see cref="Encode"/>). The engine plugin turns them
    /// into ProtoFlux dynamic impulses under the local user.
    /// </summary>
    internal static class FluxActionProtocol
    {
        public const int Count = 42;

        public const string ActionSet = "/actions/FluxActions";

        public static string ActionPath(int action)
        {
            return ActionSet + "/in/FluxAction" + action;
        }

        /// <summary>The dynamic impulse tags: <c>FluxAction7.Pressed</c>, <c>FluxAction7.Released</c>, and
        /// <c>FluxAction7</c> carrying the new state as a bool.</summary>
        public static string ImpulseTag(int action)
        {
            return "FluxAction" + action;
        }

        public const string EventMessageId = "FluxAction";

        public static int Encode(int action, bool pressed)
        {
            return (action << 1) | (pressed ? 1 : 0);
        }

        public static void Decode(int code, out int action, out bool pressed)
        {
            action = code >> 1;
            pressed = (code & 1) != 0;
        }

        /// <summary>Other programs on this PC (the CyberFinger bridge) fire FluxActions without SteamVR: one UDP
        /// datagram to 127.0.0.1:<see cref="UdpPort"/> per change, naming the impulse, <c>FluxAction42.Pressed</c> or
        /// <c>FluxAction42.Released</c> (ASCII). The engine half listens.</summary>
        public const int UdpPort = 42042;

        public static bool TryParseDatagram(string text, out int action, out bool pressed)
        {
            action = 0;
            pressed = false;
            const string prefix = "FluxAction";
            if (text == null || !text.StartsWith(prefix, StringComparison.Ordinal))
                return false;
            int dot = text.IndexOf('.', prefix.Length);
            if (dot < 0)
                return false;
            string change = text.Substring(dot + 1);
            if (change == "Pressed")
                pressed = true;
            else if (change != "Released")
                return false;
            return int.TryParse(text.Substring(prefix.Length, dot - prefix.Length), NumberStyles.None,
                                CultureInfo.InvariantCulture, out action) && action >= 1 && action <= Count;
        }

        // The queue, scoped so two Resonite instances on one machine don't cross (QueueScope).
        private const string BaseName = "MoreFluxActions.v1";
        public static readonly string OwnerId = QueueScope.Scoped(BaseName);
        public static readonly string QueueName = QueueScope.Scoped(BaseName);
    }
}
