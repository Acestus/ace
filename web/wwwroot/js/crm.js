import { crmApi, ApiError } from "./apiClient.js";

const companiesList = document.getElementById("companies-list");
const contactsList = document.getElementById("contacts-list");
const newCompanyForm = document.getElementById("new-company-form");
const newCompanyStatus = document.getElementById("new-company-status");

async function refreshCompanies() {
  const companies = await crmApi.listCompanies();
  companiesList.replaceChildren(
    ...companies.map((company) => {
      const li = document.createElement("li");
      li.textContent = company.website ? `${company.name} — ${company.website}` : company.name;
      return li;
    })
  );
}

async function refreshContacts() {
  const contacts = await crmApi.listContacts();
  contactsList.replaceChildren(
    ...contacts.map((contact) => {
      const li = document.createElement("li");
      const name = [contact.firstName, contact.lastName].filter(Boolean).join(" ") || "(no name)";
      li.textContent = contact.email ? `${name} — ${contact.email}` : name;
      return li;
    })
  );
}

newCompanyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(newCompanyForm);
  const name = formData.get("name")?.toString().trim();
  const website = formData.get("website")?.toString().trim() || null;

  newCompanyStatus.textContent = "Saving…";

  try {
    await crmApi.createCompany({ name, website, industry: null, notes: null });
    newCompanyStatus.textContent = `Added "${name}".`;
    newCompanyForm.reset();
    await refreshCompanies();
  } catch (error) {
    newCompanyStatus.textContent =
      error instanceof ApiError ? `Could not add company: ${error.message}` : "Could not add company.";
  }
});

async function init() {
  try {
    await Promise.all([refreshCompanies(), refreshContacts()]);
  } catch (error) {
    console.error("Failed to load CRM data", error);
  }
}

init();
