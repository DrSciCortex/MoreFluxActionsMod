// SPDX-FileCopyrightText: 2026 DrSciCortex
//
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using InterprocessLib;
using MoreFluxActions.Shared;
using UnityEngine;

namespace MoreFluxActions.Renderer
{
    /// <summary>
    /// The renderer half. Resonite reads SteamVR input here, in its Unity renderer, and passes it to the engine only as
    /// fixed per-controller states. So this plugin gives SteamVR an extended action manifest with FluxAction1..42
    /// (they show up in SteamVR's binding UI for Resonite, for any controller), keeps their action set active, reads
    /// them every frame (SteamVRPatches.cs) and sends each change to the engine half over InterprocessLib.
    /// </summary>
    [BepInPlugin(Guid, "MoreFluxActions.Renderer", Version)]
    public class RendererPlugin : BaseUnityPlugin
    {
        public const string Guid = "com.drscicortex.morefluxactions.renderer";
        public const string Version = "0.1.0";

        internal static ManualLogSource Log;

        private const float ConnectRetrySeconds = 2f;
        private const int MaxPending = 256;

        // Main thread only: SteamVR is updated from Unity's frame loop, and so is this plugin.
        private static Messenger s_messenger;
        private static readonly Queue<int> s_pending = new Queue<int>();
        private float _connectRetry;
        private bool _loggedWaiting;

        private void Awake()
        {
            Log = Logger;
            new Harmony(Guid).PatchAll(typeof(RendererPlugin).Assembly);
            Log.LogInfo($"MoreFluxActions renderer half {Version}: FluxAction1..{FluxActionProtocol.Count} for SteamVR");
        }

        private void Update()
        {
            TryConnect();
            while (s_messenger != null && s_pending.Count > 0)
                Send(s_pending.Dequeue());
        }

        /// <summary>A FluxAction changed (SteamVRPatches): to the engine now, or once the queue is up.</summary>
        internal static void Send(int code)
        {
            if (s_messenger == null)
            {
                if (s_pending.Count >= MaxPending)
                    s_pending.Dequeue();
                s_pending.Enqueue(code);
                return;
            }
            try
            {
                s_messenger.SendValue(FluxActionProtocol.EventMessageId, code);
            }
            catch (Exception e)
            {
                Log.LogWarning($"Could not send a FluxAction to the engine: {e.Message}");
            }
        }

        // The engine half creates the queue once the engine is up; until then, retry.
        private void TryConnect()
        {
            if (s_messenger != null)
                return;
            _connectRetry -= Time.unscaledDeltaTime;
            if (_connectRetry > 0f)
                return;
            _connectRetry = ConnectRetrySeconds;
            try
            {
                Messenger.OnWarning += OnWarning;
                Messenger.OnFailure += OnFailure;
                s_messenger = new Messenger(FluxActionProtocol.OwnerId, false, FluxActionProtocol.QueueName,
                                            SimpleMemoryPackerPool.Instance);
                Log.LogInfo($"Connected to the engine half (queue {FluxActionProtocol.QueueName})");
            }
            catch (Exception e)
            {
                Messenger.OnWarning -= OnWarning;
                Messenger.OnFailure -= OnFailure;
                s_messenger = null;
                if (!_loggedWaiting)
                {
                    _loggedWaiting = true;
                    Log.LogInfo($"Waiting for the engine half's queue {FluxActionProtocol.QueueName} ({e.GetType().Name})");
                }
            }
        }

        private static void OnWarning(string message) => Log.LogWarning($"[InterprocessLib] {message}");

        private static void OnFailure(Exception e) => Log.LogError($"[InterprocessLib] {e}");
    }
}
