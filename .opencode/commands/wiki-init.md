---
description: Scaffold the wiki/ directory for this project from the OpenWiki templates
agent: build
---
Call the `openwiki_init` tool now to scaffold this project's wiki. If the
project has an obvious name (from the directory name, package.json, or
similar), pass it as `projectName`; otherwise omit it and let the tool default
to the directory name.

Report back the tool's result, and if `wiki/` already existed, say so instead
of implying you just created it from scratch.
