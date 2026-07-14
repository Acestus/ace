// Thin fetch wrapper over the Ace CRM Functions API.
// Kept dependency-free (no bundler, no framework) per the vanilla/modular front-end goal.

const API_BASE = window.ACE_CRM_API_BASE ?? "http://localhost:7071/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  if (!response.ok) {
    const body = await safeJson(response);
    const message = body?.errors?.join(" ") ?? `Request to ${path} failed with ${response.status}`;
    throw new ApiError(message, response.status, body?.errors ?? []);
  }

  if (response.status === 204) {
    return null;
  }

  return safeJson(response);
}

async function safeJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export class ApiError extends Error {
  constructor(message, status, errors) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errors = errors;
  }
}

export const crmApi = {
  listCompanies: () => request("/companies"),
  createCompany: (payload) =>
    request("/companies", { method: "POST", body: JSON.stringify(payload) }),

  listContacts: (companyId) =>
    request(companyId ? `/contacts?companyId=${encodeURIComponent(companyId)}` : "/contacts"),
  createContact: (payload) =>
    request("/contacts", { method: "POST", body: JSON.stringify(payload) }),

  listInteractions: (contactId) => request(`/contacts/${encodeURIComponent(contactId)}/interactions`),
  createInteraction: (contactId, payload) =>
    request(`/contacts/${encodeURIComponent(contactId)}/interactions`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
