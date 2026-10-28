---
name: ulm-pin
description: Pin a critical architectural decision, schema definition, or user preference into ULM (Universal Local Memory).
tools:
  - "ulm-memory/ulm_pin_fact"
---

Pin the following fact into ULM (Universal Local Memory):
Category: ${input:category:Enter category e.g. system_architecture, user_preference, agent_config}
Fact Content: ${input:fact:Enter the golden fact content to pin into ULM}

Execute `ulm_pin_fact` with these parameters and confirm persistence.

