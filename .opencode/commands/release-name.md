---
name: release-naming
description: Generate two-word app release names based on space phenomena. Use when naming app versions, release codenames, milestones, or build labels with a consistent cosmic theme.
---

# Release Naming Skill

## Purpose
This skill creates short, memorable release names for app versions. Every name must be exactly two words and must be inspired by space phenomena.

## Naming rules
- Use exactly two words.
- Both words must relate to space, astronomy, or visible cosmic phenomena.
- Prefer names that feel natural, readable, and easy to say.
- Avoid numbers, punctuation, and extra modifiers.
- Avoid names that are overly technical, obscure, or hard to pronounce.
- Avoid repeating the same first word across nearby releases unless a naming sequence is intentional.

## Good patterns
- Phenomenon + noun.
- Noun + phenomenon.
- Adjective + phenomenon.

## Examples
- Aurora Borealis
- Solar Flare
- Lunar Eclipse
- Meteor Shower
- Cosmic Ray
- Nebula Drift

## Output format
When asked for a release name:
1. Provide one or more options.
2. Keep every option to exactly two words.
3. Do not explain the names unless requested.
4. If a sequence is needed, keep the style consistent across all releases.

## Quality checks
Before responding, verify that:
- The name has exactly two words.
- The words clearly fit the space theme.
- The result sounds like a release codename, not a product title.
- The name is unique enough to avoid confusion with common app terms.

## Edge cases
- If the user asks for a “theme,” generate a family of matching two-word names.
- If the user asks for “more elegant” names, prefer poetic phenomena like Aurora, Eclipse, Halo, or Nebula.
- If the user asks for “more technical” names, prefer terms like Pulsar, Quasar, Orbit, or Spectrum.
