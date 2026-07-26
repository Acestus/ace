---
title: Chart Demo
date: 2026-07-19
description: Static and API-backed chart examples.
draft: false
---

This page proves the lazy Chart.js loader.

## Static JSON chart

{{< chart source="/data/sample-chart.json" title="Weekly note count" caption="Static JSON loaded from the site." height="280px" >}}

## Mock API chart

{{< chart source="/api/sample-chart.json" title="API-backed page count" caption="Mock API payload loaded at runtime." height="280px" >}}
