const GSI_URL = "https://accounts.google.com/gsi/client";
const GAPI_URL = "https://apis.google.com/js/api.js";
const SCOPES = [
  "https://www.googleapis.com/auth/calendar.events",
  "https://www.googleapis.com/auth/calendar.readonly",
].join(" ");
const DISCOVERY_DOCS = ["https://www.googleapis.com/discovery/v1/apis/calendar/v3/rest"];
const TIME_ZONE = Intl.DateTimeFormat().resolvedOptions().timeZone;

let loadPromise = null;
let currentConfig = null;
let tokenClient = null;
let accessToken = null;

function ensureWindow() {
  if (typeof window === "undefined") {
    throw new Error("Google APIs require a browser environment");
  }
}

function loadScriptOnce(src) {
  return new Promise((resolve, reject) => {
    ensureWindow();
    const existing = document.querySelector(`script[src="${src}"]`);
    if (existing) {
      if (existing.dataset.loaded === "true") {
        resolve();
        return;
      }
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener(
        "error",
        () => reject(new Error(`Failed to load ${src}`)),
        { once: true }
      );
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.defer = true;
    script.onload = () => {
      script.dataset.loaded = "true";
      resolve();
    };
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(script);
  });
}

async function ensureGsiLoaded() {
  ensureWindow();
  if (window.google && window.google.accounts && window.google.accounts.oauth2) {
    return;
  }
  await loadScriptOnce(GSI_URL);
}

async function ensureGapiLoaded() {
  ensureWindow();
  if (window.gapi && window.gapi.client) {
    return;
  }
  await loadScriptOnce(GAPI_URL);
}

async function initializeClient(apiKey, clientId) {
  await ensureGsiLoaded();
  await ensureGapiLoaded();
  await new Promise((resolve, reject) => {
    window.gapi.load("client", {
      callback: resolve,
      onerror: () => reject(new Error("Failed to load Google API client")),
    });
  });
  await window.gapi.client.init({
    apiKey,
    discoveryDocs: DISCOVERY_DOCS,
  });
  tokenClient = window.google.accounts.oauth2.initTokenClient({
    client_id: clientId,
    scope: SCOPES,
    callback: () => {},
  });
  currentConfig = { apiKey, clientId };
}

export async function loadGoogle({ apiKey, clientId }) {
  if (!apiKey || !clientId) {
    throw new Error("Google API Key and OAuth Client ID are required");
  }

  if (
    !loadPromise ||
    !currentConfig ||
    currentConfig.apiKey !== apiKey ||
    currentConfig.clientId !== clientId
  ) {
    loadPromise = initializeClient(apiKey, clientId).catch((error) => {
      loadPromise = null;
      throw error;
    });
  }

  await loadPromise;
  return true;
}

export function getCurrentToken() {
  return accessToken;
}

function ensureInitialized() {
  if (!window.gapi || !window.gapi.client) {
    throw new Error("Google API client is not ready");
  }
  if (!tokenClient) {
    throw new Error("Google OAuth client is not ready");
  }
}

export async function signIn({ prompt } = {}, scopes = SCOPES) {
  ensureWindow();
  await loadPromise;
  ensureInitialized();

  return new Promise((resolve, reject) => {
    tokenClient.callback = (response) => {
      if (response.error) {
        reject(new Error(response.error_description || "Authorization failed"));
        return;
      }
      accessToken = response.access_token;
      window.gapi.client.setToken({ access_token: accessToken });
      resolve(accessToken);
    };
    try {
      tokenClient.requestAccessToken({
        prompt: prompt !== undefined ? prompt : accessToken ? "" : "consent",
        scope: scopes,
      });
    } catch (error) {
      reject(error);
    }
  });
}

export function signOut() {
  ensureWindow();
  if (!accessToken) {
    return;
  }
  try {
    const token = accessToken;
    window.google.accounts.oauth2.revoke(token, () => {});
  } catch (error) {
    console.warn("Failed to revoke Google token", error);
  }
  accessToken = null;
  if (window.gapi && window.gapi.client) {
    window.gapi.client.setToken(null);
  }
}

function requireAuth() {
  if (!accessToken) {
    throw new Error("You need to connect to Google Calendar first");
  }
}

function extractError(error) {
  if (!error) return "Unknown Google API error";
  if (typeof error === "string") return error;
  if (error.result && error.result.error) {
    return error.result.error.message || "Google API error";
  }
  if (error.message) return error.message;
  return "Unknown Google API error";
}

export async function listMonthEvents({ timeMin, timeMax, calendarId = "primary" }) {
  await loadPromise;
  ensureInitialized();
  requireAuth();

  try {
    const response = await window.gapi.client.calendar.events.list({
      calendarId,
      singleEvents: true,
      orderBy: "startTime",
      timeMin,
      timeMax,
      maxResults: 2500,
      showDeleted: false,
    });
    return response.result.items || [];
  } catch (error) {
    throw new Error(extractError(error));
  }
}

export async function insertEvent({ summary, description, startISO, endISO, reminders, colorId, calendarId = "primary" }) {
  await loadPromise;
  ensureInitialized();
  requireAuth();

  try {
    const response = await window.gapi.client.calendar.events.insert({
      calendarId,
      resource: {
        summary,
        description,
        start: {
          dateTime: startISO,
          timeZone: TIME_ZONE,
        },
        end: {
          dateTime: endISO,
          timeZone: TIME_ZONE,
        },
        ...(colorId ? { colorId } : {}),
        reminders: reminders && reminders.length
          ? { useDefault: false, overrides: reminders }
          : undefined,
      },
    });
    return response.result;
  } catch (error) {
    throw new Error(extractError(error));
  }
}

export async function listCalendars() {
  await loadPromise;
  ensureInitialized();
  requireAuth();

  try {
    const calendars = [];
    let pageToken;
    do {
      const response = await window.gapi.client.calendar.calendarList.list({
        maxResults: 250,
        pageToken,
        showDeleted: false,
        minAccessRole: "reader",
      });
      const items = response.result.items || [];
      calendars.push(...items);
      pageToken = response.result.nextPageToken;
    } while (pageToken);
    return calendars;
  } catch (error) {
    throw new Error(extractError(error));
  }
}
