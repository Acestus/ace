---
title: Naming Azure Resources with the Cloud Adoption Framework
date: 2026-08-05
description: A short reference pattern for applying Microsoft Cloud Adoption Framework naming guidance to Azure resources.
draft: false
---

## Question

How should I use the Microsoft Cloud Adoption Framework to name Azure resources in a way that is consistent, readable, and useful later when the environment grows? The short answer is to treat naming as an operating convention, not as decoration. A good resource name should tell me what the resource is, what workload it belongs to, which environment it supports, where it lives, and which instance it is when there is more than one.

## Recommended Pattern

My default pattern is: `<resource-abbreviation>-<workload>-<environment>-<region>-<instance>`. For example, an Azure Resource Group for a production API in Central US could be `rg-orders-prod-cus-001`, and the matching App Service Plan could be `asp-orders-prod-cus-001`. This follows the spirit of the Cloud Adoption Framework because the name starts with the resource type, keeps stable business context in the middle, and avoids details that should live in tags instead of names.

## Why This Works

This naming format helps with search, troubleshooting, cost review, and automation. When I look at `kv-orders-prod-cus-001`, I can quickly tell that it is a Key Vault for the orders workload in production, deployed to Central US, and it is the first instance. That same structure also works well in Bicep because names can be assembled from parameters like `workloadName`, `environmentName`, `locationCode`, and `instanceNumber` instead of being hand-typed differently in every deployment.

## Example

For a small application named `orders`, I might use `rg-orders-dev-cus-001` for the resource group, `app-orders-dev-cus-001` for the App Service, `stordersdevcus001` for the storage account, and `ai-orders-dev-cus-001` for Application Insights. Storage accounts are the important exception because Azure requires globally unique, lowercase alphanumeric names, so the same naming logic has to be compressed. The convention still matters even when the exact separators change.

## Reference Use

I use this article as a lightweight reference for future Hugo posts and short YouTube videos: start with the question, give the rule, explain why it works, then show real names. For the two-to-four minute video version, the flow is simple: introduce the problem of messy Azure names, show the CAF-inspired pattern, build three or four example names, then close by saying that tags should carry changeable metadata like owner, cost center, data classification, and lifecycle. Microsoft has more detail in the Cloud Adoption Framework pages for [resource naming](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-naming), [resource abbreviations](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-abbreviations), and [tagging strategy](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-tagging).
