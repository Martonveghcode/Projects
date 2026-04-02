# Lesson Calendar

Lesson Calendar is a Vite + React + Tailwind single-page app that helps students manage recurring lessons and push Class/Test/Homework events to Google Calendar.

## Google Cloud setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/), create or select a project.
2. Enable the **Google Calendar API** under *APIs & Services -> Library*.
3. Under *APIs & Services -> Credentials* create a **OAuth client ID (Web application)**. Add `http://localhost:5173` to the Authorized JavaScript origins. Note the generated Client ID.
4. In the same page create an **API key**. Restrict it to the Calendar API if desired.

## Local development

1. Install dependencies with `npm install`.
2. Run `npm run dev` (or press **F5** in VS Code) to start Vite.
3. Your browser should open `http://localhost:5173` automatically.

## First run

1. When the app loads, enter the Google OAuth Client ID and API Key in the setup modal.
2. Click **Connect Google** in the top bar and finish the OAuth consent flow.
3. Add your lessons and weekly slots, then use the Create Event panel to push items to Google Calendar.
4. Optional: use the **Appearance** section in Settings to tweak background, card, border, accent, and text colors. Once connected, the app will remember the connection and attempt to auto-connect next time.
