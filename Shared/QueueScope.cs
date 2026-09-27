// SPDX-FileCopyrightText: 2026 DevL0rd (DesktopBuddy, https://github.com/DevL0rd/DesktopBuddy)
// SPDX-FileCopyrightText: 2026 DrSciCortex
//
// SPDX-License-Identifier: AGPL-3.0-only
//
// Adapted from DesktopBuddy's Shared/SharedTextureBridgeProtocol.cs (AGPL-3.0): the scoping of an InterprocessLib
// queue by the -shmprefix Resonite starts both of its processes with, and the unpooled IMemoryPackerEntityPool.
// Licensed AGPL-3.0-only like its source; the rest of MoreFluxActions is MIT (README.md, Licences).

#nullable disable

using System;
using Renderite.Shared;

namespace MoreFluxActions.Shared
{
    /// <summary>InterprocessLib wants a pool for message objects; plain values need none, so nothing is pooled.</summary>
    internal sealed class SimpleMemoryPackerPool : IMemoryPackerEntityPool
    {
        public static readonly SimpleMemoryPackerPool Instance = new SimpleMemoryPackerPool();

        private SimpleMemoryPackerPool()
        {
        }

        T IMemoryPackerEntityPool.Borrow<T>() => new T();

        void IMemoryPackerEntityPool.Return<T>(T value)
        {
        }
    }

    /// <summary>
    /// Queue names scoped by the -shmprefix both of Resonite's processes are started with, so two Resonite instances
    /// on one machine don't cross.
    /// </summary>
    internal static class QueueScope
    {
        private static readonly string Scope = GetScope();

        public static string Scoped(string name)
        {
            return string.IsNullOrEmpty(Scope) ? name : name + "." + Scope;
        }

        private static string GetScope()
        {
            string prefix = GetArgument("-shmprefix") ?? GetArgument("--shmprefix");
            return string.IsNullOrWhiteSpace(prefix) ? string.Empty : "shm" + StableHash(prefix).ToString("X16");
        }

        private static string GetArgument(string name)
        {
            string[] args;
            try
            {
                args = Environment.GetCommandLineArgs();
            }
            catch
            {
                return null;
            }
            for (int i = 0; i < args.Length; i++)
            {
                string arg = args[i];
                if (arg == null)
                    continue;
                if (string.Equals(arg, name, StringComparison.OrdinalIgnoreCase))
                    return i + 1 < args.Length ? args[i + 1] : null;
                if (arg.StartsWith(name + "=", StringComparison.OrdinalIgnoreCase))
                    return arg.Substring(name.Length + 1);
            }
            return null;
        }

        private static ulong StableHash(string value)
        {
            unchecked
            {
                ulong hash = 14695981039346656037UL;          // FNV-1a
                for (int i = 0; i < value.Length; i++)
                {
                    hash ^= value[i];
                    hash *= 1099511628211UL;
                }
                return hash;
            }
        }
    }
}
