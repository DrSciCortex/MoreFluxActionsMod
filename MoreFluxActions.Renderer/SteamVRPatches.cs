// SPDX-FileCopyrightText: 2026 DrSciCortex
//
// SPDX-License-Identifier: MIT

using System;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using BepInEx;
using HarmonyLib;
using MoreFluxActions.Shared;
using Valve.Newtonsoft.Json.Linq;
using Valve.VR;

namespace MoreFluxActions.Renderer
{
    /// <summary>
    /// Only the native call is redirected: SteamVR loads the extended manifest, while Valve's Unity plugin keeps reading
    /// Resonite's own (its generated action classes know nothing of the FluxActions, and don't need to).
    /// </summary>
    [HarmonyPatch(typeof(CVRInput), nameof(CVRInput.SetActionManifestPath))]
    internal static class SetActionManifestPathPatch
    {
        private static void Prefix(ref string __0)
        {
            try
            {
                __0 = ActionManifest.Extend(__0);
            }
            catch (Exception e)
            {
                RendererPlugin.Log.LogError($"Could not extend SteamVR's action manifest, FluxActions are off: {e}");
            }
        }
    }

    /// <summary>
    /// Resonite activates only the action set of the controller it recognised. The FluxActions set is added to every
    /// update, so SteamVR delivers it whatever the controller, and read right after.
    /// </summary>
    [HarmonyPatch(typeof(CVRInput), nameof(CVRInput.UpdateActionState))]
    internal static class UpdateActionStatePatch
    {
        private static void Prefix(CVRInput __instance, ref VRActiveActionSet_t[] __0)
        {
            FluxActionInput.AddSet(__instance, ref __0);
        }

        private static void Postfix(CVRInput __instance, EVRInputError __result)
        {
            if (__result == EVRInputError.None)
                FluxActionInput.Read(__instance);
        }
    }

    /// <summary>Resonite's action manifest plus the FluxActions set, written to BepInEx's config folder.</summary>
    internal static class ActionManifest
    {
        internal static bool Extended { get; private set; }
        private static string s_path;

        internal static string Extend(string original)
        {
            if (s_path != null)
                return s_path;
            string dir = Path.Combine(Paths.ConfigPath, "MoreFluxActions");
            Directory.CreateDirectory(dir);
            JObject manifest = JObject.Parse(File.ReadAllText(original));

            JArray sets = Array(manifest, "action_sets");
            if (!Has(sets, FluxActionProtocol.ActionSet))
                sets.Add(new JObject { ["name"] = FluxActionProtocol.ActionSet, ["usage"] = "single" });
            JArray actions = Array(manifest, "actions");
            for (int a = 1; a <= FluxActionProtocol.Count; a++)
            {
                string name = FluxActionProtocol.ActionPath(a);
                if (!Has(actions, name))
                    actions.Add(new JObject { ["name"] = name, ["type"] = "boolean", ["requirement"] = "optional" });
            }

            // Their names in SteamVR's binding UI.
            JArray localization = Array(manifest, "localization");
            JObject english = localization.OfType<JObject>().FirstOrDefault(
                l => string.Equals((string)l["language_tag"], "en_US", StringComparison.OrdinalIgnoreCase));
            if (english == null)
            {
                english = new JObject { ["language_tag"] = "en_US" };
                localization.Add(english);
            }
            english[FluxActionProtocol.ActionSet] = "Flux Actions (ProtoFlux on your avatar)";
            for (int a = 1; a <= FluxActionProtocol.Count; a++)
                english[FluxActionProtocol.ActionPath(a)] = "Flux Action " + a;

            // SteamVR resolves the default bindings next to the manifest: take Resonite's along.
            string sourceDir = Path.GetDirectoryName(original);
            if (manifest["default_bindings"] is JArray bindings)
                foreach (JObject binding in bindings.OfType<JObject>())
                {
                    string url = (string)binding["binding_url"];
                    if (string.IsNullOrEmpty(url) || Path.IsPathRooted(url))
                        continue;
                    string source = Path.Combine(sourceDir, url), target = Path.Combine(dir, url);
                    if (!File.Exists(source))
                        continue;
                    Directory.CreateDirectory(Path.GetDirectoryName(target));
                    File.Copy(source, target, true);
                }

            string path = Path.Combine(dir, "actions.json");
            File.WriteAllText(path, manifest.ToString());
            s_path = path;
            Extended = true;
            RendererPlugin.Log.LogInfo($"SteamVR gets FluxAction1..{FluxActionProtocol.Count}: {path} (from {original})");
            return path;
        }

        private static JArray Array(JObject manifest, string key)
        {
            if (!(manifest[key] is JArray array))
            {
                array = new JArray();
                manifest[key] = array;
            }
            return array;
        }

        private static bool Has(JArray array, string name)
        {
            return array.OfType<JObject>().Any(
                o => string.Equals((string)o["name"], name, StringComparison.OrdinalIgnoreCase));
        }
    }

    /// <summary>The FluxActions' handles, their set added to each update, their states read after it.</summary>
    internal static class FluxActionInput
    {
        private static readonly ulong[] s_actions = new ulong[FluxActionProtocol.Count + 1];
        private static readonly bool[] s_state = new bool[FluxActionProtocol.Count + 1];
        private static readonly uint s_dataSize = (uint)Marshal.SizeOf(typeof(InputDigitalActionData_t));
        private static ulong s_set;
        private static bool s_tried, s_ready, s_loggedRead;
        private static VRActiveActionSet_t[] s_buffer = new VRActiveActionSet_t[0];

        private static bool Ready(CVRInput input)
        {
            if (s_ready || s_tried)
                return s_ready;
            s_tried = true;
            if (!ActionManifest.Extended)
            {
                RendererPlugin.Log.LogWarning("SteamVR's action manifest wasn't extended: FluxActions are off");
                return false;
            }
            EVRInputError err = input.GetActionSetHandle(FluxActionProtocol.ActionSet, ref s_set);
            if (err != EVRInputError.None || s_set == 0)
            {
                RendererPlugin.Log.LogWarning($"No FluxActions action set in SteamVR ({err}): FluxActions are off");
                return false;
            }
            for (int a = 1; a <= FluxActionProtocol.Count; a++)
            {
                err = input.GetActionHandle(FluxActionProtocol.ActionPath(a), ref s_actions[a]);
                if (err != EVRInputError.None)
                {
                    RendererPlugin.Log.LogWarning($"No handle for {FluxActionProtocol.ActionPath(a)} ({err}): FluxActions are off");
                    return false;
                }
            }
            s_ready = true;
            return true;
        }

        internal static void AddSet(CVRInput input, ref VRActiveActionSet_t[] sets)
        {
            if (sets == null || !Ready(input))
                return;
            int n = sets.Length;
            for (int i = 0; i < n; i++)
                if (sets[i].ulActionSet == s_set)
                    return;
            // Copied every frame: Valve's plugin reuses its arrays and rewrites them in place.
            if (s_buffer.Length != n + 1)
                s_buffer = new VRActiveActionSet_t[n + 1];
            System.Array.Copy(sets, s_buffer, n);
            s_buffer[n] = new VRActiveActionSet_t
            {
                ulActionSet = s_set,
                ulRestrictedToDevice = OpenVR.k_ulInvalidInputValueHandle,
                nPriority = 0,
            };
            sets = s_buffer;
        }

        internal static void Read(CVRInput input)
        {
            if (!s_ready)
                return;
            if (!s_loggedRead)
            {
                s_loggedRead = true;
                RendererPlugin.Log.LogInfo($"Reading FluxAction1..{FluxActionProtocol.Count} from SteamVR");
            }
            var data = new InputDigitalActionData_t();
            for (int a = 1; a <= FluxActionProtocol.Count; a++)
            {
                if (input.GetDigitalActionData(s_actions[a], ref data, s_dataSize, OpenVR.k_ulInvalidInputValueHandle)
                    != EVRInputError.None)
                    continue;
                if (data.bState == s_state[a])
                    continue;
                s_state[a] = data.bState;
                RendererPlugin.Send(FluxActionProtocol.Encode(a, data.bState));
            }
        }
    }
}
