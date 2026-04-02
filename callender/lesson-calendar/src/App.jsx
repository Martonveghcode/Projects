import { useCallback, useEffect, useMemo, useState } from "react";
import dayjs from "dayjs";
import { LogIn, LogOut, Settings } from "lucide-react";
import {
  loadGoogle,
  signIn,
  signOut,
  insertEvent,
  listCalendars,
} from "./lib/google";
import {
  getCfg,
  setCfg,
  getLessons,
  setLessons,
  getPrefs,
  setPrefs,
} from "./lib/storage";
import { uid } from "./lib/ui";
import { DEFAULT_THEME, GOOGLE_COLOR_MAP } from "./lib/constants";
import { resolveLessonColorHex, resolveLessonColorId } from "./lib/events";
import LessonsPanel from "./components/LessonsPanel";
import CreateEventPanel from "./components/CreateEventPanel";
import SetupModal from "./components/SetupModal";
import LessonEditor from "./components/LessonEditor";

const defaultPrefs = () => ({
  theme: { ...DEFAULT_THEME },
});

const TEST_CALENDAR_NAME = "TESTS";

const hydratePrefs = (stored) => {
  const base = defaultPrefs();
  if (!stored) {
    return base;
  }
  return {
    ...base,
    ...stored,
    theme: {
      ...DEFAULT_THEME,
      ...(stored.theme || {}),
    },
  };
};

const normalizeLesson = (lesson) => {
  if (!lesson) return lesson;
  const colorId = resolveLessonColorId(lesson);
  return {
    ...lesson,
    colorId,
    color: resolveLessonColorHex({ ...lesson, colorId }),
  };
};

const sanitizeLessonSlots = (slots = [], lessonIndex) => {
  if (!Array.isArray(slots)) {
    return [];
  }
  return slots
    .map((slot, slotIndex) => {
      if (!slot || typeof slot !== "object") {
        console.warn(`[import] Ignoring invalid slot at index ${slotIndex} for lesson ${lessonIndex}`);
        return null;
      }
      const weekday = Number(slot.weekday);
      const start = typeof slot.start === "string" ? slot.start : "";
      const end = typeof slot.end === "string" ? slot.end : "";
      if (!Number.isInteger(weekday) || weekday < 0 || weekday > 6) {
        console.warn(`[import] Ignoring slot with invalid weekday at index ${slotIndex} for lesson ${lessonIndex}`);
        return null;
      }
      if (!start || !end) {
        console.warn(`[import] Ignoring slot with missing time at index ${slotIndex} for lesson ${lessonIndex}`);
        return null;
      }
      return { weekday, start, end };
    })
    .filter(Boolean);
};

const prepareLessonsFromFile = (lessons) => {
  if (!Array.isArray(lessons)) {
    throw new Error("Lessons must be an array.");
  }
  return lessons.map((lesson, index) => {
    if (!lesson || typeof lesson !== "object") {
      throw new Error(`Lesson at index ${index} is not a valid object.`);
    }
    const name = typeof lesson.name === "string" ? lesson.name.trim() : "";
    if (!name) {
      throw new Error(`Lesson at index ${index} is missing a name.`);
    }
    const sanitized = {
      ...lesson,
      id: typeof lesson.id === "string" && lesson.id.trim() ? lesson.id.trim() : uid("lesson"),
      name,
      slots: sanitizeLessonSlots(lesson.slots, index),
    };
    return normalizeLesson(sanitized);
  });
};
export default function App() {
  const [cfg, setCfgState] = useState(() => getCfg());
  const [setupOpen, setSetupOpen] = useState(() => {
    const stored = getCfg();
    return !stored?.clientId || !stored?.apiKey;
  });
  const [lessons, setLessonsState] = useState(() => getLessons().map(normalizeLesson));
  const [prefs, setPrefsState] = useState(() => hydratePrefs(getPrefs()));
  const [editingLesson, setEditingLesson] = useState(null);

  const [googleReady, setGoogleReady] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleError, setGoogleError] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected] = useState(false);

  const [testCalendarId, setTestCalendarId] = useState(null);
  const [testCalendarLookupAttempted, setTestCalendarLookupAttempted] = useState(false);

  const [eventFeedback, setEventFeedback] = useState(null);
  const [eventSubmitting, setEventSubmitting] = useState(false);

  const theme = useMemo(() => ({ ...DEFAULT_THEME, ...(prefs?.theme || {}) }), [prefs?.theme]);
  const dataSnapshot = useMemo(
    () => ({
      cfg: cfg ? { ...cfg } : null,
      lessons: lessons.map((lesson) => ({ ...lesson })),
      prefs: prefs ? { ...prefs } : null,
    }),
    [cfg, lessons, prefs]
  );

  const updatePrefs = useCallback((updater) => {
    setPrefsState((prev) => {
      const next = typeof updater === "function" ? updater(prev) : updater;
      return hydratePrefs(next);
    });
  }, []);

  const sortedLessons = useMemo(() => {
    return [...lessons].sort((a, b) => a.name.localeCompare(b.name));
  }, [lessons]);

  useEffect(() => {
    setCfg(cfg);
  }, [cfg]);

  useEffect(() => {
    setLessons(lessons);
  }, [lessons]);

  useEffect(() => {
    setPrefs(prefs);
  }, [prefs]);

  useEffect(() => {
    const root = document.documentElement;
    Object.entries(theme).forEach(([key, value]) => {
      root.style.setProperty(`--theme-${key}`, value);
    });
  }, [theme]);

  useEffect(() => {
    let cancelled = false;
    if (cfg?.clientId && cfg?.apiKey) {
      setGoogleLoading(true);
      setGoogleError("");
      loadGoogle(cfg)
        .then(() => {
          if (!cancelled) setGoogleReady(true);
        })
        .catch((error) => {
          if (!cancelled) {
            setGoogleError(error.message || "Failed to load Google libraries");
            setGoogleReady(false);
          }
        })
        .finally(() => {
          if (!cancelled) setGoogleLoading(false);
        });
    } else {
      setGoogleReady(false);
    }
    return () => {
      cancelled = true;
    };
  }, [cfg]);

  useEffect(() => {
    if (!cfg?.clientId || !cfg?.apiKey) {
      try {
        signOut();
      } catch (_) {
        /* ignore */
      }
      setConnected(false);
    }
  }, [cfg]);

  const locateTestCalendar = useCallback(async () => {
    try {
      const calendars = await listCalendars();
      const match = calendars.find((calendar) => (calendar.summary || "").trim().toLowerCase() === TEST_CALENDAR_NAME.toLowerCase());
      const foundId = match?.id || null;
      setTestCalendarId(foundId);
      setTestCalendarLookupAttempted(true);
      return foundId;
    } catch (error) {
      setTestCalendarId(null);
      setTestCalendarLookupAttempted(true);
      throw error;
    }
  }, []);

  useEffect(() => {
    if (!connected) {
      setTestCalendarId(null);
      setTestCalendarLookupAttempted(false);
      return;
    }
    if (testCalendarLookupAttempted) {
      return;
    }
    locateTestCalendar().catch((error) => {
      console.warn(`[calendar] Failed to locate ${TEST_CALENDAR_NAME} calendar`, error);
    });
  }, [connected, locateTestCalendar, testCalendarLookupAttempted]);

  useEffect(() => {
    if (!eventFeedback) return;
    const timer = window.setTimeout(() => setEventFeedback(null), 4000);
    return () => window.clearTimeout(timer);
  }, [eventFeedback]);

  const connectGoogle = useCallback(async () => {
    if (!googleReady) {
      setGoogleError("Add your Google API credentials first");
      setSetupOpen(true);
      return;
    }
    setConnecting(true);
    setGoogleError("");
    try {
      await signIn();
      setConnected(true);
    } catch (error) {
      setGoogleError(error.message || "Failed to connect to Google Calendar");
    } finally {
      setConnecting(false);
    }
  }, [googleReady]);

  const handleDisconnect = useCallback(() => {
    try {
      signOut();
    } catch (_) {
      /* ignore */
    }
    setConnected(false);
    setTestCalendarId(null);
    setTestCalendarLookupAttempted(false);
  }, []);

  const handleSaveCfg = useCallback(
    (nextCfg) => {
      setCfgState(nextCfg);
      setSetupOpen(false);
      handleDisconnect();
    },
    [handleDisconnect]
  );

  const handleThemeChange = useCallback(
    (nextTheme) => {
      updatePrefs((prev) => ({ ...prev, theme: { ...prev.theme, ...nextTheme } }));
    },
    [updatePrefs]
  );

  const handleThemeReset = useCallback(() => {
    updatePrefs((prev) => ({ ...prev, theme: { ...DEFAULT_THEME } }));
  }, [updatePrefs]);

  const handleCreateLesson = useCallback(() => {
    const now = dayjs();
    const start = now.add(1, "hour").startOf("hour");
    const end = start.add(1, "hour");
    const defaultColorId = "9";
    const defaultColor = GOOGLE_COLOR_MAP[defaultColorId]?.hex || "#5484ed";
    setEditingLesson({
      id: null,
      name: "",
      colorId: defaultColorId,
      color: defaultColor,
      slots: [
        {
          weekday: now.day(),
          start: start.format("HH:mm"),
          end: end.format("HH:mm"),
        },
      ],
    });
  }, []);

  const handleSaveLesson = useCallback((draft) => {
    const colorId = resolveLessonColorId(draft);
    const color = resolveLessonColorHex({ ...draft, colorId });
    const lesson = {
      ...draft,
      id: draft.id || uid("lesson"),
      name: draft.name.trim(),
      colorId,
      color,
      slots: draft.slots.map((slot) => ({
        weekday: Number(slot.weekday),
        start: slot.start,
        end: slot.end,
      })),
    };
    setLessonsState((prev) => {
      const existing = prev.find((item) => item.id === lesson.id);
      if (existing) {
        return prev.map((item) => (item.id === lesson.id ? lesson : item));
      }
      return [...prev, lesson];
    });
    setEditingLesson(null);
  }, []);

  const handleDeleteLesson = useCallback((lessonId) => {
    setLessonsState((prev) => prev.filter((item) => item.id !== lessonId));
    setEditingLesson(null);
  }, []);

  const handleImportData = useCallback(
    (payload) => {
      if (!payload || typeof payload !== "object") {
        throw new Error("The file must contain a JSON object.");
      }

      const applied = [];

      if (Object.prototype.hasOwnProperty.call(payload, "cfg")) {
        const incomingCfg = payload.cfg;
        if (incomingCfg === null) {
          setCfgState(null);
          applied.push("credentials");
          handleDisconnect();
        } else if (incomingCfg && typeof incomingCfg === "object") {
          const clientId = typeof incomingCfg.clientId === "string" ? incomingCfg.clientId.trim() : "";
          const apiKey = typeof incomingCfg.apiKey === "string" ? incomingCfg.apiKey.trim() : "";
          if (!clientId || !apiKey) {
            throw new Error("Credentials must include non-empty clientId and apiKey strings.");
          }
          setCfgState({ clientId, apiKey });
          applied.push("credentials");
          handleDisconnect();
        } else {
          throw new Error("Credentials section must be an object with clientId and apiKey.");
        }
      }

      if (Object.prototype.hasOwnProperty.call(payload, "lessons")) {
        const nextLessons = prepareLessonsFromFile(payload.lessons);
        setLessonsState(nextLessons);
        setEditingLesson(null);
        applied.push("lessons");
      }

      if (Object.prototype.hasOwnProperty.call(payload, "prefs")) {
        const incomingPrefs = payload.prefs;
        if (incomingPrefs !== null && typeof incomingPrefs !== "object") {
          throw new Error("Preferences section must be an object or null.");
        }
        setPrefsState(hydratePrefs(incomingPrefs));
        applied.push("preferences");
      }

      if (!applied.length) {
        throw new Error("The file does not include any recognized sections (cfg, lessons, prefs).");
      }

      return applied;
    },
    [handleDisconnect]
  );

  const handleCreateEvent = useCallback(
    async ({ summary, description, startISO, endISO, reminders, colorId, eventType }) => {
      setEventSubmitting(true);
      setEventFeedback(null);
      let success = false;
      try {
        let targetCalendarId = "primary";
        if (eventType === "test") {
          let calendarIdToUse = testCalendarId;
          if (!calendarIdToUse) {
            try {
              calendarIdToUse = await locateTestCalendar();
            } catch (calendarLookupError) {
              throw new Error(calendarLookupError.message || `Failed to locate ${TEST_CALENDAR_NAME} calendar`);
            }
          }
          if (!calendarIdToUse) {
            throw new Error(`Create a calendar named "${TEST_CALENDAR_NAME}" in Google Calendar to store tests.`);
          }
          targetCalendarId = calendarIdToUse;
        }
        const insertPayload = {
          summary,
          description,
          startISO,
          endISO,
          reminders,
          calendarId: targetCalendarId,
        };
        if (eventType !== "test" && colorId) {
          insertPayload.colorId = colorId;
        }
        await insertEvent(insertPayload);
        const successMessage =
          eventType === "test"
            ? `Test event added to "${TEST_CALENDAR_NAME}" calendar`
            : "Event created in Google Calendar";
        setEventFeedback({ type: "success", message: successMessage });
        success = true;
      } catch (error) {
        setEventFeedback({ type: "error", message: error.message || "Failed to create event" });
      } finally {
        setEventSubmitting(false);
      }
      return success;
    },
    [locateTestCalendar, testCalendarId]
  );

  const surfaceStyle = useMemo(
    () => ({ backgroundColor: "var(--theme-surface)", borderColor: "var(--theme-border)" }),
    []
  );

  return (
    <div className="min-h-screen" style={{ backgroundColor: "var(--theme-background)", color: "var(--theme-text)" }}>
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-6 py-10">
        <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-semibold">Lesson Calendar</h1>
            <p className="text-sm text-slate-300/80">
              Define lessons, plan sessions, and send them straight to Google Calendar.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setSetupOpen(true)}
              className="flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-medium transition"
              style={{
                backgroundColor: "var(--theme-surface)",
                borderColor: "var(--theme-border)",
                color: "var(--theme-text)",
              }}
            >
              <Settings className="h-4 w-4" />
              Settings
            </button>
            {connected ? (
              <button
                type="button"
                onClick={handleDisconnect}
                className="btn-accent flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold shadow-soft transition"
              >
                <LogOut className="h-4 w-4" />
                Disconnect
              </button>
            ) : (
              <button
                type="button"
                onClick={connectGoogle}
                disabled={connecting || googleLoading}
                className="btn-accent flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold shadow-soft transition disabled:cursor-not-allowed disabled:opacity-80"
              >
                <LogIn className="h-4 w-4" />
                {connecting ? "Connecting..." : "Connect Google"}
              </button>
            )}
          </div>
        </header>

        {googleError && (
          <div className="rounded-2xl border px-4 py-3 text-sm" style={{ ...surfaceStyle, borderColor: "#f43f5e7f", color: "#fecdd3" }}>
            {googleError}
          </div>
        )}

        <main className="flex flex-col gap-6">
          <CreateEventPanel
            lessons={sortedLessons}
            onCreate={handleCreateEvent}
            isConnected={connected}
            isSubmitting={eventSubmitting}
            feedback={eventFeedback}
          />
          <LessonsPanel
            lessons={sortedLessons}
            onCreate={handleCreateLesson}
            onEdit={setEditingLesson}
            onDelete={handleDeleteLesson}
          />
        </main>
      </div>

      <SetupModal
        open={setupOpen}
        values={cfg}
        onSave={handleSaveCfg}
        onClose={!cfg ? undefined : () => setSetupOpen(false)}
        theme={theme}
        onThemeChange={handleThemeChange}
        onThemeReset={handleThemeReset}
        dataSnapshot={dataSnapshot}
        onImportData={handleImportData}
      />

      {editingLesson && (
        <LessonEditor
          lesson={editingLesson}
          onSave={handleSaveLesson}
          onCancel={() => setEditingLesson(null)}
          onDelete={editingLesson?.id ? handleDeleteLesson : undefined}
        />
      )}
    </div>
  );
}

